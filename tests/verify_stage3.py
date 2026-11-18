# SPDX-License-Identifier: MIT
"""阶段3 验证脚本：三能力编排、人工闸门、回归评测、HTTP 主链路。"""  # 脚本说明

import sys  # 系统路径
from pathlib import Path  # 路径处理

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 加入仓库根

from app.agents.harness import (  # Harness 各能力
    capability_scope, capability_check, capability_handover, run_pipeline, run_regression,
)
from app.human.gate import confirm_result, evaluate_human_review  # 人工闸门

passed = []  # 通过列表
failed = []  # 失败列表


def check(name, cond):
    """记录断言。入参 name(str) 名称；cond(bool) 结果；出参无；失败行为无。"""
    (passed if cond else failed).append(name)  # 归类
    print(("  PASS " if cond else "  FAIL ") + name)  # 打印


print("=== 阶段3 验证 ===")  # 标题

# —— 能力1 范围核对 ——
s_out = capability_scope("P", "POS-X")  # 未锁定清单
check("清单未锁定判超范围", s_out["in_scope"] is False)  # 断言
# 临时锁定清单做正向测试（直接改内存配置缓存，不影响文件）
from app.core.config import load_config  # 配置加载
cfg = load_config()  # 取配置
cfg["pilot"]["position_list"] = ["POS-A"]  # 锁定 POS-A
s_in = capability_scope("P", "POS-A")  # 命中
check("命中清单通过", s_in["in_scope"] is True)  # 断言
s_other = capability_scope("P", "POS-B")  # 不在清单
check("清单外岗位被排除", s_other["in_scope"] is False)  # 断言
cfg["pilot"]["position_list"] = []  # 恢复为空，避免同进程状态漂移

# —— 回归评测（P1 零容忍）——
reg = run_regression()  # 跑回归
check("回归评测通过", reg["passed"] is True)  # 断言
check("P1 违规数为 0", reg["p1_violations"] == 0)  # 零容忍
check("覆盖 5 类固定样本", reg["total"] == 5)  # 样本数

# —— 人工闸门 ——
g1 = evaluate_human_review({"in_scope": True}, {"changes": [{"field": "技能", "status": "未确认"}]}, True, {"consistent": True, "reason": "ok"}, {"found": True})  # 未确认项
check("未确认项强制转人工", g1["required"] is True)  # 断言
g2 = evaluate_human_review({"in_scope": False}, None, False, {"consistent": False, "reason": "x"}, {"found": False})  # 全失败
check("全失败转人工且多原因", g2["required"] is True and len(g2["reasons"]) >= 4)  # 断言
check("一线不能正式确认", confirm_result("frontline", "confirm", g1)["allowed"] is False)  # 权限
check("业务负责人可确认", confirm_result("business_owner", "confirm", g1)["allowed"] is True)  # 权限
check("未知动作拒绝", confirm_result("business_owner", "xxx", g1)["allowed"] is False)  # 拒绝

# —— 主链路（能力2/3，含真实模型调用）——
demand = "需求单版本：demand-v2\n技能条件：夜班资格"  # 需求单文本
handover = "交接单版本：handover-v1\n技能条件：普通岗"  # 交接单文本（版本落后）
oral = "电话里把技能要求改成需要夜班资格，需求单未回写；临时加夜班班次未同步。"  # 口头变更
res = run_pipeline("PILOT-1105-01", "POS-A", demand, handover, oral, None)  # 跑完整链路（关联编号缺失）
check("主链路返回结构完整", all(k in res for k in ["scope", "check", "draft", "human_review", "evidence_ids"]))  # 断言
check("版本不一致被检出", res["check"]["version_result"]["consistent"] is False)  # 确定性规则
check("关联缺失被检出", res["check"]["link_result"]["found"] is False)  # 降级
check("链路转人工不出草稿", res["human_review"]["required"] is True and res["draft"] is None)  # 不默认通过

# —— HTTP 层（红线拦截）——
try:  # 尝试 HTTP 断言
    from fastapi.testclient import TestClient  # 测试客户端
    from app.main import app  # 应用实例
    client = TestClient(app)  # 创建客户端
    r = client.get("/harness/regression")  # 回归端点
    check("/harness/regression 200", r.status_code == 200 and r.json()["data"]["passed"] is True)  # 断言
    blocked = client.post("/v1/check", json={  # 触碰写回红线
        "role": "business_owner", "batch_id": "P", "position_code": "POS-A", "writeback": True,
    })
    check("写回请求被拒绝", blocked.status_code == 200 and blocked.json()["ok"] is False)  # 红线
except ImportError:  # httpx 未装
    print("  SKIP HTTP 断言（httpx 未安装）")  # 跳过

print(f"=== 结果：{len(passed)} 通过 / {len(failed)} 失败 ===")  # 汇总
if failed:  # 有失败
    sys.exit(1)  # 非零退出
