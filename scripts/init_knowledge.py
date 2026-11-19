# SPDX-License-Identifier: MIT
"""离线初始化知识库：建表 + 灌入合成演练样本（唯一允许写知识库的脚本）。

用法：python3 scripts/init_knowledge.py
说明：数据为虚构演练样本，非真实业务，不作基线（f12 红线）。
      业务运行时代码全程只读，写入只发生在这个离线脚本里。
      重复执行会先清表再灌数，保证幂等。
"""  # 脚本说明

import sys  # 系统路径
from pathlib import Path  # 路径处理
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 加入仓库根，否则找不到 app 包

import json  # JSON 序列化属性
from app.knowledge.db import connect_rw, db_path  # 可写连接（仅初始化用）

# —— 合成演练数据：岗位事实（对应旧 FACTS，保持一致以便回归）——
FACTS = {  # 岗位事实常量
    "POS-A": {  # 岗位 A
        "attrs": {  # 属性
            "hard_conditions": ["夜班资格", "电工证"],  # 硬条件
            "rule_version": "rule-v2",  # 规则版本基准
            "link_key": "LK-1001",  # 关联编号
        },  # 属性结束
        "source": "需求单 DEMAND-A / 字段-技能条件",  # 来源位置
    },  # 岗位 A 结束
    "POS-B": {  # 岗位 B
        "attrs": {  # 属性
            "hard_conditions": ["叉车证"],  # 硬条件
            "rule_version": "rule-v1",  # 规则版本基准
            "link_key": "LK-1002",  # 关联编号
        },  # 属性结束
        "source": "需求单 DEMAND-B / 字段-技能条件",  # 来源位置
    },  # 岗位 B 结束
}  # 事实常量结束

# —— 图谱边：关联编号 -> 关联单据（对应旧 LINK_INDEX）——
EDGES = [  # 三元组边列表
    ("LK-1001", "关联单据", "DEMAND-A"),  # 关联需求单
    ("LK-1001", "关联单据", "HANDOVER-A"),  # 关联交接单
    ("LK-1001", "关联单据", "RULE-A"),  # 关联规则单
    ("LK-1002", "关联单据", "DEMAND-B"),  # 关联需求单
    ("LK-1002", "关联单据", "HANDOVER-B"),  # 关联交接单
    ("LK-1002", "关联单据", "RULE-B"),  # 关联规则单
    ("POS-A", "要求技能", "夜班资格"),  # 岗位要求技能
    ("POS-A", "要求技能", "电工证"),  # 岗位要求技能
    ("POS-B", "要求技能", "叉车证"),  # 岗位要求技能
]  # 边列表结束

# —— 文档块：供 RAG 检索的证据片段，每条带来源位置 ——
DOCUMENTS = [  # 文档列表
    ("DOC-001", "需求单 DEMAND-A 技能条件",  # 编号与标题
     "需求单版本 demand-v2，岗位 POS-A，技能条件要求夜班资格与电工证，班次白班，来源需求单 DEMAND-A 字段技能条件。",  # 正文
     "需求单 DEMAND-A / 字段-技能条件"),  # 来源位置
    ("DOC-002", "交接单 HANDOVER-A 岗位信息",  # 编号与标题
     "交接单版本 handover-v1，岗位 POS-A，技能条件普通岗，班次白班，来源交接单 HANDOVER-A。",  # 正文
     "交接单 HANDOVER-A / 岗位信息"),  # 来源位置
    ("DOC-003", "电话记录：POS-A 口头变更",  # 编号与标题
     "电话里把技能要求改成需要夜班资格，需求单未回写；临时加夜班，已确认的白班班次没同步，状态未确认。",  # 正文
     "电话记录 2026-11-05 / POS-A"),  # 来源位置
    ("DOC-004", "规则单 RULE-A 版本基准",  # 编号与标题
     "规则单 RULE-A 版本 rule-v2，岗位 POS-A 硬条件为夜班资格与电工证，是版本比对的确定性基准。",  # 正文
     "规则单 RULE-A / 版本字段"),  # 来源位置
    ("DOC-005", "群消息：夜班安排",  # 编号与标题
     "群里说 POS-A 夜班临时调整，但没有同步到交接单，属于未确认的口头变更，需要业务负责人确认。",  # 正文
     "群消息 2026-11-05 / POS-A"),  # 来源位置
    ("DOC-006", "需求单 DEMAND-B 技能条件",  # 编号与标题
     "需求单版本 demand-v1，岗位 POS-B，技能条件要求叉车证，来源需求单 DEMAND-B 字段技能条件。",  # 正文
     "需求单 DEMAND-B / 字段-技能条件"),  # 来源位置
]  # 文档列表结束


def build_schema(cur):
    """建表（幂等，先删后建）。

    入参：cur(sqlite3.Cursor) 游标。
    出参：无。
    失败行为：无（DDL 确定性执行）。
    """
    cur.execute("DROP TABLE IF EXISTS facts")  # 删事实表
    cur.execute("DROP TABLE IF EXISTS edges")  # 删边表
    cur.execute("DROP TABLE IF EXISTS documents")  # 删文档表
    cur.execute("""CREATE TABLE facts (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        name TEXT NOT NULL,
        attrs_json TEXT NOT NULL,
        source TEXT NOT NULL
    )""")  # 建事实表（SQL 内不写 Python 注释）
    cur.execute("""CREATE TABLE edges (
        from_id TEXT NOT NULL,
        rel TEXT NOT NULL,
        to_id TEXT NOT NULL,
        source TEXT NOT NULL
    )""")  # 建图谱边表
    cur.execute("""CREATE TABLE documents (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        source TEXT NOT NULL
    )""")  # 建文档表


def seed(cur):
    """灌入合成演练数据。

    入参：cur(sqlite3.Cursor) 游标。
    出参：无。
    失败行为：无（数据为常量，确定性写入）。
    """
    for eid, obj in FACTS.items():  # 遍历岗位事实
        cur.execute(  # 插入事实
            "INSERT INTO facts(id,type,name,attrs_json,source) VALUES(?,?,?,?,?)",  # SQL
            (eid, "岗位", eid, json.dumps(obj["attrs"], ensure_ascii=False), obj["source"]),  # 参数
        )  # 插入结束
    for frm, rel, to in EDGES:  # 遍历图谱边
        cur.execute(  # 插入边
            "INSERT INTO edges(from_id,rel,to_id,source) VALUES(?,?,?,?)",  # SQL
            (frm, rel, to, "合成演练样本"),  # 参数
        )  # 插入结束
    for did, title, content, source in DOCUMENTS:  # 遍历文档
        cur.execute(  # 插入文档
            "INSERT INTO documents(id,title,content,source) VALUES(?,?,?,?)",  # SQL
            (did, title, content, source),  # 参数
        )  # 插入结束


def main():
    """主流程：建表 + 灌数 + 打印统计。

    入参：无。
    出参：无（副作用：写数据库文件）。
    失败行为：异常直接抛出，退出非零，提示初始化失败。
    """
    conn = connect_rw()  # 可写连接（唯一写入入口）
    try:  # 建表灌数
        cur = conn.cursor()  # 取游标
        build_schema(cur)  # 建表
        seed(cur)  # 灌数
        conn.commit()  # 提交事务
        n_fact = cur.execute("SELECT COUNT(*) FROM facts").fetchone()[0]  # 事实数
        n_edge = cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0]  # 边数
        n_doc = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]  # 文档数
        print(f"知识库初始化完成：{db_path()}")  # 打印路径
        print(f"  事实 {n_fact} 条 / 图谱边 {n_edge} 条 / 文档块 {n_doc} 条")  # 统计
        print("  数据声明：合成演练样本，非真实业务，不作基线")  # 声明
    finally:  # 无论成功失败
        conn.close()  # 关闭连接


if __name__ == "__main__":  # 脚本入口
    main()  # 执行
