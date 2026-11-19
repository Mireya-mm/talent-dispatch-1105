# SPDX-License-Identifier: MIT
"""版本一致性确定性规则：不调模型，纯比较。"""  # 模块说明

ALLOWED_STATUS = {"已确认", "未确认", "未识别", "缺失"}  # 合法状态集合


def compare_versions(demand_version, handover_version, rule_version):
    """比较需求单/交接单/规则版本三者是否一致（确定性，不用模型）。

    入参：三个版本号字符串，可为 None。
    出参：dict，{"consistent": bool, "fields": [str], "reason": str}。
    失败行为：任一版本为 None 视为不一致并列出缺项，不抛异常。
    """
    versions = {  # 版本映射
        "demand_version": demand_version,  # 需求单版本
        "handover_version": handover_version,  # 交接单版本
        "rule_version": rule_version,  # 规则版本
    }
    missing = [k for k, v in versions.items() if not v]  # 缺失的版本字段
    vals = [v for v in versions.values() if v]  # 非空版本值
    inconsistent = []  # 不一致字段列表
    if vals and len(set(vals)) > 1:  # 存在多个不同版本
        inconsistent = list(versions.keys())  # 全部字段列为不一致
    consistent = len(missing) == 0 and len(inconsistent) == 0  # 全部有值且一致才算一致
    reason = "三个版本一致" if consistent else ("版本缺失：" + ",".join(missing) if missing else "版本不一致")  # 原因
    return {"consistent": consistent, "fields": missing + inconsistent, "reason": reason}  # 返回结果


def has_unconfirmed(changes):
    """检查变更列表中是否存在非"已确认"状态的项。

    入参：changes(list[dict])，每项含 status 字段。
    出参：bool，存在未确认/未识别/缺失则为 True。
    失败行为：status 非法（不在 ALLOWED_STATUS）按"未确认"处理（fail-closed），
             不把非法状态当成已确认放过。
    """
    for c in changes:  # 遍历变更
        st = c.get("status")  # 取状态
        if st not in ALLOWED_STATUS:  # 非法状态
            return True  # 按未确认处理，转人工
        if st != "已确认":  # 非已确认
            return True  # 存在未确认项
    return False  # 全部已确认
