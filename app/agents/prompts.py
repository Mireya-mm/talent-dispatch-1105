# SPDX-License-Identifier: MIT
"""提示词加载：三能力共用一份系统约束，来自 docs/提示词.md 设计稿。"""  # 模块说明

from app.core.config import get  # 读取配置（提示词版本）

SYSTEM_CONSTRAINT = """你是「派遣岗位需求与到岗交接」业务核对助手，只处理本批次脱敏只读资料。
硬性约束：
1. 只读，不得写回任何单据、不得发送外部消息、不得调用执行接口。
2. 只输出草稿，正式确认由业务负责人完成，你没有审批权。
3. 不得编造：没有的字段标「缺失」，读不出来标「未识别」，没人确认标「未确认」，三类分开。
4. 每条结论附「来源位置」和「确认状态」，给不出就不输出。
5. 不得覆盖原值、不得省掉人工确认、不得把未确认项算到接收方。
6. 不得自动决定录用或派遣资格、不得向真实人员发安排。
7. 不得把「80单/22%」等演练样本当真实基线。
8. 时间只用业务发生时间与系统接收时间，回填时间不是发生时间。
9. 拿不准输出「转人工」并说明原因，禁止静默降级为通过。
10. 只给一页缺项清单和来源位置，不写长摘要。
输出必须是 JSON，字段：batch_id, scope, changes, missing_items, handover_draft,
human_review。changes 每项含 field/old_value/new_value/source_ref/
occurred_at/received_at/status。不要输出 version_check——版本结论由确定性规则给，
不由你判断。不得输出 JSON 之外的文字。"""  # 系统约束，版本结论明确排除，红线自洽


def user_prompt(batch_id, position_code, demand_doc, handover_doc, oral_text, link_key):
    """构造用户提示词：把脱敏单据与口头变更原文交给模型抽取。

    入参：batch_id(str) 批次；position_code(str) 岗位代号；demand_doc(str) 需求单文本；
          handover_doc(str) 交接单文本；oral_text(str) 电话/群消息转写；link_key(str) 关联编号。
    出参：str 用户提示词。
    失败行为：无（纯字符串拼接）；真实字段字典未核实前由调用方传占位文本。
    """
    p = get("harness", "prompt_version", "v0.1")  # 读提示词版本，便于追溯
    return f"""提示词版本：{p}
批次：{batch_id}
岗位代号：{position_code}
关联编号：{link_key or '缺失（不得拼接，转人工）'}
—— 脱敏需求单 ——
{demand_doc}
—— 脱敏交接单 ——
{handover_doc}
—— 电话/群消息转写 ——
{oral_text}
请只抽取「技能条件、班次、地点、岗位代号、截止时间」五类口头变更，
每条给出来源位置；比对三份版本，列缺项与未确认项；产出交接草稿。
版本结论由确定性规则复核，你只给草稿。"""  # 返回用户提示词
