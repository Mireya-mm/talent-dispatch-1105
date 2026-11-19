# SPDX-License-Identifier: MIT
"""用户与审计存储：独立 SQLite 库，与知识库分离。

users 表存口令哈希与角色；audit 表留登录/授权/管理动作痕迹。
本模块同时提供离线初始化（建表 + 引导管理员）和运行时查询。
运行时不提供「改业务数据」接口，只管账号与审计。
"""  # 模块说明

import sqlite3  # 标准库 SQLite
import time  # 时间戳
from datetime import datetime  # 时间格式化
from pathlib import Path  # 路径处理
from app.core.config import ROOT, get  # 读配置与仓库根
from app.auth.security import hash_password, verify_password  # 口令工具


def _path():
    """解析鉴权库路径。

    入参：无。
    出参：Path 绝对路径。
    失败行为：无（纯路径拼接）。
    """
    rel = get("auth", "db_path", "data/auth.db")  # 读配置路径
    p = Path(rel)  # 路径对象
    return p if p.is_absolute() else ROOT / p  # 相对拼仓库根


def _connect():
    """建立鉴权库连接（行按列名访问）。

    入参：无。
    出参：sqlite3.Connection。
    失败行为：文件不存在时建空库，由调用方决定是否需要初始化。
    """
    p = _path()  # 取路径
    p.parent.mkdir(parents=True, exist_ok=True)  # 建父目录
    conn = sqlite3.connect(str(p))  # 连接（不存在则建）
    conn.row_factory = sqlite3.Row  # 按列名访问
    return conn  # 返回连接


def init_auth_db():
    """初始化鉴权库：建表 + 创建引导管理员（幂等）。

    入参：无。
    出参：dict，{"created_admin": bool}。
    失败行为：异常直接抛出，退出非零。
    """
    conn = _connect()  # 连接
    try:  # 建表与引导
        cur = conn.cursor()  # 游标
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt TEXT NOT NULL,
            pwd_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            display_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )""")  # 用户表
        cur.execute("""CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT NOT NULL
        )""")  # 审计表
        admin = get("auth", "bootstrap_admin", "admin")  # 引导管理员账号
        exists = cur.execute("SELECT 1 FROM users WHERE username=?", (admin,)).fetchone()  # 是否已存在
        created = False  # 是否新建
        if not exists:  # 不存在则创建
            hp = hash_password(get("auth", "bootstrap_password", "ChangeMe@1105"))  # 哈希口令
            cur.execute(  # 插入管理员
                "INSERT INTO users(username,salt,pwd_hash,role,display_name,active,created_at) VALUES(?,?,?,?,?,?,?)",  # SQL
                (admin, hp["salt"], hp["hash"], "admin", "系统管理员", 1, _now()),  # 参数
            )  # 插入结束
            created = True  # 标记已建
        conn.commit()  # 提交
        return {"created_admin": created}  # 返回结果
    finally:  # 无论成功失败
        conn.close()  # 关闭


def _now():
    """当前时间字符串（审计用）。

    入参：无。
    出参：str ISO 风格时间。
    失败行为：无。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 格式化当前时间


def authenticate(username, password):
    """登录认证：查用户 → 校验口令 → 返回角色。

    入参：username(str) 用户名；password(str) 明文口令。
    出参：dict，{"ok":bool,"role":str|None,"reason":str}。
    失败行为：用户不存在/停用/口令错一律 ok=False 且原因统一，不暴露账号是否存在。
    """
    conn = _connect()  # 连接
    try:  # 查询校验
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()  # 查用户
        # 安全审查注释：失败原因统一为「用户名或口令错误」，不区分账号是否存在，
        # 防止枚举攻击；停用账号也按失败处理，不给任何可用身份。
        if row is None or not row["active"]:  # 不存在或停用
            return {"ok": False, "role": None, "reason": "用户名或口令错误"}  # 统一失败
        if not verify_password(password, row["salt"], row["pwd_hash"]):  # 口令错
            return {"ok": False, "role": None, "reason": "用户名或口令错误"}  # 统一失败
        return {"ok": True, "role": row["role"], "reason": "ok"}  # 通过
    finally:  # 无论成功失败
        conn.close()  # 关闭


def get_user(username):
    """查询用户记录（不含口令哈希外泄）。

    入参：username(str) 用户名。
    出参：dict 或 None，含 username/role/display_name/active。
    失败行为：未命中返回 None。
    """
    conn = _connect()  # 连接
    try:  # 查询
        row = conn.execute(  # 只取安全字段
            "SELECT username,role,display_name,active,created_at FROM users WHERE username=?", (username,)
        ).fetchone()  # 查用户
        return dict(row) if row else None  # 转字典或 None
    finally:  # 无论成功失败
        conn.close()  # 关闭


def list_users():
    """列出全部用户（安全字段）。

    入参：无。
    出参：list[dict]。
    失败行为：空库返回空列表。
    """
    conn = _connect()  # 连接
    try:  # 查询
        rows = conn.execute(  # 只取安全字段
            "SELECT username,role,display_name,active,created_at FROM users ORDER BY created_at"
        ).fetchall()  # 全部用户
        return [dict(r) for r in rows]  # 转字典列表
    finally:  # 无论成功失败
        conn.close()  # 关闭


def create_user(username, password, role, display_name):
    """创建用户（管理员动作）。

    入参：username(str) 用户名；password(str) 口令；role(str) 角色；display_name(str) 显示名。
    出参：dict，{"ok":bool,"reason":str}。
    失败行为：用户名已存在返回 ok=False；角色非法由路由层先校验。
    """
    conn = _connect()  # 连接
    try:  # 插入
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():  # 已存在
            return {"ok": False, "reason": "用户名已存在"}  # 拒绝
        hp = hash_password(password)  # 哈希口令
        conn.execute(  # 插入用户
            "INSERT INTO users(username,salt,pwd_hash,role,display_name,active,created_at) VALUES(?,?,?,?,?,?,?)",  # SQL
            (username, hp["salt"], hp["hash"], role, display_name, 1, _now()),  # 参数
        )  # 插入结束
        conn.commit()  # 提交
        return {"ok": True, "reason": "已创建"}  # 成功
    finally:  # 无论成功失败
        conn.close()  # 关闭


def set_active(username, active):
    """启用/停用用户（管理员动作）。

    入参：username(str) 用户名；active(bool) 是否启用。
    出参：dict，{"ok":bool,"reason":str}。
    失败行为：用户不存在返回 ok=False。
    """
    conn = _connect()  # 连接
    try:  # 更新
        cur = conn.execute(  # 改启用状态
            "UPDATE users SET active=? WHERE username=?", (1 if active else 0, username)
        )  # 更新语句
        conn.commit()  # 提交
        if cur.rowcount == 0:  # 无匹配
            return {"ok": False, "reason": "用户不存在"}  # 拒绝
        return {"ok": True, "reason": "已更新"}  # 成功
    finally:  # 无论成功失败
        conn.close()  # 关闭


def audit(actor, action, detail):
    """写审计日志（追加，不覆盖）。

    入参：actor(str) 操作者；action(str) 动作；detail(str) 详情。
    出参：无。
    失败行为：异常由全局兜底，不影响主流程响应（审计写失败不吞主结果）。
    """
    conn = _connect()  # 连接
    try:  # 追加
        conn.execute(  # 插入审计
            "INSERT INTO audit(ts,actor,action,detail) VALUES(?,?,?,?)",  # SQL
            (_now(), actor, action, detail),  # 参数
        )  # 插入结束
        conn.commit()  # 提交
    finally:  # 无论成功失败
        conn.close()  # 关闭


def list_audit(limit=50):
    """查看审计日志（管理员动作）。

    入参：limit(int) 返回条数。
    出参：list[dict]。
    失败行为：空表返回空列表。
    """
    conn = _connect()  # 连接
    try:  # 查询
        rows = conn.execute(  # 按时间倒序
            "SELECT ts,actor,action,detail FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()  # 审计记录
        return [dict(r) for r in rows]  # 转字典列表
    finally:  # 无论成功失败
        conn.close()  # 关闭
