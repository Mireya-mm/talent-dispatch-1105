# SPDX-License-Identifier: MIT
"""知识库只读查询层：事实表、关联图谱、bigram 检索。全部只读，返回深拷贝副本。

三能力从这里取「确定性事实」，不靠模型记忆：
- 岗位硬条件、规则版本基准 → fact 表（取代旧 graph.py 的硬编码 FACTS）。
- 关联编号 → 图谱 relation 表精确解析（缺失就是缺失，不猜不拼）。
- 检索 → 文档块的 bigram 重合度打分，结果带来源位置，供提示词当证据用。
"""  # 模块说明

import copy  # 深拷贝，杜绝调用方反向改动事实
from collections import defaultdict  # 分组计数
from app.knowledge.db import connect_ro  # 只读连接（业务唯一通道）
from app.core.config import get  # 读检索阈值配置


def _bigrams(text):
    """把文本切成相邻双字集合（字符级 bigram），用于不依赖分词库的粗粒度检索。

    入参：text(str) 原始文本。
    出参：set[str] 双字集合；长度不足 2 时返回原字符集合。
    失败行为：空输入返回空集合，由上层判为不相关，不抛异常。
    """
    s = "".join(ch for ch in (text or "") if not ch.isspace())  # 去空白
    if len(s) < 2:  # 太短
        return {s} if s else set()  # 单字或空
    return {s[i:i + 2] for i in range(len(s) - 1)}  # 相邻双字集合


def _overlap(q_set, d_set):
    """计算两个 bigram 集合的重合度（交集/查询集大小）。

    入参：q_set(set) 查询 bigram；d_set(set) 文档 bigram。
    出参：float 重合度，0~1。
    失败行为：查询集为空返回 0，避免除零。
    """
    if not q_set:  # 空查询
        return 0.0  # 无重合
    return len(q_set & d_set) / len(q_set)  # 交集占查询比例


def get_fact(entity_id):
    """按实体 ID 取岗位/单据事实（只读，深拷贝）。

    入参：entity_id(str) 实体编号，如 POS-A。
    出参：dict 或 None；命中返回 {id,type,name,attrs,source}，未命中 None。
    失败行为：未命中返回 None，由上层转人工，不猜近似实体。
    """
    conn = connect_ro()  # 只读连接
    try:  # 查询并复制
        row = conn.execute("SELECT * FROM facts WHERE id=?", (entity_id,)).fetchone()  # 精确查
        if row is None:  # 未命中
            return None  # 缺失
        d = dict(row)  # 转字典
        import json  # 局部导入
        d["attrs"] = json.loads(d["attrs_json"])  # 解析属性 JSON
        d.pop("attrs_json", None)  # 移除原始 JSON 串
        return copy.deepcopy(d)  # 深拷贝返回
    finally:  # 无论成功失败
        conn.close()  # 关闭连接


def resolve_links(link_key):
    """按关联编号解析关联单据（只读图谱精确匹配）。

    入参：link_key(str) 关联编号或 None。
    出参：dict，{"found":bool,"documents":[str],"reason":str}。
    失败行为：编号缺失或无匹配 found=False，明确降级人工，绝不拼接猜测。
    """
    if not link_key:  # 编号为空
        return {"found": False, "documents": [], "reason": "关联编号缺失，转人工比对"}  # 降级
    conn = connect_ro()  # 只读连接
    try:  # 查图谱边
        rows = conn.execute(  # 按关联编号找关联单据
            "SELECT to_id FROM edges WHERE from_id=? AND rel='关联单据'", (link_key,)
        ).fetchall()  # 取所有关联
        if not rows:  # 无匹配
            return {"found": False, "documents": [], "reason": "关联编号无匹配，转人工比对"}  # 降级
        return {"found": True, "documents": [r["to_id"] for r in rows], "reason": "关联编号命中"}  # 命中
    finally:  # 无论成功失败
        conn.close()  # 关闭连接


def search(query, top_k=None):
    """对文档块做 bigram 检索，返回带来源的证据片段（RAG 检索部分）。

    入参：query(str) 检索文本；top_k(int|None) 返回条数，None 读配置。
    出参：list[dict]，每项 {id,title,score,source,snippet}，按分数降序。
    失败行为：低于阈值或空查询返回空列表（fail-closed：宁可不给证据，不给错的）。
    """
    k = top_k if top_k is not None else get("knowledge", "search_top_k", 3)  # 返回条数
    threshold = get("knowledge", "min_bigram_overlap", 0.12)  # 相关阈值
    q_set = _bigrams(query)  # 查询 bigram
    if not q_set:  # 空查询
        return []  # 无结果
    conn = connect_ro()  # 只读连接
    try:  # 扫描文档块打分
        rows = conn.execute("SELECT * FROM documents").fetchall()  # 全部文档（演练量小，全扫）
    finally:  # 无论成功失败
        conn.close()  # 关闭连接
    scored = []  # 打分结果
    for r in rows:  # 逐文档
        d_text = (r["title"] or "") + " " + (r["content"] or "")  # 标题+正文
        score = _overlap(q_set, _bigrams(d_text))  # 算重合度
        if score >= threshold:  # 达到阈值
            scored.append({  # 证据片段
                "id": r["id"],  # 文档编号
                "title": r["title"],  # 标题
                "score": round(score, 3),  # 分数
                "source": r["source"],  # 来源位置（f42 硬要求）
                "snippet": (r["content"] or "")[:160],  # 摘要前 160 字
            })  # 加入结果
    scored.sort(key=lambda x: x["score"], reverse=True)  # 按分降序
    return scored[:k]  # 取前 k 条


def evidence_notice():
    """返回数据声明，明确样本为合成演练、不作基线（f12 红线）。

    入参：无。
    出参：str 声明文本。
    失败行为：无（纯配置读取）。
    """
    return get("knowledge", "seed_notice", "合成演练样本，不作基线")  # 读声明配置
