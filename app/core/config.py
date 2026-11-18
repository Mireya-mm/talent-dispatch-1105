# SPDX-License-Identifier: MIT
"""配置加载：唯一读取仓库根 config.yaml，提供只读访问。"""  # 模块说明

from pathlib import Path  # 路径处理，用于定位仓库根
import yaml  # YAML 解析库，读取配置文件

# 仓库根目录 = 本文件(app/core/config.py)向上两级
ROOT = Path(__file__).resolve().parent.parent.parent  # 定位到 talent-dispatch-1105/
CONFIG_PATH = ROOT / "config.yaml"  # 配置文件固定路径，不接外部传入（防篡改）

_cache = None  # 模块级缓存，避免每次请求重复读盘


def load_config():
    """加载并返回配置字典。

    入参：无（路径固定为仓库根 config.yaml）。
    出参：dict，配置内容。
    失败行为：文件缺失或 YAML 解析失败时抛出 RuntimeError，服务启动即失败，
             绝不返回空配置——空配置会导致鉴权/红线失效，属于不可接受风险。
    """
    global _cache  # 声明使用模块级缓存
    if _cache is not None:  # 已加载过则直接返回缓存
        return _cache  # 返回缓存配置
    if not CONFIG_PATH.exists():  # 配置文件不存在
        raise RuntimeError("config.yaml 缺失，拒绝以空配置启动")  # 硬失败，不降级
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:  # 以 UTF-8 打开配置
        data = yaml.safe_load(fh)  # 解析 YAML 为字典
    if not isinstance(data, dict):  # 解析结果非字典
        raise RuntimeError("config.yaml 格式错误，顶层必须是映射")  # 硬失败
    _cache = data  # 写入缓存
    return _cache  # 返回配置


def get(section, key, default=None):
    """按 section.key 读取配置项。

    入参：section(str) 配置段名；key(str) 键名；default 缺失时的默认值。
    出参：对应配置值，找不到返回 default。
    失败行为：配置未加载时先触发 load_config；段不存在返回 default，不抛异常。
    """
    cfg = load_config()  # 确保配置已加载
    return cfg.get(section, {}).get(key, default)  # 逐层取值，缺失用默认值
