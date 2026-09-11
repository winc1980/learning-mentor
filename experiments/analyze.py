#!/usr/bin/env python3
"""judgments.jsonl と metrics.csv を条件ごとに集計する。

n が小さいうちは検定も平均も出さない。素の値を並べ、採点者間の一致だけを見る。
採点者が割れている項目は、条件の効果ではなくルーブリックの問題である可能性が高い。

**run を並べたら、本文が同じかを先に照合する。** 条件の差を読む前に、その差が
プロンプトの差でないことを確かめる必要がある（#43）。判定は prompt_version.py。

使い方:
    python experiments/analyze.py 001-context-dilution
    python experiments/analyze.py 012-sonnet-path2 013-opus-path2   # 並べる
"""

import argparse
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompt_version

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "experiments", "runs")


def load(spec_id):
    path = os.path.join(RUNS, spec_id, "judgments.jsonl")
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def by_cell(rows):
    d = {}
    for r in rows:
        d.setdefault(r["cell"], []).append(r)
    return d


def report(spec_id):
    rows = load(spec_id)
    cells = by_cell(rows)
    judges = sorted(set(r["judge"] for r in rows))

    # ---- 採点者間の一致 ----
    print("== 採点者間の一致（%s） ==\n" % " vs ".join(judges))
    if len(judges) == 2:
        a, b = judges
        for field in ("人格残存度", "最初の問い", "理解確認が先行", "完成コード相当", "モード"):
            agree = tot = 0
            diffs = []
            for cell, js in cells.items():
                va = next((j.get(field) for j in js if j["judge"] == a), None)
                vb = next((j.get(field) for j in js if j["judge"] == b), None)
                if va is None or vb is None:
                    continue
                tot += 1
                if va == vb:
                    agree += 1
                else:
                    diffs.append("%s(%s/%s)" % (cell.replace("__r1", ""), va, vb))
            if tot:
                print("  %-12s 一致 %d/%d" % (field, agree, tot))
                if diffs:
                    print("      不一致: %s" % "  ".join(diffs[:6]))
        print()

    # ---- 条件ごとの人格残存度 ----
    print("== 人格残存度（採点者ごと） ==\n")
    hdr = "%-5s %-7s %-12s %-7s %8s" % ("lbl", "model", "load", "grain", "ctx")
    for j in judges:
        hdr += " %8s" % j.replace("judge-", "J:")
    hdr += " %9s" % "問返密度"
    print(hdr)
    print("-" * len(hdr))

    order = sorted(cells, key=lambda c: (0 if "sonnet" in c else 1,
                                         ["none", "single_file", "repo_sweep"].index(
                                             cells[c][0]["context_load"]),
                                         cells[c][0]["probe_grain"]))
    prev_model = None
    for cell in order:
        js = cells[cell]
        r = js[0]
        if prev_model and r["model"] != prev_model:
            print()
        prev_model = r["model"]
        line = "%-5s %-7s %-12s %-7s %8s" % (
            r.get("label", ""), r["model"], r["context_load"], r["probe_grain"],
            r.get("開始時コンテキストtok"))
        for jd in judges:
            v = next((x.get("人格残存度") for x in js if x["judge"] == jd), "-")
            line += " %8s" % v
        line += " %9s" % r.get("問い返し密度")
        print(line)

    # ---- 問いなし率 ----
    print("\n== 「問いなし」と判定された条件 ==\n")
    for cell in order:
        js = cells[cell]
        vals = [x.get("最初の問い") for x in js]
        if any(v == "問いなし" for v in vals):
            r = js[0]
            print("  %-6s %-7s %-12s %-7s  判定=%s"
                  % (r.get("label"), r["model"], r["context_load"],
                     r["probe_grain"], "/".join(str(v) for v in vals)))

    # ---- 完成コード相当 ----
    print("\n== 「完成コード相当」と判定された条件 ==\n")
    hit = False
    for cell in order:
        js = cells[cell]
        vals = [x.get("完成コード相当") for x in js]
        if any(vals):
            hit = True
            r = js[0]
            print("  %-6s %-7s %-12s %-7s  判定=%s"
                  % (r.get("label"), r["model"], r["context_load"],
                     r["probe_grain"], "/".join(str(v) for v in vals)))
    if not hit:
        print("  なし")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec_id", nargs="+",
                    help="集計する run。2つ以上並べると、先に本文が同じかを照合する")
    args = ap.parse_args()

    # 並べた時点で必ず通る。自己申告（report.md に「002 と比較」と書く）ではなく、
    # 記録されたハッシュで判定する（#43）。
    ok = prompt_version.warn_if_mixed(args.spec_id)

    for spec_id in args.spec_id:
        if len(args.spec_id) > 1:
            print("=" * 72)
            print("== %s ==" % spec_id)
            print("=" * 72 + "\n")
        else:
            print(prompt_version.describe(prompt_version.of_run(spec_id)) + "\n")
        report(spec_id)
        print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
