# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""生成竖向、含菱形人工判断点的架构图 SVG（方案设计）。

仅依赖 Python 标准库。输出覆盖 docs/架构图.svg。
菱形＝必须人工的判断点；主轴走正常路径，右侧为「否」分支。
"""
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "架构图.svg"

W, H = 1000, 2120
BG = "#fffdf5"
PAL = {
    "main": ("#eaf2e6", "#7a9474", "#29443b"),
    "dec":  ("#fff4d6", "#c9a227", "#29443b"),
    "bad":  ("#fbeae7", "#b23a2e", "#b23a2e"),
    "man":  ("#f2f6ee", "#2d654f", "#29443b"),
}
MX, MW = 300, 320      # 主轴矩形
DW, DH = 360, 110      # 菱形
CX = 460
SX, SW, SH = 690, 270, 56   # 右侧「否」分支


def esc(s):
    return html.escape(s)


def text(x, y, s, size=13, fill="#29443b", anchor="middle", weight="normal"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')


nodes = [
    dict(id="A", k="r", y=110,  h=56,  t="数据接入层 · 脱敏只读导出",        s="批次号 / 岗位代号 / 来源位置 / 两个时间戳", c="main"),
    dict(id="B", k="d", y=196,  h=110, t="◇ 判断 1 · 本单在试点范围内？",    s="清单是否已锁定 · f05", c="dec"),
    dict(id="C", k="r", y=336,  h=56,  t="知识层 · 知识库（知识图谱）",      s="岗位硬条件 / 规则版本 / 关联编号 / 确认状态", c="main"),
    dict(id="D", k="d", y=422,  h=110, t="◇ 判断 2 · 跨工具有统一关联编号？", s="f30 f31", c="dec"),
    dict(id="E", k="r", y=562,  h=56,  t="能力 1 · 场景范围核对",             s="输出：范围内 / 范围外 + 命中条款", c="main"),
    dict(id="F", k="r", y=648,  h=56,  t="能力 2 · 资料与版本核对（核心）",   s="抽取口头变更 → 结构化要素 → 版本比对", c="main"),
    dict(id="G", k="d", y=734,  h=110, t="◇ 判断 3 · 变更是否回写需求单？",   s="f10 f23", c="dec"),
    dict(id="H", k="r", y=874,  h=56,  t="交付层 · 一页缺项清单",             s="含来源位置，不给长摘要 · f15", c="main"),
    dict(id="I", k="d", y=960,  h=110, t="◇ 判断 4 · 版本与关键字段能否确认？", s="f44 f41", c="dec"),
    dict(id="J", k="r", y=1100, h=56,  t="能力 3 · 交接草稿整理",             s="最新版本 / 未确认项 / 截止时间 · f23", c="main"),
    dict(id="K", k="d", y=1186, h=110, t="◇ 判断 5 · 每条结果能否关联来源与复核记录？", s="f42", c="dec"),
    dict(id="L", k="r", y=1326, h=56,  t="交接单草稿",                        s="接收人 / 版本 / 未结项 · f20", c="main"),
    dict(id="M", k="d", y=1412, h=110, t="◇ 判断 6 · 到岗条件与交接单是否一致？", s="f50 f51", c="dec"),
    dict(id="N", k="r", y=1552, h=56,  t="人工确认闸门",                      s="正式确认由业务负责人完成 · 模型无审批权 f22 f41", c="man"),
    dict(id="O", k="r", y=1638, h=56,  t="交接完成",                          s="只读、未写回、未对外发送", c="man"),
]
byid = {n["id"]: n for n in nodes}
labels = {("B", "C"): "是", ("D", "E"): "是", ("G", "H"): "已处理",
          ("I", "J"): "是", ("K", "L"): "是", ("M", "N"): "是"}
sides = [
    dict(at="B", t="整批暂停 / 排除",           s="否 · 不默认按全量处理", lab="否"),
    dict(at="D", t="降级人工比对并留痕",       s="否 · 不猜、不自动拼接", lab="否"),
    dict(at="G", t="列「变更未回写」+ 旧版本", s="否 · status = 未确认", lab="否"),
    dict(at="I", t="进人工队列 / 暂停",        s="否 · 绝不默认通过", lab="否"),
    dict(at="K", t="不签认，转人工",           s="否 · 缺来源或缺复核记录", lab="否"),
    dict(at="M", t="到岗返工登记 / 周复盘",    s="否 · f54 f55", lab="否"),
]

o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Microsoft YaHei, sans-serif">']
o.append('''<defs>
  <marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#2d654f"/></marker>
  <marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#b23a2e"/></marker>
</defs>''')
o.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')
o.append(text(40, 44, "架构图 · 业务核对助手（方案设计）", 24, "#29443b", "start", "bold"))
o.append(text(40, 70, "竖向分层 / 菱形＝必须人工的判断点 / 主轴走正常路径，右侧为「否」分支", 13, "#6b7f70", "start"))
o.append(text(40, 92, "仅设计，不代表已实现系统 · 全链路只读，没有写回通道", 12, "#6b7f70", "start"))

for i in range(len(nodes) - 1):
    a, b = nodes[i], nodes[i + 1]
    y1, y2 = a["y"] + a["h"], b["y"]
    o.append(f'<line x1="{CX}" y1="{y1}" x2="{CX}" y2="{y2-4}" stroke="#2d654f" stroke-width="2" marker-end="url(#a)"/>')
    lab = labels.get((a["id"], b["id"]))
    if lab:
        o.append(text(478, (y1 + y2) // 2 + 4, lab, 11, "#2d654f", "start"))

for s in sides:
    d = byid[s["at"]]
    ry = d["y"] + d["h"] / 2
    sy = d["y"] + (d["h"] - SH) / 2
    path = f'M {CX+DW/2},{ry} L 670,{ry} L 670,{sy+SH/2} L {SX-4},{sy+SH/2}'
    o.append(f'<path d="{path}" stroke="#b23a2e" stroke-width="1.6" fill="none" marker-end="url(#ar)"/>')
    o.append(text(662, ry - 8, s["lab"], 11, "#b23a2e", "end"))

for n in nodes:
    fill, stroke, tc = PAL[n["c"]]
    if n["k"] == "r":
        o.append(f'<rect x="{MX}" y="{n["y"]}" width="{MW}" height="{n["h"]}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        o.append(text(CX, n["y"] + 25, n["t"], 14, tc))
        if n["s"]:
            o.append(text(CX, n["y"] + 44, n["s"], 11, "#6b7f70"))
    else:
        y, h = n["y"], n["h"]
        pts = f'{CX},{y} {CX+DW/2},{y+h/2} {CX},{y+h} {CX-DW/2},{y+h/2}'
        o.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
        o.append(text(CX, y + h / 2 - 2, n["t"], 12.5, tc, "middle", "bold"))
        o.append(text(CX, y + h / 2 + 20, n["s"], 11, "#8a7433"))

for s in sides:
    d = byid[s["at"]]
    sy = d["y"] + (d["h"] - SH) / 2
    o.append(f'<rect x="{SX}" y="{sy}" width="{SW}" height="{SH}" rx="8" fill="#fbeae7" stroke="#b23a2e" stroke-width="1.2"/>')
    o.append(text(SX + SW / 2, sy + 24, s["t"], 12, "#b23a2e"))
    o.append(text(SX + SW / 2, sy + 43, s["s"], 10, "#6b7f70"))

# 侧边约束说明
o.append(f'<rect x="40" y="1740" width="260" height="150" rx="8" fill="#f2f6ee" stroke="#2d654f" stroke-width="1.2"/>')
o.append(text(60, 1767, "评测层 · Harness", 14, "#29443b", "start", "bold"))
for i, line in enumerate([
    "固定样本回归", "未确认误判为已确认 = 0 容忍",
    "每次提示词 / 规则变更全量重跑", "绑定能力 2 与能力 3",
]):
    o.append(text(60, 1793 + i * 23, "· " + line, 11, "#29443b", "start"))
o.append(f'<rect x="320" y="1740" width="260" height="150" rx="8" fill="#f2f6ee" stroke="#2d654f" stroke-width="1.2"/>')
o.append(text(340, 1767, "本地部署（例 Ollama）", 14, "#29443b", "start", "bold"))
for i, line in enumerate([
    "合成资料不出域", "抽取在本地完成", "模型选型待定", "真实接口 / 规则待核实",
]):
    o.append(text(340, 1793 + i * 23, "· " + line, 11, "#29443b", "start"))
o.append(f'<rect x="600" y="1740" width="360" height="150" rx="8" fill="#fbeae7" stroke="#b23a2e" stroke-width="1.2"/>')
o.append(text(620, 1767, "不开放（f05 f32 f52）", 14, "#b23a2e", "start", "bold"))
for i, line in enumerate([
    "写回需求单 / 台账", "外部消息 / 执行接口",
    "录用或派遣资格判定", "向真实人员发送安排",
]):
    o.append(text(620, 1793 + i * 23, "· " + line, 11, "#b23a2e", "start"))

o.append(f'<rect x="40" y="1910" width="920" height="170" rx="8" fill="#f7f4e8" stroke="#cbd4bf" stroke-width="1.2"/>')
o.append(text(60, 1937, "试点边界（本轮不可越线）", 14, "#29443b", "start", "bold"))
for i, line in enumerate([
    "· 一个批次 f05；30 个岗位列硬条件与待确认项、变更影响清单 f02；仅脱敏只读导出 f32",
    "· 不自动决定录用或派遣资格、不向真实人员发送安排 f05 f52；对外承诺由业务人员确认 f52",
    "· 一线可提交变更、正式确认由业务负责人完成，模型没有审批权 f22；正式结论须授权人员确认 f41",
    "· 四周、两名骨干、每周不超四小时 f03；范围业务负责人定、质量侧可叫停、客户侧确认用途 f04",
    "· f12「80 单 / 22% 重复澄清」为虚构演练样本，不作基线",
]):
    o.append(text(60, 1963 + i * 23, line, 11.5, "#29443b", "start"))
o.append(text(40, 2100, "编号 fNN = fsg-assignment-fNN｜来源 discovery-report.md｜方案设计阶段·不开发系统", 11, "#6b7f70", "start"))
o.append("</svg>")

OUT.write_text("\n".join(o), encoding="utf-8")
print("generated", OUT.relative_to(ROOT), "| viewBox 0 0", W, H,
      "| 菱形判断点", sum(1 for n in nodes if n["k"] == "d"), "| 节点", len(nodes))
