# SPDX-License-Identifier: MIT
"""FastAPI 应用入口：全局异常兜底 + 挂载路由。"""  # 模块说明

from fastapi import FastAPI, Request  # FastAPI 主类与请求对象
from fastapi.exceptions import RequestValidationError  # 参数校验异常
from fastapi.responses import HTMLResponse  # 首页 HTML 响应
from app.core.config import ROOT  # 仓库根，用于定位首页文件
from app.api.routes import router as api_router  # 导入路由
from app.api.auth_routes import router as auth_router  # 鉴权/管理路由
from app.core.config import get  # 读取配置
from app.core.response import fail_response  # 统一失败响应
from app.auth.deps import AuthError  # 鉴权异常类型

app = FastAPI(  # 创建应用实例
    title=get("app", "name"),  # 标题读配置
    version=get("app", "version"),  # 版本读配置
)  # 应用实例

app.include_router(api_router)  # 挂载接口路由
app.include_router(auth_router)  # 挂载鉴权/管理路由


@app.get("/", response_class=HTMLResponse, include_in_schema=False)  # 首页：交互演示
def index():
    """返回自包含的交互演示首页（打开网址即可看完整核对流程）。

    入参：无。
    出参：HTMLResponse，index.html 内容。
    失败行为：文件缺失时返回简易提示页，不让根路径 500。
    """
    p = ROOT / "index.html"  # 首页文件路径
    if p.exists():  # 文件存在
        return HTMLResponse(p.read_text(encoding="utf-8"))  # 返回页面
    return HTMLResponse("<h2>演示页缺失，请访问 /docs 查看接口</h2>")  # 兜底提示


@app.exception_handler(AuthError)  # 鉴权异常处理器
async def auth_error_handler(request, exc):
    """鉴权失败时返回统一结构，HTTP 403，不裸露内部细节。

    入参：request(Request) 请求对象；exc(AuthError) 鉴权异常。
    出参：JSONResponse，统一失败结构，HTTP 403。
    失败行为：无（纯转换）。
    """
    return fail_response("FORBIDDEN", exc.msg, 403)  # 统一失败响应


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
