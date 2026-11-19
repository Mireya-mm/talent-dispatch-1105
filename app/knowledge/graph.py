# SPDX-License-Identifier: MIT
"""知识库适配层：保持原三函数签名，数据改由 SQLite 只读知识库提供。

设计取舍（对应 f30/f31）：不做向量检索、不做模糊拼接。关联编号缺失就是缺失，
直接降级人工，绝不靠"看起来像"去猜关联，避免把两张不同单据错连到一起。
全部只读，代码里没有任何写入/更新接口；写入只在离线初始化脚本里发生。
"""  # 模块说明

from app.core.config import get  # 读取试点配置
from app.knowledge.store import get_fact, resolve_links  # 从 SQLite 知识库取数


def get_position_facts(position_code):
    """按岗位代号查询硬条件事实（只读，数据来自知识库 facts 表）。

    入参：position_code(str) 岗位代号。
    出参：dict 或 None；命中返回含 hard_conditions/rule_version/source/link_key 的事实，未命中 None。
    失败行为：未命中返回 None，由上层决定是否转人工，不抛异常、不猜近似岗位。
    """
    fact = get_fact(position_code)  # 从知识库精确查（内部已深拷贝）
    if fact is None:  # 未命中
        return None  # 缺失
    a = fact["attrs"]  # 取属性
    # 只读保证注释：store.get_fact 已返回深拷贝，这里再组装新字典，
    # 调用方即便改动 hard_conditions 列表也不会污染知识库事实表。
    return {  # 适配成原接口结构
        "hard_conditions": list(a.get("hard_conditions", [])),  # 硬条件列表副本
        "rule_version": a.get("rule_version"),  # 规则版本基准
        "source": fact["source"],  # 来源位置
        "link_key": a.get("link_key"),  # 关联编号
    }  # 返回事实副本


def resolve_by_link(link_key):
    """按关联编号解析关联单据（只读图谱精确匹配）。

    入参：link_key(str) 关联编号，可为 None。
    出参：dict，{"found": bool, "documents": [str], "reason": str}。
    失败行为：link_key 为 None 或图谱无匹配时 found=False，明确降级人工，
             绝不返回"可能是"的猜测结果（对应 f30 关联编号缺失直接转人工）。
    """
    return resolve_links(link_key)  # 委托知识库图谱查询，保持返回结构一致


def in_pilot(position_code):
    """判断岗位是否属于已锁定的试点清单（清单由管理员锁定，存配置）。

    入参：position_code(str) 岗位代号。
    出参：dict，{"locked": bool, "in_scope": bool, "reason": str}。
    失败行为：试点清单未锁定（为空）时 locked=False、in_scope=False，
             整批暂停——这是 f05 边界要求，不默认全量放行。
    """
    positions = get("pilot", "position_list") or []  # 读取试点岗位清单
    if not positions:  # 清单为空=未锁定
        return {"locked": False, "in_scope": False, "reason": "试点岗位清单未锁定，整批暂停"}  # 暂停
    return {  # 清单已锁定，判断是否命中
        "locked": True,  # 已锁定
        "in_scope": position_code in positions,  # 精确判断
        "reason": "命中试点清单" if position_code in positions else "不在试点清单",  # 原因
    }  # 返回判定
