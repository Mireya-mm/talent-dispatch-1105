# SPDX-License-Identifier: MIT
"""FastAPI 应用入口：全局异常兜底 + 挂载路由。"""  # 模块说明

from fastapi import FastAPI, Request  # FastAPI 主类与请求对象
from fastapi.exceptions import RequestValidationError  # 参数校验异常
from app.api.routes import router as api_router  # 导入路由
from app.core.config import get  # 读取配置
from app.core.response import fail_response  # 统一失败响应

app = FastAPI(  # 创建应用实例
    title=get("app", "name"),  # 标题读配置
    version=get("app", "version"),  # 版本读配置
)  # 应用实例

app.include_router(api_router)  # 挂载接口路由


@app.exception_handler(RequestValidationError)  # 参数校验异常处理器
async def validation_handler(request, exc):
    """参数校验失败时返回统一结构，不裸露 FastAPI 默认错误体。

    入参：request(Request) 请求对象；exc(RequestValidationError) 校验异常。
    出参：JSONResponse，统一失败结构，HTTP 422。
    失败行为：无（纯转换）。
    """
    return fail_response("BAD_REQUEST", "请求参数不合法", 422)  # 统一失败响应


@app.exception_handler(Exception)  # 全局异常兜底
async def global_exception_handler(request, exc):
    """任何未捕获异常都包成统一结构，绝不裸露 500 堆栈。

    入参：request(Request) 请求对象；exc(Exception) 异常对象。
    出参：JSONResponse，统一失败结构，HTTP 500。
    失败行为：记录异常类型到 msg（不泄露敏感堆栈），便于定位又不泄密。
    """
    # 安全审查注释：对外只暴露异常类型，不返回堆栈/路径/配置，防止信息泄露。
    return fail_response("INTERNAL", f"内部错误：{type(exc).__name__}", 500)  # 统一失败
