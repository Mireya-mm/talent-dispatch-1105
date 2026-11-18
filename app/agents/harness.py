# SPDX-License-Identifier: MIT
"""Harness：三能力编排 + 固定样本回归评测（标准库实现，不装第三方框架）。

三能力是同一 pipeline 上的纯函数，共用一次模型调用（只在"资料与版本核对"用模型）：
  能力1 场景范围核对 —— 确定性规则，不调模型
  能力2 资料与版本核对 —— 一次模型调用 + 确定性规则复核
  能力3 交接草稿整理 —— 纯函数整理，不出可对外版本
评测层硬门槛：把"未确认"误判成"已确认"的次数必须为 0（P1 零容忍）。
"""  # 模块说明

from app.core.config import get  # 读取配置
from app.core.rules import compare_versions, has_unconfirmed  # 版本规则
from app.core.schema import validate_model_output  # 输出校验
from app.knowledge.graph import get_position_facts, resolve_by_link, in_pilot  # 知识库
from app.llm.ollama_client import call_model  # 唯一模型出口
from app.agents.prompts import SYSTEM_CONSTRAINT, user_prompt  # 提示词
from app.human.gate import evaluate_human_review  # 人工闸门


def capability_scope(batch_id, position_code):
    """能力1：场景范围核对（确定性，不调模型）。

    入参：batch_id(str) 批次；position_code(str) 岗位代号。
    出参：dict，in_scope/reason/position_facts。
    失败行为：试点清单未锁定或岗位缺事实均判 out-of-scope，转人工，不默认放行。
    """
    pilot = in_pilot(position_code)  # 查试点清单
    if not pilot["locked"]:  # 清单未锁定
        # 边界注释：f05 要求试点清单由业务负责人锁定，未锁定就整批暂停，
        # 绝不默认全量处理，否则会把范围外单据混进结果。
        return {"in_scope": False, "reason": pilot["reason"], "position_facts": None}  # 暂停
    if not pilot["in_scope"]:  # 不在清单
        return {"in_scope": False, "reason": pilot["reason"], "position_facts": None}  # 排除
    facts = get_position_facts(position_code)  # 查岗位事实
    if facts is None:  # 事实缺失
        return {"in_scope": False, "reason": "岗位事实缺失，转人工", "position_facts": None}  # 转人工
    return {"in_scope": True, "reason": "命中试点清单", "position_facts": facts}  # 通过


def capability_check(batch_id, position_code, demand_doc, handover_doc, oral_text, link_key):
    """能力2：资料与版本核对（一次模型调用 + 确定性复核）。

    入参：batch_id(str) 批次；position_code(str) 岗位；demand_doc/handover_doc/oral_text(str) 文本；
          link_key(str) 关联编号或 None。
    出参：dict，{"model_data": dict|None, "schema_valid": bool, "version_result": dict,
                 "link_result": dict, "model_reason": str}。
    失败行为：模型失败/输出脏/关联缺失都返回对应标记，由能力3与人工闸门转人工。
    """
    link_result = resolve_by_link(link_key)  # 关联编号解析（确定性）
    # 版本结论由确定性规则给，绝不交给模型（f30/f31）：
    # 需求单/交接单版本从单据文本解析，规则版本取岗位事实里的基准值。
    # 真实字段字典尚未核实，这里只用占位解析，不猜不拼。
    facts = get_position_facts(position_code)  # 取岗位事实（含规则版本基准）
    rule_version = facts["rule_version"] if facts else None  # 规则版本缺失则判不一致
    vr = compare_versions(  # 版本比较（确定性）
        _extract_version(demand_doc, "需求单版本"),  # 需求单版本
        _extract_version(handover_doc, "交接单版本"),  # 交接单版本
        rule_version,  # 规则版本基准
    )
    up = user_prompt(batch_id, position_code, demand_doc, handover_doc, oral_text, link_key)  # 构造提示词
    model = call_model(up, SYSTEM_CONSTRAINT)  # 唯一一次模型调用
    model_data = model["data"] if model["ok"] else None  # 取模型数据
    schema_valid = validate_model_output(model_data)["valid"] if model_data else False  # 校验
    # 人工确认注释：模型再智能也不给版本结论——版本一致性由上面的确定性规则判（f30/f31）。
    # 模型只负责把口头变更抽成要素，且输出必须过 schema，不过就是脏数据转人工。
    return {  # 返回核对结果
        "model_data": model_data,  # 模型草稿
        "schema_valid": schema_valid,  # schema 是否通过
        "version_result": vr,  # 确定性版本结论
        "link_result": link_result,  # 关联编号结论
        "model_reason": model["reason"],  # 模型调用说明
    }


def _extract_version(text, label):
    """从单据文本中提取形如「标签：值」的版本号（确定性解析，不调模型）。

    入参：text(str) 单据文本；label(str) 标签名。
    出参：str 或 None，提取到的版本号。
    失败行为：未找到返回 None，由版本规则判缺失，不猜不默认。
    """
    if not text:  # 空文本
        return None  # 缺失
    for line in text.splitlines():  # 逐行扫描
        if label in line and "：" in line:  # 命中标签且含中文冒号
            return line.split("：", 1)[1].strip()  # 取冒号后值
    return None  # 未找到


def capability_handover(check_result, scope_result):
    """能力3：交接草稿整理（纯函数，不出可对外版本）。

    入参：check_result(dict) 能力2结果；scope_result(dict) 能力1结果。
    出参：dict，{"draft": dict|None, "human_review": dict}。
    失败行为：范围外、模型脏、版本不一致、关联缺失任一触发都进人工队列，draft=None。
    """
    model_data = check_result["model_data"]  # 取模型草稿
    vr = check_result["version_result"]  # 版本结论
    lr = check_result["link_result"]  # 关联结论
    scope_ok = scope_result["in_scope"]  # 范围是否通过
    # 范围外直接转人工，不整理草稿
    if not scope_ok:  # 范围外
        return {"draft": None, "human_review": {"required": True, "reasons": [scope_result["reason"]], "queue": "转人工"}}  # 转人工
    review = evaluate_human_review(  # 人工闸门判定
        {"in_scope": scope_ok},  # 范围
        model_data,  # 模型输出
        check_result["schema_valid"],  # schema 结果
        vr,  # 版本结果
        lr,  # 关联结果
    )
    if review["required"]:  # 需人工
        # 人工确认注释：只要闸门拦下，就不产出可对外草稿（f44 不默认通过），
        # 只给人工队列原因，让人补证据或确认版本后再走。
        return {"draft": None, "human_review": review}  # 转人工
    return {"draft": model_data.get("handover_draft"), "human_review": review}  # 通过才给草稿


def run_pipeline(batch_id, position_code, demand_doc, handover_doc, oral_text, link_key):
    """编排三能力跑一次完整核对（主链路入口）。

    入参：同 capability_check，外加批次与岗位。
    出参：dict，统一业务结果：scope/check/draft/human_review/evidence_ids。
    失败行为：任何阶段异常被全局异常处理器兜住；本函数只返回结构化结果，不抛业务异常。
    """
    scope = capability_scope(batch_id, position_code)  # 能力1
    check = capability_check(batch_id, position_code, demand_doc, handover_doc, oral_text, link_key)  # 能力2
    handover = capability_handover(check, scope)  # 能力3
    # 版本结论来自确定性规则（check["version_result"]），不取模型输出，
    # 即便模型多吐了 version_check 也被这里覆盖——红线：版本结论绝不由模型给。
    return {  # 汇总
        "batch_id": batch_id,  # 批次
        "scope": {"in_scope": scope["in_scope"], "reason": scope["reason"]},  # 范围结论
        "version_check": check["version_result"],  # 版本结论（规则来源，覆盖模型）
        "link_check": check["link_result"],  # 关联编号结论（规则来源）
        "check": check,  # 核对细节（含模型草稿）
        "draft": handover["draft"],  # 草稿（可能 None）
        "human_review": handover["human_review"],  # 人工判定
        "evidence_ids": ["f10", "f11", "f13", "f30", "f42", "f50"],  # 关联证据编号
    }


# ——— 评测层：固定样本回归 ———

# 固定样本：覆盖已确认新版本、电话改未回写、临时加夜班未同步、关联编号缺失、来源缺失五类。
REGRESSION_CASES = [  # 样本常量
    {"id": "confirmed_new_version", "expect_human": False, "status": "已确认", "source_ref": "需求单/技能条件"},  # 已确认
    {"id": "oral_change_not_written", "expect_human": True, "status": "未确认", "source_ref": "电话记录/技能条件"},  # 未回写
    {"id": "night_shift_not_synced", "expect_human": True, "status": "未确认", "source_ref": "群消息/班次"},  # 夜班未同步
    {"id": "link_key_missing", "expect_human": True, "status": "未确认", "source_ref": "需求单/关联编号"},  # 关联缺失
    {"id": "source_missing", "expect_human": True, "status": "未确认", "source_ref": None},  # 来源缺失
]


def run_regression():
    """跑固定样本回归评测，校验硬门槛（P1 零误判）。

    入参：无（样本来自 REGRESSION_CASES 常量）。
    出参：dict，{"passed": bool, "total": int, "p1_violations": int, "details": list}。
    失败行为：任一"未确认"被判为可放行（expect_human=True 却 required=False）计为 P1 违规；
             p1_violations>0 即 passed=False，禁止进入下一阶段。
    """
    details = []  # 明细
    p1 = 0  # P1 违规计数
    for case in REGRESSION_CASES:  # 遍历样本
        model_data = {"changes": [{"field": "技能条件", "status": case["status"], "source_ref": case["source_ref"]}]}  # 构造样本输出
        schema_valid = validate_model_output(model_data)["valid"]  # schema 校验
        link_result = {"found": case["id"] != "link_key_missing"}  # 关联结果
        vr = {"consistent": case["id"] == "confirmed_new_version", "reason": "样本"}  # 版本结果
        review = evaluate_human_review({"in_scope": True}, model_data, schema_valid, vr, link_result)  # 人工判定
        human_required = review["required"]  # 是否需人工
        # P1 注释：把"未确认/未识别/缺失"误判成可自动放行是零容忍错误，
        # 与 f31/f44 对应，出现一次就判定评测失败，必须修规则/提示词后重跑。
        is_p1 = (case["expect_human"] and not human_required)  # 是否 P1 违规
        if is_p1:  # 违规
            p1 += 1  # 计数
        details.append({"id": case["id"], "expect_human": case["expect_human"], "human_required": human_required, "p1": is_p1})  # 明细
    passed = p1 == 0  # 零容忍
    return {"passed": passed, "total": len(REGRESSION_CASES), "p1_violations": p1, "details": details}  # 返回评测结果
