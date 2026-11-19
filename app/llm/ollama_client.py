# SPDX-License-Identifier: MIT
"""Ollama 客户端：全工程唯一模型出口，参数全部读 config.yaml。

三个硬性约束：
1. 每次请求显式传 think:false —— Qwen3.5 默认开思考，0.8B 会把 token 全耗在
   thinking 上导致 content 为空（Modelfile 不支持 PARAMETER think，只能请求体传）。
2. 模型输出一律当脏数据 —— 调用方必须过 schema，不合规转人工，不让模型自己修。
3. 任何失败（超时/非200/空输出/坏 JSON）都返回降级结果转人工，不重试、不静默通过。
"""  # 模块说明

import json  # JSON 编解码
import urllib.request  # 标准库 HTTP 客户端，不引入第三方依赖
import urllib.error  # HTTP 异常类型
from app.core.config import get  # 读取模型配置


def build_payload(user_text, system_text=None):
    """构造 Ollama /api/chat 请求体。

    入参：user_text(str) 用户输入文本；system_text(str) 可选系统提示词。
    出参：dict 请求体，含 think:false、format:json 与全部模型参数。
    失败行为：无（纯构造函数）；参数缺失时由调用方保证。
    """
    messages = []  # 消息列表
    if system_text:  # 有系统提示词
        messages.append({"role": "system", "content": system_text})  # 加入系统消息
    messages.append({"role": "user", "content": user_text})  # 加入用户消息
    return {  # 请求体
        "model": get("ollama", "model"),  # 模型名读配置
        "stream": False,  # 非流式，一次性拿完整输出
        "format": get("ollama", "format"),  # json 格式，便于解析
        "think": get("ollama", "think"),  # 关键：显式关闭思考，否则 content 为空
        "options": {  # 模型参数
            "temperature": get("ollama", "temperature"),  # 温度读配置
            "num_ctx": get("ollama", "num_ctx"),  # 上下文窗口读配置
            "num_predict": get("ollama", "num_predict"),  # 输出上限读配置
        },
        "messages": messages,  # 消息列表
    }


def call_model(user_text, system_text=None):
    """调用本地模型，返回结构化结果或降级标记（不抛异常）。

    入参：user_text(str) 用户输入；system_text(str) 可选系统提示词。
    出参：dict，{"ok": bool, "data": dict|None, "reason": str}；
          ok=True 表示拿到可解析 JSON，data 为模型输出；否则 data=None、reason 说明原因。
    失败行为：超时/连接失败/非200/空 content/坏 JSON 一律 ok=False 并给出原因，
             由上层转人工队列；绝不重试、绝不返回半截结果当成功。
    """
    payload = build_payload(user_text, system_text)  # 构造请求体
    url = get("ollama", "base_url").rstrip("/") + "/api/chat"  # 拼接口地址
    timeout = get("ollama", "timeout_seconds", 60)  # 读超时配置
    req = urllib.request.Request(  # 构造 HTTP 请求
        url,  # 目标地址
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),  # 请求体字节
        headers={"Content-Type": "application/json"},  # JSON 头
        method="POST",  # POST 方法
    )
    try:  # 捕获所有模型调用失败
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # 发起请求
            body = json.loads(resp.read().decode("utf-8"))  # 解析响应
    except urllib.error.HTTPError as e:  # HTTP 非200
        return {"ok": False, "data": None, "reason": f"模型 HTTP 错误：{e.code}"}  # 降级
    except (urllib.error.URLError, TimeoutError, OSError) as e:  # 连接/超时
        return {"ok": False, "data": None, "reason": f"模型不可用：{type(e).__name__}"}  # 降级
    except (ValueError, UnicodeDecodeError) as e:  # 响应解析失败
        return {"ok": False, "data": None, "reason": f"模型响应损坏：{type(e).__name__}"}  # 降级

    content = (body.get("message") or {}).get("content", "")  # 取正式输出（非 thinking）
    if not content or not content.strip():  # 空输出
        # 人工确认注释：空 content 通常是思考吃光 token 所致，属不可信输出，
        # 必须转人工，不能把空当"无异常"放行（否则会把未确认项静默漏掉）。
        return {"ok": False, "data": None, "reason": "模型输出为空（疑似思考耗尽 token）"}  # 降级
    try:  # 尝试解析 JSON
        parsed = json.loads(content)  # 解析模型输出
    except (ValueError, TypeError):  # 坏 JSON
        return {"ok": False, "data": None, "reason": "模型输出不是合法 JSON"}  # 降级
    return {"ok": True, "data": parsed, "reason": "模型输出已解析，待 schema 校验"}  # 返回待校验
