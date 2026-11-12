# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""复现方案设计任务 3 的首年 ROI 简化测算（纯数值计算）。

仅依赖 Python 标准库；不接任何业务接口、不读业务数据。
所有输入均为「演练假设·待补」占位值，不是调研结果，不作立项依据。
用法：python scripts/calc_roi.py
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Inputs:
    setup_fee: float = 36_000.0        # 一次性实施报价（元）
    monthly_cost: float = 2_000.0      # 每月运行费用（元）
    monthly_volume: float = 300.0      # 每月处理数量（件）
    minutes_saved: float = 30.0        # 每件节省时间（分钟，含人工复核）
    hourly_rate: float = 80.0          # 人员综合时薪（元/小时）
    realization: float = 0.50          # 预计兑现比例（采用率 × 可兑现比例）


def calc(i: Inputs) -> dict:
    monthly_hours = i.monthly_volume * i.minutes_saved / 60.0
    monthly_gross = monthly_hours * i.hourly_rate
    monthly_realized = monthly_gross * i.realization
    monthly_net_cash = monthly_realized - i.monthly_cost
    first_year_gain = monthly_realized * 12
    first_year_cost = i.setup_fee + i.monthly_cost * 12
    first_year_net = first_year_gain - first_year_cost
    roi = first_year_net / first_year_cost if first_year_cost else 0.0
    payback = i.setup_fee / monthly_net_cash if monthly_net_cash > 0 else None
    # 首年打平所需的兑现后月收益
    breakeven_monthly = first_year_cost / 12
    # 在其他参数不变时，各输入的打平临界值
    return {
        "monthly_hours": monthly_hours,
        "monthly_gross": monthly_gross,
        "monthly_realized": monthly_realized,
        "monthly_net_cash": monthly_net_cash,
        "first_year_gain": first_year_gain,
        "first_year_cost": first_year_cost,
        "first_year_net": first_year_net,
        "roi": roi,
        "payback_months": payback,
        "breakeven_monthly": breakeven_monthly,
        "breakeven_realization": breakeven_monthly / monthly_gross if monthly_gross else None,
        "breakeven_volume": breakeven_monthly / (i.minutes_saved / 60 * i.hourly_rate * i.realization),
        "breakeven_minutes": breakeven_monthly / (i.monthly_volume * i.hourly_rate / 60 * i.realization),
    }


def main():
    i = Inputs()
    r = calc(i)
    print("=== 输入（全部为演练假设·待补）===")
    print(f"  一次性实施报价   {i.setup_fee:>10,.0f} 元")
    print(f"  每月运行费用     {i.monthly_cost:>10,.0f} 元")
    print(f"  每月处理数量     {i.monthly_volume:>10,.0f} 件")
    print(f"  每件节省时间     {i.minutes_saved:>10,.0f} 分钟")
    print(f"  人员综合时薪     {i.hourly_rate:>10,.0f} 元/小时")
    print(f"  预计兑现比例     {i.realization*100:>10,.0f} %")
    print("=== 计算 ===")
    print(f"  月节省工时       {r['monthly_hours']:>10,.0f} 小时")
    print(f"  月毛节省         {r['monthly_gross']:>10,.0f} 元")
    print(f"  兑现后月收益     {r['monthly_realized']:>10,.0f} 元")
    print(f"  月净现金流       {r['monthly_net_cash']:>10,.0f} 元")
    print(f"  首年兑现收益     {r['first_year_gain']:>10,.0f} 元")
    print(f"  首年总成本       {r['first_year_cost']:>10,.0f} 元")
    print(f"  首年净收益       {r['first_year_net']:>10,.0f} 元")
    print(f"  ROI              {r['roi']*100:>10,.1f} %")
    pb = r["payback_months"]
    print(f"  回本时间         {('%.1f 个月' % pb) if pb else '无法回本（月净现金流为负）':>10}")
    print("=== 打平临界点（其余参数不变）===")
    print(f"  兑现后月收益需 ≥ {r['breakeven_monthly']:>10,.0f} 元（当前 {r['monthly_realized']:,.0f}）")
    print(f"  兑现比例临界     {r['breakeven_realization']*100:>10,.1f} %")
    print(f"  月处理量临界     {r['breakeven_volume']:>10,.0f} 件")
    print(f"  每件节省临界     {r['breakeven_minutes']:>10,.1f} 分钟")
    print("=== 声明 ===")
    print("  数字全部为演练假设·待补；真实单量、耗时、复核工时未提供；f12 不作基线。")
    print("  工时节省不等于现金收益；真实样本补齐前不作出「划算」的结论。")


if __name__ == "__main__":
    main()
