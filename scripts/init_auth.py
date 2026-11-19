# SPDX-License-Identifier: MIT
"""离线初始化鉴权库：建表 + 创建引导管理员（幂等）。

用法：python3 scripts/init_auth.py
说明：初始管理员账号口令来自 config.yaml，仅演练用；首次登录后应改口令。
"""  # 脚本说明

import sys  # 系统路径
from pathlib import Path  # 路径处理
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 加入仓库根

from app.auth.auth_store import init_auth_db, list_users  # 初始化与查询
from app.core.config import get  # 读配置


def main():
    """主流程：初始化并打印账号提示。

    入参：无。
    出参：无。
    失败行为：异常直接抛出，退出非零。
    """
    r = init_auth_db()  # 初始化
    admin = get("auth", "bootstrap_admin", "admin")  # 管理员账号
    print("鉴权库初始化完成。")  # 提示
    if r["created_admin"]:  # 新建了管理员
        print(f"  初始管理员：{admin}（口令见 config.yaml 的 bootstrap_password，演练用，请尽快修改）")  # 账号提示
    else:  # 已存在
        print(f"  管理员 {admin} 已存在，未改动。")  # 提示
    print(f"  当前用户数：{len(list_users())}")  # 统计


if __name__ == "__main__":  # 脚本入口
    main()  # 执行
