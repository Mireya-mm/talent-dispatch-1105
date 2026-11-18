# SPDX-License-Identifier: MIT
"""阶段1 验证脚本：配置加载、统一响应、权限/红线、健康检查、全局异常。"""  # 脚本说明

import sys  # 系统路径
from pathlib import Path  # 路径处理

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 把仓库根加入 import 路径

from app.core.config import load_config, get, ROOT  # 配置加载函数
from app.core.response import ok, fail, error_code  # 响应封装
from app.core.guard import check_permission, check_guardrails  # 权限与红线
from app.main import app  # FastAPI 实例

passed = []  # 通过的断言
failed = []  # 失败的断言


def check(name, cond):
    """记录一条断言结果。

    入参：name(str) 断言名；cond(bool) 断言结果。
    出参：无。
    失败行为：无（只记录到全局列表）。
    """
    (passed if cond else failed).append(name)  # 按结果归入通过/失败列表
    print(("  PASS " if cond else "  FAIL ") + name)  # 打印结果


print("=== 阶段1 验证 ===")  # 标题
cfg = load_config()  # 加载配置
check("config.yaml 位于仓库根", (ROOT / "config.yaml").exists())  # 配置文件存在
check("配置含 ollama 段", "ollama" in cfg)  # 段存在
check("模型名为项目专用", get("ollama", "model") == "fsg-assign-check:0.8b")  # 模型名正确
check("think 关闭", get("ollama", "think") is False)  # 思考必须关

r_ok = ok({"x": 1})  # 成功响应
check("ok 结构正确", r_ok == {"ok": True, "data": {"x": 1}, "error": None})  # 结构断言
r_fail = fail("FORBIDDEN", "无权限")  # 失败响应
check("fail 结构正确", r_fail["ok"] is False and r_fail["error"]["code"] == "E_PERM_DENIED")  # 结构断言
check("错误码映射", error_code("MODEL_UNAVAILABLE") == "E_MODEL_DOWN")  # 码映射

check("一线可读", check_permission("frontline", "read")["allowed"] is True)  # 权限正向
check("一线不能确认版本", check_permission("frontline", "confirm_version")["allowed"] is False)  # 权限反向
check("业务负责人可确认", check_permission("business_owner", "confirm_version")["allowed"] is True)  # 权限正向
check("质量侧可叫停", check_permission("quality_review", "halt")["allowed"] is True)  # 权限正向
check("未知角色拒绝", check_permission("hacker", "read")["allowed"] is False)  # fail-closed

check("写回被拦", check_guardrails({"writeback": True})["ok"] is False)  # 红线拦截
check("只读请求放行", check_guardrails({"read": True})["ok"] is True)  # 正常放行
check("模型审批被拦", check_guardrails({"model_approval": True})["ok"] is False)  # 红线拦截

# 用 FastAPI 内置 TestClient 测路由；若 httpx 未装则跳过 HTTP 断言，不误报为失败
try:  # 尝试导入测试客户端
    from fastapi.testclient import TestClient  # FastAPI 测试客户端
    client = TestClient(app)  # 创建客户端
    h = client.get("/health")  # 请求健康检查
    check("/health 返回 200", h.status_code == 200)  # 状态码
    check("/health ok=true", h.json()["ok"] is True)  # 统一结构
    m = client.get("/models")  # 请求模型信息
    check("/models 返回 200", m.status_code == 200)  # 状态码
    check("/models think=false", m.json()["data"]["think"] is False)  # 思考关闭
except ImportError:  # 缺少 httpx
    print("  SKIP HTTP 断言（httpx 未安装，纯函数断言已覆盖）")  # 跳过说明

print(f"=== 结果：{len(passed)} 通过 / {len(failed)} 失败 ===")  # 汇总
if failed:  # 有失败
    sys.exit(1)  # 非零退出，便于 CI/命令行识别
