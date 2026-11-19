# SPDX-License-Identifier: MIT
"""人工确认闸门：版本确认、来源补齐、正式签认三道，模型零审批权。"""  # 模块说明

from app.core.config import get  # 读取红线配置


def evaluate_human_review(scope, model_data, schema_valid, version_result, link_result):
    """综合判定是否必须转人工，以及原因（不代替人做确认）。

    入参：scope(dict) 范围核对结果；model_data(dict|None) 模型输出；
          schema_valid(bool) schema 是否通过；version_result(dict) 版本规则结果；
          link_result(dict) 关联编号解析结果。
    出参：dict，{"required": bool, "reasons": [str], "queue": str}。
    失败行为：任一红线触发即 required=True；输入异常一律按"需人工"处理，
             绝不返回可自动放行的结论。
    """
    reasons = []  # 转人工原因列表
    if not scope.get("in_scope"):  # 不在试点范围
        reasons.append("不在试点范围或清单未锁定：" + scope.get("reason", ""))  # 记录
    if model_data is None:  # 模型调用失败
        reasons.append("模型不可用或输出为空")  # 记录
    if not schema_valid:  # schema 不合规
        reasons.append("模型输出不符合 schema")  # 记录
    if not version_result.get("consistent"):  # 版本不一致或缺失
        reasons.append("版本不一致：" + version_result.get("reason", ""))  # 记录
    if not link_result.get("found"):  # 关联编号缺失
        reasons.append("关联编号缺失：" + link_result.get("reason", ""))  # 记录
    # 人工确认注释：模型输出里只要存在未确认项，就不能出可对外交接版本（f25/f31/f44）。
    # 这里做的是"拦住"，不是"替人判确认"——确认动作只能由业务负责人完成。
    if model_data:  # 有模型输出
        changes = model_data.get("changes") or []  # 取变更列表
        for ch in changes:  # 遍历
            if ch.get("status") != "已确认":  # 非已确认
                reasons.append(f"字段 {ch.get('field','?')} 状态为 {ch.get('status')}")  # 记录
                break  # 只记一条代表性原因，避免刷屏
    required = len(reasons) > 0  # 有原因就必须转人工
    if not required:  # 看似无需人工
        # 人工确认注释：即使全部规则通过，正式签认仍需授权人完成（f41/f52），
        # 模型零审批权，故这里仍标记需人工签认，只是原因不同。
        reasons.append("正式签认须由业务负责人完成（模型零审批权）")  # 记录
        required = True  # 仍需人工
    return {"required": required, "reasons": reasons, "queue": "转人工" if required else ""}  # 返回判定


def confirm_result(role, action, human_review):
    """业务负责人正式确认/退回的入口（演练中只校验权限，不落库）。

    入参：role(str) 操作角色；action(str) confirm/reject；human_review(dict) 人工复核结论。
    出参：dict，{"allowed": bool, "reason": str}。
    失败行为：角色无权或动作未知一律拒绝；本函数不写任何数据，只返回判定，
             真实签认留痕格式待质量复核负责人补齐（见 docs/提示词.md 待补表）。
    """
    from app.core.guard import check_permission  # 局部导入，避免循环依赖
    if action not in ("confirm", "reject"):  # 未知动作
        return {"allowed": False, "reason": "未知动作"}  # 拒绝
    perm = check_permission(role, "confirm_version")  # 校验确认版本权限
    if not perm["allowed"]:  # 无权
        # 权限校验注释：只有业务负责人能确认版本；一线、质量、客户、模型均无权，
        # 模型零审批权是案例红线，代码里不存在模型调用本函数的路径。
        return {"allowed": False, "reason": perm["reason"]}  # 拒绝
    return {"allowed": True, "reason": "权限通过，待真实签认留痕格式补齐后执行"}  # 允许但提示待补
