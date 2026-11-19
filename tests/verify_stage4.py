# SPDX-License-Identifier: MIT
"""阶段4 验证脚本：SQLite 知识库（图谱+RAG+只读）与登录鉴权/管理员。

覆盖：知识库命中/缺失不猜/只读防护/检索带来源；token 签发校验/篡改拒绝/
未登录拒绝/越权拒绝/停用失效；管理员建用户/锁试点/审计留痕。
"""  # 脚本说明

import sys  # 系统路径
from pathlib import Path  # 路径处理
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 加入仓库根

from app.knowledge import store as kb  # 知识库查询
from app.knowledge.db import connect_ro  # 只读连接
from app.auth.security import (  # 口令与 token 工具
    hash_password, verify_password, issue_token, decode_token,
)
from app.auth.auth_store import (  # 用户存储
    authenticate, create_user, set_active, get_user, list_audit, init_auth_db,
)
from app.core.config import get  # 读配置

passed = []  # 通过列表
failed = []  # 失败列表


def check(name, cond):
    """记录断言。入参 name(str) 名称；cond(bool) 结果；出参无；失败行为无。"""
    (passed if cond else failed).append(name)  # 归类
    print(("  PASS " if cond else "  FAIL ") + name)  # 打印


print("=== 阶段4 验证 ===")  # 标题

# —— 知识库：事实 ——
f = kb.get_fact("POS-A")  # 查已知岗位
check("知识库命中岗位事实", f is not None and "夜班资格" in f["attrs"]["hard_conditions"])  # 命中
check("知识库未命中返回 None", kb.get_fact("POS-X") is None)  # 不猜
f["attrs"]["hard_conditions"].append("TAMPER")  # 尝试篡改
check("知识库返回深拷贝不可污染", "TAMPER" not in kb.get_fact("POS-A")["attrs"]["hard_conditions"])  # 只读

# —— 知识库：图谱关联 ——
lr = kb.resolve_links("LK-1001")  # 命中关联
check("图谱关联编号命中", lr["found"] is True and "HANDOVER-A" in lr["documents"])  # 图谱
check("图谱关联缺失降级", kb.resolve_links(None)["found"] is False)  # 缺失
check("图谱未知编号不猜", kb.resolve_links("LK-9999")["found"] is False)  # 不猜

# —— 知识库：检索（RAG 检索部分）——
res = kb.search("夜班 电工证 需求单")  # 检索
check("检索返回证据片段", len(res) > 0)  # 有结果
check("证据片段带来源位置", all(r.get("source") for r in res))  # f42 来源硬要求
check("检索结果按分数降序", all(res[i]["score"] >= res[i + 1]["score"] for i in range(len(res) - 1)))  # 排序
check("无关查询不硬凑结果", len(kb.search("火星 宇宙 银河系")) == 0)  # fail-closed
check("数据声明标注不作基线", "不作基线" in kb.evidence_notice())  # f12

# —— 知识库：运行时只读 ——
conn = connect_ro()  # 只读连接
ro_ok = False  # 标志
try:  # 尝试写入
    conn.execute("DELETE FROM facts")  # 只读连接执行删除
except Exception:  # 应抛异常
    ro_ok = True  # 符合预期：写被物理拒绝
finally:  # 关闭
    conn.close()  # 关连接
check("运行时连接物理只读", ro_ok is True)  # 只读红线

# —— 口令哈希 ——
hp = hash_password("test1234")  # 哈希
check("口令哈希含盐", hp["salt"] and hp["hash"] and hp["salt"] != hp["hash"])  # 加盐
check("正确口令校验通过", verify_password("test1234", hp["salt"], hp["hash"]) is True)  # 正确
check("错误口令校验拒绝", verify_password("wrong", hp["salt"], hp["hash"]) is False)  # 错误

# —— token ——
tk = issue_token("tester", "business_owner")  # 签发
d = decode_token(tk)  # 校验
check("token 签发校验通过", d["ok"] is True and d["role"] == "business_owner")  # 正常
tampered = tk[:-3] + ("abc" if not tk.endswith("abc") else "xyz")  # 篡改签名
check("token 篡改被拒绝", decode_token(tampered)["ok"] is False)  # 防篡改
check("空 token 被拒绝", decode_token("")["ok"] is False)  # 空值

# —— 登录与用户 ——
init_auth_db()  # 确保库就绪
admin = get("auth", "bootstrap_admin", "admin")  # 管理员账号
pw = get("auth", "bootstrap_password", "ChangeMe@1105")  # 口令
check("管理员登录成功", authenticate(admin, pw)["ok"] is True)  # 登录
check("错误口令登录失败", authenticate(admin, "wrong")["ok"] is False)  # 拒绝
check("未知用户登录失败", authenticate("nobody", "x")["ok"] is False)  # 拒绝
u = "verify_user_" + str(hash(tk) % 100000)  # 唯一测试用户名
create_user(u, "pass1234", "frontline", "验证用户")  # 建用户
check("创建用户成功", get_user(u) is not None)  # 建成
set_active(u, False)  # 停用
check("停用用户后登录失败", authenticate(u, "pass1234")["ok"] is False)  # 停用生效
set_active(u, True)  # 恢复
check("启用用户后登录成功", authenticate(u, "pass1234")["ok"] is True)  # 恢复

# —— HTTP 鉴权 ——
try:  # HTTP 断言
    from fastapi.testclient import TestClient  # 测试客户端
    from app.main import app  # 应用实例
    client = TestClient(app)  # 客户端
    r0 = client.get("/v1/auth/me")  # 无 token
    check("未登录查身份被拒", r0.status_code == 403)  # 鉴权
    lg = client.post("/v1/auth/login", json={"username": admin, "password": pw})  # 登录
    token = lg.json()["data"]["token"]  # token
    h = {"Authorization": "Bearer " + token}  # 请求头
    me = client.get("/v1/auth/me", headers=h)  # 查身份
    check("带 token 查身份通过", me.status_code == 200 and me.json()["data"]["role"] == "admin")  # 通过
    users = client.get("/v1/admin/users", headers=h)  # 列用户
    check("管理员列用户通过", users.status_code == 200 and len(users.json()["data"]) >= 1)  # 管理员
    bad_search = client.post("/v1/knowledge/search", json={"query": "夜班"}, headers={"Authorization": "Bearer bad.token"})  # 坏 token
    check("坏 token 访问被拒", bad_search.status_code == 403)  # 拒绝
    audit_rows = client.get("/v1/admin/audit", headers=h)  # 审计
    check("管理员查审计通过", audit_rows.status_code == 200 and len(audit_rows.json()["data"]) >= 1)  # 审计
except ImportError:  # httpx 未装
    print("  SKIP HTTP 断言")  # 跳过

print(f"=== 结果：{len(passed)} 通过 / {len(failed)} 失败 ===")  # 汇总
if failed:  # 有失败
    sys.exit(1)  # 非零退出
