# SPDX-License-Identifier: MIT
"""口令哈希与 token 签发/校验：全部标准库（hashlib/hmac/base64/json），零第三方依赖。

令牌设计：HMAC-SHA256 签名的紧凑串，形如 base64(payload).base64(sig)。
- payload 含 username/role/exp，服务端不存会话，天然无状态。
- 每次校验重算签名比对，密钥来自 config.yaml（演练值，生产必须替换）。
- 角色写进 token 且参与签名，客户端改不动；改角色需重新登录。
"""  # 模块说明

import hashlib  # 哈希库
import hmac  # 消息认证码
import base64  # base64 编解码
import json  # JSON 编解码
import time  # 时间戳
from app.core.config import get  # 读鉴权配置


def _b64e(raw):
    """base64url 编码（去掉等号填充）。

    入参：raw(bytes) 原始字节。
    出参：str 编码串。
    失败行为：无（纯编码）。
    """
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")  # 编码去填充


def _b64d(text):
    """base64url 解码（补回等号填充）。

    入参：text(str) 编码串。
    出参：bytes 原始字节。
    失败行为：非法输入抛 ValueError，由调用方转「token 无效」。
    """
    pad = "=" * (-len(text) % 4)  # 计算填充
    return base64.urlsafe_b64decode(text + pad)  # 解码


def _secret():
    """取签名密钥（演练值，生产必须替换）。

    入参：无。
    出参：bytes 密钥字节。
    失败行为：无（读配置）。
    """
    return get("auth", "token_secret", "change-me").encode("utf-8")  # 配置密钥转字节


def hash_password(password, salt=None):
    """PBKDF2-HMAC-SHA256 加盐哈希口令。

    入参：password(str) 明文口令；salt(bytes|None) 盐，None 时随机生成。
    出参：dict，{"salt": str(hex), "hash": str(hex)}。
    失败行为：无（确定性算法，盐随机不影响校验）。
    """
    import os  # 局部导入
    salt = salt or os.urandom(16)  # 无盐则随机 16 字节
    iters = get("auth", "pbkdf2_iterations", 120000)  # 迭代次数读配置
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)  # 派生密钥
    return {"salt": salt.hex(), "hash": dk.hex()}  # 返回十六进制盐与哈希


def verify_password(password, salt_hex, hash_hex):
    """校验口令是否匹配（恒定时间比较）。

    入参：password(str) 明文；salt_hex(str) 盐十六进制；hash_hex(str) 期望哈希十六进制。
    出参：bool 是否匹配。
    失败行为：非法十六进制抛 ValueError 时按不匹配处理（fail-closed）。
    """
    try:  # 捕获非法输入
        dk = hashlib.pbkdf2_hmac(  # 重算哈希
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex),  # 算法与盐
            get("auth", "pbkdf2_iterations", 120000),  # 迭代次数
        )  # 派生密钥
        return hmac.compare_digest(dk.hex(), hash_hex)  # 恒定时间比较
    except (ValueError, TypeError):  # 非法十六进制或类型
        return False  # 不匹配


def issue_token(username, role):
    """签发 token（无状态，含角色与过期时间）。

    入参：username(str) 用户名；role(str) 角色标识。
    出参：str token 串。
    失败行为：无（纯签发）。
    """
    ttl = get("auth", "token_ttl_seconds", 28800)  # 有效期读配置
    payload = {  # 载荷
        "u": username,  # 用户名
        "r": role,  # 角色（参与签名，客户端改不动）
        "exp": int(time.time()) + ttl,  # 过期时间戳
    }  # 载荷结束
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))  # 序列化并编码
    sig = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())  # 签名
    return body + "." + sig  # 拼接返回


def decode_token(token):
    """校验并解析 token（验签 + 验过期）。

    入参：token(str) token 串。
    出参：dict，{"ok":bool,"username":str|None,"role":str|None,"reason":str}。
    失败行为：签名不符/格式错/过期一律 ok=False，绝不返回可用身份。
    """
    if not token or "." not in token:  # 格式不对
        return {"ok": False, "username": None, "role": None, "reason": "token 格式无效"}  # 拒绝
    body, sig = token.split(".", 1)  # 拆载荷与签名
    expect = _b64e(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())  # 重算签名
    if not hmac.compare_digest(sig, expect):  # 签名不符
        return {"ok": False, "username": None, "role": None, "reason": "token 签名无效"}  # 拒绝
    try:  # 解析载荷
        payload = json.loads(_b64d(body))  # 解码反序列化
    except (ValueError, TypeError):  # 坏 JSON
        return {"ok": False, "username": None, "role": None, "reason": "token 载荷损坏"}  # 拒绝
    if int(payload.get("exp", 0)) < int(time.time()):  # 过期
        return {"ok": False, "username": None, "role": None, "reason": "token 已过期"}  # 拒绝
    return {"ok": True, "username": payload.get("u"), "role": payload.get("r"), "reason": "ok"}  # 通过
