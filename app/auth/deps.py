# SPDX-License-Identifier: MIT
"""FastAPI 鉴权依赖：从 Authorization 头解析 token，提供要求权限的依赖工厂。

用法：路由函数签名加 user: dict = Depends(require("read"))。
- require(action) 先要求 token 有效，再查权限矩阵里该角色是否有 action。
- 任一步失败抛 AuthError，由 main.py 的异常处理器包成统一 {ok,data,error}。
- 模型没有任何 token，也进不了任何受保护路由——零权限从结构上保证。
"""  # 模块说明

from fastapi import Header, Depends  # 请求头依赖与依赖注入
from app.auth.security import decode_token  # token 校验
from app.core.config import get  # 读权限矩阵
from app.auth.auth_store import get_user  # 查用户当前状态


class AuthError(Exception):
    """鉴权失败异常，携带错误码与信息，供全局处理器转统一响应。"""  # 类说明

    def __init__(self, code, msg):
        """构造鉴权异常。

        入参：code(str) 语义码；msg(str) 信息。
        出参：无。
        失败行为：无。
        """
        self.code = code  # 错误码
        self.msg = msg  # 错误信息
        super().__init__(msg)  # 初始化父类


def current_user(authorization: str = Header(default="")):
    """解析当前用户（依赖函数）。

    入参：authorization(str) Authorization 头，形如 "Bearer xxx"。
    出参：dict，{"username":str,"role":str}。
    失败行为：token 缺失/无效/用户被停用一律抛 AuthError，不给可用身份。
    """
    if not authorization.startswith("Bearer "):  # 无 Bearer 头
        raise AuthError("FORBIDDEN", "缺少 token，请先登录")  # 拒绝
    token = authorization.split(" ", 1)[1].strip()  # 取 token
    d = decode_token(token)  # 校验 token
    if not d["ok"]:  # token 无效
        raise AuthError("FORBIDDEN", d["reason"])  # 拒绝
    # 安全审查注释：token 有效仍要查一次用户当前状态——管理员停用账号后，
    # 未过期的旧 token 也必须立即失效，否则停用形同虚设。
    row = get_user(d["username"])  # 查用户
    if row is None or not row["active"]:  # 不存在或停用
        raise AuthError("FORBIDDEN", "账号不可用或已被停用")  # 拒绝
    return {"username": d["username"], "role": d["role"], "display_name": row["display_name"]}  # 返回用户


def require(action):
    """生成「要求某权限」的依赖工厂。

    入参：action(str) 动作名，对应 config.yaml permissions 里的键。
    出参：callable 依赖函数，返回用户信息；权限不足抛 AuthError。
    失败行为：角色无该权限抛 AuthError(FORBIDDEN)。
    """
    def dep(user: dict = Depends(current_user)):  # 依赖当前用户
        perms = get("permissions", user["role"], {}) or {}  # 读该角色权限
        if not perms.get(action, False):  # 无此权限
            # 权限校验注释：显性拒绝并说明缺什么权限，禁止静默跳过；
            # 模型角色根本不在权限矩阵里，天然无法通过任何 require。
            raise AuthError("FORBIDDEN", f"角色 {user['role']} 无权限：{action}")  # 拒绝
        return user  # 放行
    return dep  # 返回依赖函数
