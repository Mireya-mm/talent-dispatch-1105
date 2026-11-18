# SPDX-License-Identifier: MIT
"""模型输出 schema 校验：输出一律当脏数据，不合规即转人工。"""  # 模块说明

# 顶层必填字段。注意 version_check 不在其中：版本结论由确定性规则给（红线），
# 模型只负责抽变更要素；模型若多吐 version_check 也不信任，最终由规则层覆盖。
REQUIRED_TOP = ["batch_id", "scope", "changes", "missing_items", "handover_draft", "human_review"]  # 顶层必填字段

# 变更项允许的状态值（与 rules.py 保持一致）
VALID_STATUS = {"已确认", "未确认", "未识别", "缺失"}  # 状态白名单


def validate_model_output(payload):
    """校验模型输出的 JSON 结构是否合规。

    入参：payload 已解析的模型输出（dict）。
    出参：dict，{"valid": bool, "errors": [str]}。
    失败行为：任何必填字段缺失、类型错误、状态非法都判 valid=False；
             调用方据此转人工，绝不让脏数据进入正式结论。
    """
    errors = []  # 错误列表
    if not isinstance(payload, dict):  # 顶层必须是字典
        return {"valid": False, "errors": ["顶层不是对象"]}  # 直接判错
    for field in REQUIRED_TOP:  # 遍历必填字段
        if field not in payload:  # 缺失
            errors.append(f"缺少字段：{field}")  # 记录
    changes = payload.get("changes")  # 取变更列表
    if not isinstance(changes, list):  # 类型错误
        errors.append("changes 必须是数组")  # 记录
    else:  # 列表类型正确
        for i, ch in enumerate(changes):  # 遍历每项
            if not isinstance(ch, dict):  # 项非对象
                errors.append(f"changes[{i}] 不是对象")  # 记录
                continue  # 跳过
            st = ch.get("status")  # 取状态
            if st not in VALID_STATUS:  # 状态非法
                errors.append(f"changes[{i}].status 非法：{st}")  # 记录
            if not ch.get("source_ref"):  # 缺来源位置（f42 硬要求）
                errors.append(f"changes[{i}] 缺 source_ref")  # 记录
    hv = payload.get("handover_draft")  # 取交接草稿
    if not isinstance(hv, dict):  # 类型错误
        errors.append("handover_draft 必须是对象")  # 记录
    elif hv.get("ready") is True:  # ready=true 需要额外校验
        # 人工确认注释：ready=true 意味着可出正式交接，必须逐项核实条件，
        # 缺任何一项都无法保证"未确认项没有流到接收方"（f25/f31），故严格卡死。
        if hv.get("latest_confirmed_version") is None:  # 无确认版本
            errors.append("ready=true 但无确认版本")  # 记录
        if hv.get("unconfirmed_items"):  # 存在未确认项
            errors.append("ready=true 但存在未确认项")  # 记录
    return {"valid": len(errors) == 0, "errors": errors}  # 返回校验结果
