# -*- coding: utf-8 -*-
"""生成竖向、含菱形判断点的现状流程图 SVG。

仅依赖 Python 标准库。输出覆盖仓库根目录下「现状流程图.svg」。
菱形＝必须人工的判断点；主轴走现状问题路径，右侧为另一分支。
"""
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "现状流程图.svg"

W, H = 980, 2170
BG = "#fffdf5"
PAL = {
    "main": ("#eaf2e6", "#7a9474", "#29443b"),
    "dec": ("#fff4d6", "#c9a227", "#29443b"),
    "bad": ("#fbeae7", "#b23a2e", "#b23a2e"),
    "man": ("#f2f6ee", "#2d654f", "#29443b"),
}
MX, MW = 300, 300      # 主轴矩形
DW = 340               # 菱形宽
CX = 450
SX, SW, SH = 660, 280, 56  # 右侧分支列

NODES = [
    dict(id="A", k="r", y=110, h=56, t="客户提出岗位需求", s="岗位简报 / 变更单", c="main"),
    dict(id="B", k="r", y=196, h=56, t="岗位条件澄清", s="群消息先处理 → 后补单 · f13", c="main"),
    dict(id="C", k="r", y=282, h=56, t="登记岗位条件到需求单", s="", c="main"),
    dict(id="D", k="d", y=368, h=110, t="电话中是否修改岗位条件？", s="判断点 1", c="dec"),
    dict(id="E", k="r", y=508, h=56, t="电话改条件：技能要求 / 夜班班次", s="f10 f11", c="main"),
    dict(id="F", k="d", y=594, h=110, t="变更是否回写需求单？", s="判断点 2", c="dec"),
    dict(id="H", k="r", y=734, h=56, t="交接单仍引用旧技能要求", s="f10 · 本案例断点", c="bad"),
    dict(id="I", k="d", y=820, h=110, t="版本与关键字段能否确认？", s="判断点 3", c="dec"),
    dict(id="K", k="d", y=960, h=110, t="跨工具是否有统一关联编号？", s="判断点 4 · f30", c="dec"),
    dict(id="L", k="r", y=1100, h=56, t="人工比对服务台 / 台账 / 文件库", s="f30 f31", c="main"),
    dict(id="N", k="r", y=1186, h=56, t="当班逐字段人工复核", s="建议不覆盖原值、不省确认 · f14", c="main"),
    dict(id="O", k="d", y=1272, h=110, t="结果能否关联来源与复核记录？", s="判断点 5 · f42", c="dec"),
    dict(id="P", k="r", y=1412, h=56, t="交接单列最新版本 / 未确认项 / 截止时间", s="f23", c="main"),
    dict(id="Q", k="r", y=1498, h=56, t="接收人签收，责任转移", s="f20 f25", c="main"),
    dict(id="R", k="r", y=1584, h=56, t="人员到岗", s="", c="main"),
    dict(id="S", k="d", y=1670, h=110, t="到岗条件与交接单是否一致？", s="判断点 6", c="dec"),
    dict(id="T", k="r", y=1810, h=56, t="到岗返工 · 客户体验受损", s="f50 f51 f53", c="bad"),
    dict(id="U", k="r", y=1896, h=56, t="反馈 / 投诉登记，周复盘", s="f54 f55", c="main"),
]
BY_ID = {n["id"]: n for n in NODES}
EDGE_LABELS = {
    ("D", "E"): "是（现状）", ("F", "H"): "否（现状）", ("I", "K"): "是",
    ("K", "L"): "否（现状）", ("O", "P"): "是", ("S", "T"): "否（现状）",
}
SIDES = [
    dict(at="D", t="沿用已确认条件", s="否 · 直接进版本确认", lab="否"),
    dict(at="F", t="生成新版本并标记确认状态", s="是 · f24 f34", lab="是"),
    dict(at="I", t="进人工队列 / 暂停", s="否 · f44 → 授权人员确认 f41", lab="否"),
    dict(at="K", t="只读比对，出一页缺项清单", s="是 · f15 f32", lab="是"),
    dict(at="O", t="不签认，转人工复核", s="否 · f44", lab="否"),
    dict(at="S", t="按确认条件正常到岗", s="是 · 进入反馈复盘", lab="是"),
]
BOUNDARY = [
    "· 一个批次的需求单 f05；仅脱敏只读导出，写回 / 外部消息 / 执行接口不开放 f32",
    "· 不自动决定录用或派遣资格、不向真实人员发送安排，对外承诺由业务人员确认 f05 f52",
    "· 一线可提交变更、正式确认由业务负责人完成，模型没有审批权 f22；正式结论须授权人员确认 f41",
    "· 四周、两名骨干、每周不超四小时 f03；范围业务负责人定、质量侧可叫停、客户侧确认用途 f04",
]


def text(x, y, s, size=13, fill="#29443b", anchor="middle", weight="normal"):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{html.escape(s)}</text>')


def build():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'width="{W}" height="{H}" font-family="Microsoft YaHei, sans-serif">']
    o.append('''<defs>
  <marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#2d654f"/></marker>
  <marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="#b23a2e"/></marker>
</defs>''')
    o.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')
    o.append(text(40, 44, "现状流程图 · 派遣岗位需求与到岗交接", 24, "#29443b", "start", "bold"))
    o.append(text(40, 70, "竖向流程 / 菱形＝必须人工的判断点 / 主轴走现状问题路径，右侧为另一分支", 13, "#6b7f70", "start"))
    o.append(text(40, 92, "合成演练 · 只读核对与人工交接 · 不代表真实授权、业务执行或客户验收", 12, "#6b7f70", "start"))

    # 主轴竖向连线
    for i in range(len(NODES) - 1):
        a, b = NODES[i], NODES[i + 1]
        y1, y2 = a["y"] + a["h"], b["y"]
        color = "#b23a2e" if b["c"] == "bad" else "#2d654f"
        mk = "ar" if b["c"] == "bad" else "a"
        o.append(f'<line x1="{CX}" y1="{y1}" x2="{CX}" y2="{y2-4}" stroke="{color}" stroke-width="2" marker-end="url(#{mk})"/>')
        lab = EDGE_LABELS.get((a["id"], b["id"]))
        if lab:
            o.append(text(468, (y1 + y2) // 2 + 4, lab, 11, color, "start"))

    # 菱形 → 右侧分支
    for s in SIDES:
        d = BY_ID[s["at"]]
        ry = d["y"] + d["h"] / 2
        sy = d["y"] + (d["h"] - SH) / 2
        o.append(f'<path d="M {CX+DW/2},{ry} L 640,{ry} L 640,{sy+SH/2} L {SX-4},{sy+SH/2}" '
                 f'stroke="#2d654f" stroke-width="1.6" fill="none" marker-end="url(#a)"/>')
        o.append(text(632, ry - 8, s["lab"], 11, "#2d654f", "end"))

    # 节点
    for n in NODES:
        fill, stroke, tc = PAL[n["c"]]
        if n["k"] == "r":
            o.append(f'<rect x="{MX}" y="{n["y"]}" width="{MW}" height="{n["h"]}" rx="8" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
            o.append(text(CX, n["y"] + 25, n["t"], 14, tc))
            if n["s"]:
                o.append(text(CX, n["y"] + 44, n["s"], 11, "#6b7f70"))
        else:
            y, h = n["y"], n["h"]
            pts = f'{CX},{y} {CX+DW/2},{y+h/2} {CX},{y+h} {CX-DW/2},{y+h/2}'
            o.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
            o.append(text(CX, y + h / 2 - 2, n["t"], 13, tc, "middle", "bold"))
            o.append(text(CX, y + h / 2 + 20, n["s"], 11, "#8a7433"))

    for s in SIDES:
        d = BY_ID[s["at"]]
        sy = d["y"] + (d["h"] - SH) / 2
        fill, stroke, tc = PAL["man"]
        o.append(f'<rect x="{SX}" y="{sy}" width="{SW}" height="{SH}" rx="8" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        o.append(text(SX + SW / 2, sy + 24, s["t"], 12, tc))
        o.append(text(SX + SW / 2, sy + 43, s["s"], 10, "#6b7f70"))

    # 底部边界
    o.append(f'<rect x="40" y="1990" width="900" height="150" rx="8" fill="#f7f4e8" stroke="#cbd4bf" stroke-width="1.2"/>')
    o.append(text(60, 2017, "试点边界（本轮不可越线）", 14, "#29443b", "start", "bold"))
    for i, line in enumerate(BOUNDARY):
        o.append(text(60, 2043 + i * 23, line, 12, "#29443b", "start"))
    o.append(text(60, 2132, "f12「80 单 / 22% 重复澄清」为虚构样本，不作基线", 11, "#b23a2e", "start"))
    o.append(text(40, 2160, "编号 fNN = fsg-assignment-fNN｜来源 discovery-report.md｜2026-11-05", 11, "#6b7f70", "start"))
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    diamonds = sum(1 for n in NODES if n["k"] == "d")
    print(f"generated {OUT.name} | viewBox 0 0 {W} {H} | 菱形判断点 {diamonds} 个 | 节点 {len(NODES)} 个")
