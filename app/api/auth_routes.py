# SPDX-License-Identifier: MIT
"""鉴权与管理路由：登录、当前用户、用户管理、锁试点、审计、知识库检索。

所有受保护路由用 Depends(require(动作)) 强制鉴权；公开路由只有 /auth/login。
管理员动作（建用户/停用/锁试点/看审计）要求 admin 角色对应权限。
"""  # 模块说明

from fastapi import APIRouter, Depends  # 路由器与依赖
from pydantic import BaseModel  # 请求体模型
from typing import Optional  # 可选类型
from app.core.config import get, load_config  # 读配置（锁试点要改内存配置）
from app.core.response import ok, fail  # 统一响应
from app.auth.auth_store import (  # 用户存储
    authenticate, get_user, list_users, create_user, set_active, audit, list_audit,
)
from app.auth.security import issue_token  # 签发 token
from app.auth.deps import require  # 权限依赖
from app.knowledge import store as kb  # 知识库只读查询


class LoginRequest(BaseModel):  # 登录请求体
    username: str  # 用户名
    password: str  # 口令


class UserCreateRequest(BaseModel):  # 建用户请求体
    username: str  # 用户名
    password: str  # 口令
    role: str  # 角色
    display_name: str = ""  # 显示名


class ActiveRequest(BaseModel):  # 启用/停用请求体
    active: bool  # 是否启用


class PilotLockRequest(BaseModel):  # 锁定试点清单请求体
    positions: list[str]  # 岗位代号列表


class SearchRequest(BaseModel):  # 检索请求体
    query: str  # 检索文本
    top_k: Optional[int] = None  # 返回条数


router = APIRouter(prefix="/v1", tags=["auth"])  # 路由前缀


def _valid_role(role):
    """校验角色是否在权限矩阵中定义。

    入参：role(str) 角色标识。
    出参：bool 是否合法。
    失败行为：无。
    """
    return role in (get("permissions", None) or {})  # 权限矩阵里存在即合法


@router.post("/auth/login")  # 登录（公开）
def login(req: LoginRequest):
    """登录：认证口令，成功签发带角色的 token 并记审计。

    入参：req(LoginRequest) 用户名与口令。
    出参：统一结构；成功 data 含 token/role/username。
    失败行为：认证失败返回 fail(E_PERM_DENIED)，不发 token。
    """
    r = authenticate(req.username, req.password)  # 认证
    if not r["ok"]:  # 失败
        return fail("FORBIDDEN", r["reason"])  # 拒绝
    token = issue_token(req.username, r["role"])  # 签发 token
    audit(req.username, "login", "登录成功")  # 记审计
    return ok({"token": token, "role": r["role"], "username": req.username})  # 返回


@router.get("/auth/me")  # 当前用户
def me(user: dict = Depends(require("read"))):
    """查看当前登录用户的身份（需有效 token）。

    入参：user(dict) 由依赖注入的当前用户。
    出参：统一结构，data 含用户名/角色/显示名。
    失败行为：未登录或无 read 权限由依赖抛 AuthError。
    """
    return ok({"username": user["username"], "role": user["role"], "display_name": user["display_name"]})  # 返回


@router.get("/admin/users")  # 列用户
def admin_list_users(user: dict = Depends(require("manage_users"))):
    """管理员列出全部用户。

    入参：user(dict) 当前管理员。
    出参：统一结构，data 为用户列表。
    失败行为：无 manage_users 权限由依赖拒绝。
    """
    audit(user["username"], "list_users", "查看用户列表")  # 记审计
    return ok(list_users())  # 返回


@router.post("/admin/users")  # 建用户
def admin_create_user(req: UserCreateRequest, user: dict = Depends(require("manage_users"))):
    """管理员创建用户。

    入参：req(UserCreateRequest) 新用户信息；user(dict) 当前管理员。
    出参：统一结构；成功 data 含用户名与角色。
    失败行为：角色非法或用户名已存在返回 fail。
    """
    if not _valid_role(req.role):  # 角色非法
        return fail("BAD_REQUEST", f"未知角色：{req.role}")  # 拒绝
    r = create_user(req.username, req.password, req.role, req.display_name or req.username)  # 建用户
    if not r["ok"]:  # 失败
        return fail("BAD_REQUEST", r["reason"])  # 拒绝
    audit(user["username"], "create_user", f"创建用户 {req.username} 角色 {req.role}")  # 记审计
    return ok({"username": req.username, "role": req.role})  # 返回


@router.post("/admin/users/{username}/active")  # 启用/停用
def admin_set_active(username: str, req: ActiveRequest, user: dict = Depends(require("manage_users"))):
    """管理员启用或停用用户。

    入参：username(str) 目标用户；req(ActiveRequest) 启用标志；user(dict) 当前管理员。
    出参：统一结构。
    失败行为：用户不存在返回 fail。
    """
    # 安全审查注释：禁止停用自己，避免管理员把自己锁在门外导致无人可管。
    if username == user["username"]:  # 目标是自己
        return fail("BAD_REQUEST", "不能停用当前登录的管理员账号")  # 拒绝
    r = set_active(username, req.active)  # 改状态
    if not r["ok"]:  # 失败
        return fail("BAD_REQUEST", r["reason"])  # 拒绝
    audit(user["username"], "set_active", f"用户 {username} 启用={req.active}")  # 记审计
    return ok({"username": username, "active": req.active})  # 返回


@router.post("/admin/pilot/lock")  # 锁定试点清单
def admin_lock_pilot(req: PilotLockRequest, user: dict = Depends(require("lock_pilot"))):
    """管理员锁定本批次试点岗位清单（清单为空则整批暂停，f05）。

    入参：req(PilotLockRequest) 岗位列表；user(dict) 当前管理员。
    出参：统一结构，data 为锁定后的清单。
    失败行为：空清单返回 fail（不允许用空清单误开全量）。
    """
    if not req.positions:  # 空清单
        return fail("BAD_REQUEST", "试点清单不能为空，空清单代表整批暂停")  # 拒绝
    cfg = load_config()  # 取配置（内存缓存）
    cfg["pilot"]["position_list"] = list(dict.fromkeys(req.positions))  # 去重后写入内存配置
    audit(user["username"], "lock_pilot", f"锁定试点清单：{cfg['pilot']['position_list']}")  # 记审计
    return ok({"position_list": cfg["pilot"]["position_list"]})  # 返回


@router.get("/admin/audit")  # 查审计
def admin_audit(user: dict = Depends(require("view_audit"))):
    """管理员查看审计日志。

    入参：user(dict) 当前管理员。
    出参：统一结构，data 为审计记录列表。
    失败行为：无 view_audit 权限由依赖拒绝。
    """
    return ok(list_audit())  # 返回


@router.post("/knowledge/search")  # 知识库检索
def knowledge_search(req: SearchRequest, user: dict = Depends(require("read"))):
    """知识库检索（RAG 检索部分），返回带来源的证据片段。

    入参：req(SearchRequest) 检索文本；user(dict) 当前用户。
    出参：统一结构，data 含 results 与数据声明。
    失败行为：未登录由依赖拒绝；无命中返回空列表（fail-closed）。
    """
    results = kb.search(req.query, req.top_k)  # 检索
    audit(user["username"], "kb_search", f"检索：{req.query[:40]}")  # 记审计
    return ok({"results": results, "notice": kb.evidence_notice()})  # 返回
