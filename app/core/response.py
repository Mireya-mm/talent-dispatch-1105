# SPDX-License-Identifier: MIT
"""统一响应封装：所有对外接口返回 {ok, data, error} 结构。"""  # 模块说明

from fastapi.responses import JSONResponse  # FastAPI 的 JSON 响应类


def error_code(name):
    """错误码表：把语义化名称映射为稳定字符串码。

    入参：name(str) 错误语义名。
    出参：str 错误码，未知名称原样返回。
    失败行为：无（纯映射函数）。
    """
    codes = {  # 错误码字典，集中管理，便于前端识别
        "FORBIDDEN": "E_PERM_DENIED",  # 权限不足
        "BAD_REQUEST": "E_BAD_REQUEST",  # 参数错误
        "NOT_IN_SCOPE": "E_OUT_OF_SCOPE",  # 超出试点范围
        "MODEL_UNAVAILABLE": "E_MODEL_DOWN",  # 模型不可用
        "SCHEMA_INVALID": "E_SCHEMA_INVALID",  # 模型输出不合规
        "INTERNAL": "E_INTERNAL",  # 内部错误
    }
    return codes.get(name, name)  # 返回映射码或原名


def ok(data=None):
    """构造成功响应。

    入参：data 业务数据，可为任意可序列化对象，默认 None。
    出参：dict，形如 {"ok": True, "data": data, "error": None}。
    失败行为：无（纯构造函数）。
    """
    return {"ok": True, "data": data, "error": None}  # 成功结构，error 固定为 None


def fail(code, msg, data=None):
    """构造失败响应。

    入参：code(str) 错误码；msg(str) 人类可读信息；data 附加数据，默认 None。
    出参：dict，形如 {"ok": False, "data": data, "error": {code, msg}}。
    失败行为：无（纯构造函数）。
    """
    return {  # 失败结构
        "ok": False,  # 成功标志为 False
        "data": data,  # 附加数据（多为 None）
        "error": {"code": error_code(code), "msg": msg},  # 错误体，码经映射
    }


def fail_response(code, msg, status_code=400, data=None):
    """构造带 HTTP 状态码的失败响应（供异常处理器使用）。

    入参：code(str) 错误码；msg(str) 信息；status_code(int) HTTP 码；data 附加数据。
    出参：JSONResponse，body 为统一失败结构。
    失败行为：无（纯构造函数）。
    """
    return JSONResponse(  # 返回 JSON 响应
        status_code=status_code,  # 设置 HTTP 状态码
        content=fail(code, msg, data),  # body 用统一失败结构
    )
