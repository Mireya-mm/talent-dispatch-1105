# SPDX-License-Identifier: MIT
"""阶段2 验证脚本：知识库、版本规则、schema 校验、模型请求体构造。"""  # 脚本说明

import sys  # 系统路径
from pathlib import Path  # 路径处理

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 加入仓库根到 import 路径

from app.knowledge.graph import get_position_facts, resolve_by_link, in_pilot  # 知识库
from app.core.rules import compare_versions, has_unconfirmed  # 版本规则
from app.core.schema import validate_model_output  # schema 校验
from app.llm.ollama_client import build_payload  # 模型请求体构造

passed = []  # 通过列表
failed = []  # 失败列表


def check(name, cond):
    """记录断言结果。

    入参：name(str) 断言名；cond(bool) 结果。
    出参：无。
    失败行为：无。
    """
    (passed if cond else failed).append(name)  # 归类
    print(("  PASS " if cond else "  FAIL ") + name)  # 打印


print("=== 阶段2 验证 ===")  # 标题

# —— 知识库 ——
f = get_position_facts("POS-A")  # 查询已知岗位
check("命中岗位事实", f is not None and "夜班资格" in f["hard_conditions"])  # 命中断言
check("未命中返回 None", get_position_facts("POS-X") is None)  # 未命中不强猜
f["hard_conditions"].append("TAMPER")  # 尝试篡改返回副本
check("返回的是副本不可改事实表", "TAMPER" not in get_position_facts("POS-A")["hard_conditions"])  # 只读断言
check("关联编号命中", resolve_by_link("LK-1001")["found"] is True)  # 命中
check("关联编号缺失降级人工", resolve_by_link(None)["found"] is False)  # 缺失降级
check("未知关联编号降级", resolve_by_link("LK-9999")["found"] is False)  # 未知降级
check("试点未锁定则暂停", in_pilot("POS-A")["in_scope"] is False)  # 边界断言

# —— 版本规则 ——
v = compare_versions("v2", "v2", "v2")  # 一致场景
check("版本一致判定", v["consistent"] is True)  # 一致
v2 = compare_versions("v2", "v1", "v2")  # 不一致场景
check("版本不一致判定", v2["consistent"] is False and len(v2["fields"]) > 0)  # 不一致
v3 = compare_versions("v2", None, "v2")  # 缺失场景
check("版本缺失判定", v3["consistent"] is False and "handover_version" in v3["fields"])  # 缺失

# —— 未确认检测 ——
check("含未确认项被识别", has_unconfirmed([{"status": "未确认"}]) is True)  # 未确认
check("全部已确认放行核查", has_unconfirmed([{"status": "已确认"}]) is False)  # 已确认
check("非法状态按未确认处理", has_unconfirmed([{"status": "???"}]) is True)  # fail-closed

# —— schema 校验 ——
base = {  # 合规样本
    "batch_id": "PILOT-1105-01",  # 批次
    "scope": {"in_scope": True},  # 范围
    "changes": [{"status": "未确认", "source_ref": "需求单/字段"}],  # 变更带来源
    "version_check": {},  # 版本检查
    "missing_items": [],  # 缺项
    "handover_draft": {"ready": False},  # 草稿未就绪
    "human_review": {"required": True},  # 需人工
}
check("合规输出通过", validate_model_output(base)["valid"] is True)  # 合规
bad1 = dict(base)  # 复制
bad1["changes"] = [{"status": "已确认"}]  # 缺来源
check("缺来源被拦", validate_model_output(bad1)["valid"] is False)  # 来源硬要求
bad2 = dict(base)  # 复制
bad2["handover_draft"] = {"ready": True, "latest_confirmed_version": None, "unconfirmed_items": ["夜班"]}  # ready 但条件不足
check("ready=true 条件不足被拦", validate_model_output(bad2)["valid"] is False)  # 就绪闸门
bad3 = dict(base)  # 复制
del bad3["human_review"]  # 删必填字段
check("缺必填字段被拦", validate_model_output(bad3)["valid"] is False)  # 必填断言

# —— 模型请求体 ——
p = build_payload("测试输入", "系统约束")  # 构造请求体
check("请求体 think=false", p["think"] is False)  # 关键参数
check("请求体 format=json", p["format"] == "json")  # 结构化
check("请求体含 system 消息", len(p["messages"]) == 2 and p["messages"][0]["role"] == "system")  # 系统消息

print(f"=== 结果：{len(passed)} 通过 / {len(failed)} 失败 ===")  # 汇总
if failed:  # 有失败
    sys.exit(1)  # 非零退出
