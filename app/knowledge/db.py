# SPDX-License-Identifier: MIT
"""知识库数据库连接管理：严格区分「初始化可写」与「运行时只读」两种连接。

红线（对应 f30/f31/只读核对）：
1. 业务运行时一律用 connect_ro()——以 SQLite URI mode=ro 打开，物理上无法写入。
2. 只有 scripts/init_knowledge.py 这类离线脚本才用 connect_rw() 建表灌数。
3. 代码里不存在任何「业务链路调用 connect_rw」的路径，从结构上杜绝写回。
"""  # 模块说明

import sqlite3  # 标准库 SQLite 驱动，零第三方依赖
from pathlib import Path  # 路径处理
from app.core.config import ROOT, get  # 读取仓库根与数据库路径配置


def db_path():
    """解析知识库数据库文件路径（相对仓库根）。

    入参：无。
    出参：Path，数据库的绝对路径。
    失败行为：无（纯路径拼接），文件不存在时由连接函数按只读规则处理。
    """
    rel = get("knowledge", "db_path", "data/knowledge.db")  # 读配置里的相对路径
    p = Path(rel)  # 构造路径对象
    return p if p.is_absolute() else ROOT / p  # 相对路径拼到仓库根，绝对路径原样返回


def connect_ro():
    """建立运行时只读连接——业务链路唯一允许的连接方式。

    入参：无。
    出参：sqlite3.Connection，以 mode=ro 打开，任何写操作都会抛异常。
    失败行为：数据库文件不存在时抛 RuntimeError，要求先跑初始化脚本，不静默建空库
              （空库会让知识库查询全部落空却看似正常，属不可接受的静默降级）。
    """
    path = db_path()  # 取数据库路径
    if not path.exists():  # 文件不存在
        raise RuntimeError("知识库未初始化，请先运行 python3 scripts/init_knowledge.py")  # 硬失败
    uri = f"file:{path}?mode=ro"  # SQLite URI，mode=ro 物理只读
    conn = sqlite3.connect(uri, uri=True)  # 只读方式打开，写操作直接报错
    conn.row_factory = sqlite3.Row  # 让结果可按列名访问
    return conn  # 返回只读连接


def connect_rw():
    """建立可写连接——仅供离线初始化脚本使用，业务代码禁止调用。

    入参：无。
    出参：sqlite3.Connection，可读写连接。
    失败行为：自动创建父目录，不抛异常（初始化场景允许首次建库）。
    """
    path = db_path()  # 取数据库路径
    path.parent.mkdir(parents=True, exist_ok=True)  # 建父目录（首次初始化）
    conn = sqlite3.connect(str(path))  # 读写方式打开（不存在则创建）
    conn.row_factory = sqlite3.Row  # 按列名访问
    return conn  # 返回可写连接
