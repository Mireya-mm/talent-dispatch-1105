# SPDX-License-Identifier: MIT
"""权限校验与数据红线：越权即拒绝并留痕，绝不静默放行。"""  # 模块说明

from app.core.config import get  # 读取权限矩阵与红线配置
from app.core.response import fail  # 统一失败结构


def check_permission(role, action):
    """校验某角色是否可执行某动作。

    入参：role(str) 角色标识；action(str) 动作名（read/submit_change/confirm_version/halt）。
    出参：dict，{"allowed": bool, "reason": str}。
    失败行为：角色或动作未定义时按"拒绝"处理（fail-closed），不放行未知主体。
    """
    perms = get("permissions", role)  # 从配置读取该角色权限
    if perms is None:  # 角色不存在
        return {"allowed": False, "reason": "未知角色，拒绝"}  # fail-closed
    allowed = perms.get(action)  # 取对应动作权限
    if allowed is None:  # 动作未定义
        return {"allowed": False, "reason": "未知动作，拒绝"}  # fail-closed
    return {  # 返回判定结果
        "allowed": bool(allowed),  # 转布尔
        "reason": "允许" if allowed else "该角色无此权限",  # 原因说明
    }


def check_guardrails(requested):
    """校验请求是否触碰数据红线（写回/自动决策/发消息/模型审批）。

    入参：requested(dict) 请求中声明的动作标志，如 {"writeback": true}。
    出参：dict，{"ok": bool, "violations": [str]}。
    失败行为：任何红线被触碰返回 ok=False；红线配置缺失时按最严格处理（全禁）。
    """
    g = get("guardrails", None) or {}  # 读取红线配置，缺失用空字典（最严格）
    violations = []  # 违规项列表
    mapping = {  # 请求标志 -> 红线配置键（配置为 false 表示禁止）
        "writeback": "auto_writeback",  # 自动回写
        "auto_decide": "auto_decide",  # 自动决策资格
        "send_to_real_person": "send_to_real_person",  # 向真人发安排
        "model_approval": "model_has_approval",  # 模型审批
    }
    for flag, cfg_key in mapping.items():  # 遍历映射
        if requested.get(flag):  # 请求里声明了该动作
            if not g.get(cfg_key, False):  # 红线禁止该动作（默认禁止）
                violations.append(flag)  # 记录违规
    return {"ok": len(violations) == 0, "violations": violations}  # 无违规才放行


def permission_response(role, action):
    """权限校验 + 统一响应封装，供路由层直接返回。

    入参：role(str) 角色；action(str) 动作。
    出参：dict 或 None；None 表示放行，dict 表示应直接返回的失败响应。
    失败行为：权限不足时返回 fail 结构（E_PERM_DENIED），不抛异常。
    """
    result = check_permission(role, action)  # 调用权限判定
    if not result["allowed"]:  # 不允许
        # 安全审查注释：权限不足必须显性拒绝并带原因，禁止静默跳过校验。
        return fail("FORBIDDEN", f"权限不足：{result['reason']}")  # 返回统一失败
    return None  # 放行
