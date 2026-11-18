# SPDX-License-Identifier: MIT
"""只读知识库：岗位硬条件事实表 + 关联编号索引。

设计取舍（对应 f30/f31）：不做向量检索、不做模糊拼接。关联编号缺失就是缺失，
直接降级人工，绝不靠"看起来像"去猜关联，避免把两张不同单据错连到一起。
全部只读，代码里没有任何写入/更新接口。
"""  # 模块说明

import copy  # 深拷贝，防止调用方改动事实表内部的可变对象
from app.core.config import get  # 读取试点配置

# 岗位硬条件事实表：键=岗位代号，值=该岗位的硬条件与当前确认版本。
# 数据为合成演练样本（非真实业务），来源见访谈 f31；真实值待业务负责人补齐。
FACTS = {  # 事实表常量，只读
    "POS-A": {  # 岗位代号 POS-A
        "hard_conditions": ["夜班资格", "电工证"],  # 硬条件列表
        "rule_version": "rule-v2",  # 规则版本
        "source": "需求单 DEMAND-A / 字段-技能条件",  # 来源位置
        "link_key": "LK-1001",  # 关联编号
    },
    "POS-B": {  # 岗位代号 POS-B
        "hard_conditions": ["叉车证"],  # 硬条件列表
        "rule_version": "rule-v1",  # 规则版本
        "source": "需求单 DEMAND-B / 字段-技能条件",  # 来源位置
        "link_key": "LK-1002",  # 关联编号
    },
}

# 关联编号索引：link_key -> 该关联下的单据清单（只读）。
LINK_INDEX = {  # 索引常量
    "LK-1001": ["DEMAND-A", "HANDOVER-A", "RULE-A"],  # 关联下的三份单据
    "LK-1002": ["DEMAND-B", "HANDOVER-B", "RULE-B"],  # 关联下的三份单据
}


def get_position_facts(position_code):
    """按岗位代号查询硬条件事实（只读）。

    入参：position_code(str) 岗位代号。
    出参：dict 或 None；命中返回事实副本，未命中返回 None。
    失败行为：未命中返回 None，由上层决定是否转人工，不抛异常、不猜近似岗位。
    """
    fact = FACTS.get(position_code)  # 精确匹配，不做模糊
    # 只读保证注释：必须深拷贝（含嵌套列表），浅拷贝会让调用方通过 fact["hard_conditions"]
    # 反向改动事实表，破坏"只读知识库"红线，故用 copy.deepcopy。
    return copy.deepcopy(fact) if fact else None  # 深拷贝返回，彻底隔离内部状态


def resolve_by_link(link_key):
    """按关联编号解析关联单据（只读）。

    入参：link_key(str) 关联编号，可为 None。
    出参：dict，{"found": bool, "documents": [str], "reason": str}。
    失败行为：link_key 为 None 或不在索引中时 found=False，明确降级人工，
             绝不返回"可能是"的猜测结果（对应 f30 关联编号缺失直接转人工）。
    """
    if not link_key:  # 关联编号为空
        return {"found": False, "documents": [], "reason": "关联编号缺失，转人工比对"}  # 降级
    docs = LINK_INDEX.get(link_key)  # 精确查索引
    if docs is None:  # 索引无此编号
        return {"found": False, "documents": [], "reason": "关联编号无匹配，转人工比对"}  # 降级
    return {"found": True, "documents": list(docs), "reason": "关联编号命中"}  # 返回单据清单


def in_pilot(position_code):
    """判断岗位是否属于已锁定的试点清单。

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
    }
