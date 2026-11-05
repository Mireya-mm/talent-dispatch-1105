# -*- coding: utf-8 -*-
"""从 source/discovery-report.md 的「访谈记录」章节生成 md / json / csv 三种格式。

仅依赖 Python 标准库。输出覆盖仓库根目录下对应文件。
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "discovery-report.md"

ROLES = {
    "r0": ("顾明岚", "服务业务负责人"),
    "r1": ("林亦舟", "派遣项目服务专员"),
    "r2": ("唐映秋", "到岗与班次协调员"),
    "r3": ("秦芮", "数据与系统工程师"),
    "r4": ("傅景", "质量复核负责人"),
    "r5": ("叶书", "客户现场负责人"),
}

LINE = re.compile(r"^- (\S+) (访谈者|fsg-assignment-(r\d))：(.+)$")
EVIDENCE = re.compile(r"\[(fsg-assignment-f\d+)\]")


def parse():
    text = SRC.read_text(encoding="utf-8")
    block = text.split("## 访谈记录", 1)[1].split("## 公开业务来源", 1)[0]
    records, pending = [], None
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = LINE.match(line)
        if not m:
            continue
        ts, who, body = m.group(1), m.group(2), m.group(4)
        if who == "访谈者":
            pending = {"time": ts, "question": body}
            continue
        rid = who.split("-")[-1]
        name, title = ROLES.get(rid, ("未知", "未知"))
        records.append({
            "seq": len(records) + 1,
            "time": pending["time"],
            "role_id": rid,
            "name": name,
            "title": title,
            "question": pending["question"],
            "answer": body,
            "evidence": EVIDENCE.findall(body),
        })
    return records


def write_markdown(records):
    out = [
        "# 访谈记录 · 派遣岗位需求与到岗交接",
        "",
        "- 案例：上海外服（集团）有限公司 · 派遣岗位需求与到岗交接",
        "- 资料性质：合成演练访谈事实，需求为待验证假设",
        "- 采集覆盖：36/36（100%）；覆盖率不等于需求确认或验收通过",
        "- 来源：`source/discovery-report.md`「访谈记录」章节，原样转录",
        f"- 问答条目：{len(records)} 条（含同题重复提问，按原始记录保留）",
        "",
        "> 编号说明：回答中的 `[fsg-assignment-fNN]` 为访谈事实证据编号；其余文档统一简写为 `fNN`。",
        "",
    ]
    for r in records:
        out += [
            f'## {r["seq"]:02d} · {r["title"]}（{r["name"]}）',
            "",
            f'- 时间：{r["time"]}',
            f'- 角色编号：fsg-assignment-{r["role_id"]}',
            f'- 提问：{r["question"]}',
            "",
            "**回答（原文）**",
            "",
            r["answer"],
            "",
            "- 关联证据：" + ("、".join(f"`{e}`" for e in r["evidence"]) if r["evidence"] else "无"),
            "",
        ]
    (ROOT / "访谈记录.md").write_text("\n".join(out), encoding="utf-8")


def write_json(records):
    payload = {
        "case": "上海外服（集团）有限公司 · 派遣岗位需求与到岗交接",
        "nature": "合成演练访谈事实；需求为待验证假设",
        "coverage": "36/36",
        "source": "source/discovery-report.md / 访谈记录",
        "record_count": len(records),
        "records": [
            {
                "seq": r["seq"], "time": r["time"], "role_id": r["role_id"],
                "name": r["name"], "title": r["title"],
                "question": r["question"], "answer": r["answer"],
                "evidence_ids": r["evidence"],
            }
            for r in records
        ],
    }
    (ROOT / "访谈记录.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_csv(records):
    with (ROOT / "访谈记录.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "时间", "角色编号", "姓名", "职能", "提问", "回答原文", "证据编号", "资料性质"])
        for r in records:
            w.writerow([
                r["seq"], r["time"], "fsg-assignment-" + r["role_id"],
                r["name"], r["title"], r["question"], r["answer"],
                " ".join(r["evidence"]), "合成演练·待验证",
            ])


if __name__ == "__main__":
    recs = parse()
    write_markdown(recs)
    write_json(recs)
    write_csv(recs)
    print(f"generated {len(recs)} interview records -> 访谈记录.md / .json / .csv")
