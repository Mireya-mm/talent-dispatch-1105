# SPDX-License-Identifier: MIT
"""端到端演示：锁定试点清单后，展示一次完整核对的产出。

用法：先起服务与 Ollama，再 python3 scripts/demo_e2e.py
说明：本脚本只演示只读核对流程，不写回任何单据、不向真人发安排。
"""  # 脚本说明

import sys  # 系统路径
from pathlib import Path  # 路径处理

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 加入仓库根

from app.core.config import load_config  # 配置加载
from app.agents.harness import run_pipeline  # Harness 主链路
from app.core.schema import validate_model_output  # 输出校验

cfg = load_config()  # 取配置
cfg["pilot"]["position_list"] = ["POS-A", "POS-B"]  # 模拟业务负责人锁定试点清单（仅内存，不写文件）

demand = "需求单版本：demand-v2\n技能条件：普通岗\n班次：白班"  # 需求单（旧口径）
handover = "交接单版本：handover-v1\n技能条件：普通岗\n班次：白班"  # 交接单（旧版本）
oral = "电话里把技能要求改成需要夜班资格，需求单未回写；临时加夜班，已确认的白班班次没同步。"  # 口头变更原文

result = run_pipeline(  # 跑完整链路
    "PILOT-1105-01",  # 批次
    "POS-A",  # 岗位
    demand,  # 需求单
    handover,  # 交接单
    oral,  # 口头变更
    "LK-1001",  # 关联编号（命中）
)

print("=== 一、范围核对 ===")  # 输出范围
print("  是否在试点范围：", result["scope"]["in_scope"], "|", result["scope"]["reason"])  # 范围结论

print("=== 二、模型抽取的口头变更（草稿，非结论）===")  # 输出模型草稿
md = result["check"]["model_data"]  # 取模型输出
print("  模型调用说明：", result["check"]["model_reason"])  # 调用状态
if md:  # 有输出
    for ch in md.get("changes", []):  # 逐条变更
        print("  - 字段:", ch.get("field"), "| 新值:", ch.get("new_value"), "| 状态:", ch.get("status"), "| 来源:", ch.get("source_ref"))  # 变更明细
    if not result["check"]["schema_valid"]:  # schema 未过
        print("  （0.8B 偶发缺字段/格式不稳，输出按脏数据转人工，不进正式结论）")  # 降级说明
else:  # 无输出
    print("  （模型输出为空，已转人工）")  # 降级提示

print("=== 三、确定性规则复核（版本结论不交给模型）===")  # 输出规则结果
vr = result["check"]["version_result"]  # 版本结论
print("  版本是否一致：", vr["consistent"], "|", vr["reason"])  # 版本结论
print("  关联编号命中：", result["check"]["link_result"]["found"])  # 关联结论
print("  模型输出合规：", result["check"]["schema_valid"])  # schema 结论

print("=== 四、人工闸门 ===")  # 输出人工判定
hr = result["human_review"]  # 人工复核
print("  是否转人工：", hr["required"])  # 判定
for r in hr["reasons"][:6]:  # 前六条原因
    print("   ·", r)  # 原因明细
print("  可对外草稿：", result["draft"])  # 草稿（应为 None）

print("=== 五、结论 ===")  # 总结
print("  本次核对把电话变更抽出成草稿并检出版本不一致；因存在未确认项，")  # 说明
print("  系统不自动生成交接、不写回需求单，而是转人工由业务负责人确认。")  # 边界
print("  证据编号：", ",".join(result["evidence_ids"]))  # 证据
