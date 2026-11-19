# SPDX-License-Identifier: MIT
"""路由定义：/health、/models、POST /v1/check 核对主链路。"""  # 模块说明

from fastapi import APIRouter, Depends  # API 路由器与依赖
from pydantic import BaseModel  # 请求体模型
from typing import Optional  # 可选类型
from app.core.config import get  # 读取配置
from app.core.response import ok  # 统一成功结构
from app.core.guard import check_guardrails  # 红线校验
from app.agents.harness import run_pipeline, run_regression  # Harness 编排与评测
from app.auth.deps import require  # 权限依赖
from app.auth.auth_store import audit  # 审计留痕
from app.llm.ollama_client import probe_model  # 模型在线探测
from app.knowledge import store as kb  # 知识库只读统计
from app.knowledge.graph import get_position_facts  # 岗位事实（只读）

router = APIRouter()  # 创建路由器实例


class CheckRequest(BaseModel):  # 核对请求体 schema
    batch_id: str  # 批次号
    position_code: str  # 岗位代号
    demand_doc: str = ""  # 脱敏需求单文本
    handover_doc: str = ""  # 脱敏交接单文本
    oral_text: str = ""  # 电话/群消息转写
    link_key: Optional[str] = None  # 关联编号，可缺失
    writeback: bool = False  # 是否请求写回（红线，默认 False）
    auto_decide: bool = False  # 是否请求自动决策（红线，默认 False）
    send_to_real_person: bool = False  # 是否请求向真人发安排（红线）


@router.get("/health")  # 健康检查端点
def health():
    """健康检查：确认服务存活与配置加载。

    入参：无。
    出参：统一成功结构，data 含 app 名、版本、环境、红线摘要。
    失败行为：配置未加载时由 lifespan/依赖触发异常，被全局异常处理器兜住。
    """
    return ok({  # 返回运行状态
        "app": get("app", "name"),  # 应用名
        "version": get("app", "version"),  # 版本
        "env": get("app", "env"),  # 环境标识
        "read_only": get("guardrails", "read_only"),  # 只读标志
    })


@router.get("/models")  # 模型信息端点
def models():
    """模型信息：展示配置的模型名，不探测外部、不暴露地址细节。

    入参：无。
    出参：统一成功结构，data 含专用模型名与基座模型名。
    失败行为：无（只读配置）。
    """
    return ok({  # 返回模型信息
        "model": get("ollama", "model"),  # 项目专用模型
        "base_model": get("ollama", "base_model"),  # 基座模型
        "think": get("ollama", "think"),  # 思考开关（应为 false）
    })


@router.get("/v1/system/status")  # 工作台系统状态
def system_status(user: dict = Depends(require("read"))):
    """返回工作台所需的真实系统状态：模型在线、试点锁定、知识库统计。

    入参：user(dict) 当前登录用户（需 read 权限）。
    出参：统一结构，data 含 model/pilot/knowledge 三组真实状态。
    失败行为：知识库统计失败降级为 0，不影响其余状态返回；模型探测内部已兜底。
    """
    pilot_list = get("pilot", "position_list") or []  # 读当前试点清单（内存态，管理员可锁）
    return ok({  # 返回真实状态
        "model": probe_model(),  # 模型在线探测（真实请求本地服务）
        "pilot": {  # 试点范围状态
            "locked": bool(pilot_list),  # 清单非空即已锁定
            "positions": pilot_list,  # 当前清单
            "batch_id": get("pilot", "batch_id"),  # 批次号
        },  # 试点结束
        "knowledge": {  # 知识库统计（真实查询）
            "notice": kb.evidence_notice(),  # 数据声明
            "sample_hint": "试试搜索：夜班资格、电工证、版本、交接、关联编号",  # 检索提示
        },  # 知识库结束
        "current_user": {"username": user["username"], "role": user["role"]},  # 当前身份
    })  # 返回


@router.get("/v1/positions")  # 岗位事实列表
def positions(user: dict = Depends(require("read"))):
    """列出知识库中全部岗位的只读事实，供工作台表单加载真实岗位。

    入参：user(dict) 当前登录用户（需 read 权限）。
    出参：统一结构，data 为岗位事实列表（含硬条件/规则版本/关联编号/来源）。
    失败行为：知识库为空返回空列表；不猜不拼，只读已存在的事实。
    """
    conn = kb.connect_ro()  # 只读连接
    try:  # 查全部岗位 id
        ids = [r["id"] for r in conn.execute("SELECT id FROM facts WHERE type='岗位'").fetchall()]  # 岗位编号
    finally:  # 关闭连接
        conn.close()  # 释放只读连接
    items = []  # 结果列表
    for pid in ids:  # 逐岗位取事实
        f = get_position_facts(pid)  # 只读事实
        if f:  # 命中
            items.append({"position_code": pid, **f})  # 加入列表
    return ok(items)  # 返回真实岗位列表


@router.get("/harness/regression")  # 回归评测端点
def regression():
    """跑固定样本回归评测，返回 P1 零容忍结果。

    入参：无。
    出参：统一成功结构，data 为评测报告。
    失败行为：评测内部异常被全局异常处理器兜住。
    """
    return ok(run_regression())  # 返回评测报告


@router.post("/v1/check")  # 核对主链路
def check(req: CheckRequest, user: dict = Depends(require("read"))):
    """执行一次核对：鉴权 → 红线校验 → 三能力编排 → 返回草稿或人工队列。

    入参：req(CheckRequest) 请求体；user(dict) 由 token 解析出的当前用户。
    出参：统一结构；未登录/无 read 权限/触碰红线返回 fail(E_PERM_DENIED)。
    失败行为：鉴权失败在依赖层拒绝；红线拦截不进入模型；其余异常全局兜底。
    """
    # 安全审查注释：角色来自 token（require 依赖注入），不再信请求体自报，
    # 一线、质量、客户、管理员各按权限矩阵受限，模型无任何 token 进不来。
    # 先过红线校验，写回/自动决策/发真人安排一律拒绝，
    # 从结构上不给这些能力任何通道——不是靠模型判断，是代码里根本没有。
    gr = check_guardrails({  # 红线校验
        "writeback": req.writeback,  # 写回标志
        "auto_decide": req.auto_decide,  # 自动决策标志
        "send_to_real_person": req.send_to_real_person,  # 发真人标志
    })
    if not gr["ok"]:  # 触碰红线
        from app.core.response import fail  # 局部导入避免循环
        return fail("FORBIDDEN", f"触碰数据红线：{','.join(gr['violations'])}")  # 拒绝
    result = run_pipeline(  # 跑三能力编排
        req.batch_id,  # 批次
        req.position_code,  # 岗位
        req.demand_doc,  # 需求单
        req.handover_doc,  # 交接单
        req.oral_text,  # 口头变更
        req.link_key,  # 关联编号
    )
    audit(user["username"], "check", f"核对批次 {req.batch_id} 岗位 {req.position_code}")  # 记审计
    return ok(result)  # 返回统一成功结构（含 human_review，不替人确认）
