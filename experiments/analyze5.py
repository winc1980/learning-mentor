#!/usr/bin/env python3
"""反復のある run を条件ごとに集計する（002 以降）。

n=1 用の analyze.py と違い、こちらは条件ごとに中央値と範囲を出す。
効果を主張してよいのは条件間で範囲が重ならないときだけ。

**run を並べたら、本文が同じかを先に照合する。** 条件の差を読む前に、その差が
プロンプトの差でないことを確かめる必要がある（#43）。判定は prompt_version.py。

使い方:
    python experiments/analyze5.py 002-opus-n5
    python experiments/analyze5.py 012-sonnet-path2 013-opus-path2   # 並べる
"""

import argparse
import io
import json
import os
import sys
from statistics import median

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompt_version

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "experiments", "runs")

LBL = {("none", "fine"): "A", ("none", "coarse"): "B",
       ("single_file", "fine"): "C", ("single_file", "coarse"): "D",
       ("repo_sweep", "fine"): "E", ("repo_sweep", "coarse"): "F"}
ORDER = [("none", "fine"), ("single_file", "fine"), ("none", "coarse"),
         ("single_file", "coarse"), ("repo_sweep", "fine"), ("repo_sweep", "coarse")]


def load(spec_id):
    path = os.path.join(RUNS, spec_id, "judgments.jsonl")
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def rng(vals):
    return "%g-%g" % (min(vals), max(vals)) if vals else "-"


def report(spec_id):
    rows = load(spec_id)
    judges = sorted(set(r["judge"] for r in rows))

    # ---- 採点者間の一致 ----
    cells = {}
    for r in rows:
        cells.setdefault(r["cell"], []).append(r)
    print("== 採点者間の一致（%s） ==\n" % " vs ".join(judges))
    if len(judges) == 2:
        a, b = judges
        for field in ("人格残存度", "最初の問い", "理解確認が先行", "完成コード相当", "モード"):
            agree = tot = 0
            near = 0
            for cell, js in cells.items():
                va = next((j.get(field) for j in js if j["judge"] == a), None)
                vb = next((j.get(field) for j in js if j["judge"] == b), None)
                if va is None or vb is None:
                    continue
                tot += 1
                if va == vb:
                    agree += 1
                elif field == "人格残存度" and abs(va - vb) <= 1:
                    near += 1
            extra = "（±1 以内を含めると %d/%d）" % (agree + near, tot) if near else ""
            print("  %-12s 一致 %d/%d %s" % (field, agree, tot, extra))
    print()

    # ---- 条件ごとの集計 ----
    by_cond = {}
    for r in rows:
        by_cond.setdefault((r["context_load"], r["probe_grain"]), []).append(r)

    print("== 条件ごとの人格残存度（採点者2名 × 5反復 = 10判定） ==\n")
    print("%-3s %-12s %-7s %10s %8s %6s %7s  %s"
          % ("lbl", "load", "grain", "ctx中央", "ctx範囲", "人格中央", "人格範囲", "分布"))
    print("-" * 92)
    for k in ORDER:
        rs = by_cond.get(k, [])
        if not rs:
            continue
        ctx = [r["開始時コンテキストtok"] for r in rs]
        sc = [r["人格残存度"] for r in rs]
        dist = {}
        for v in sc:
            dist[v] = dist.get(v, 0) + 1
        ds = " ".join("%d:%d" % (v, dist[v]) for v in sorted(dist, reverse=True))
        print("%-3s %-12s %-7s %10d %8s %6g %7s  %s"
              % (LBL[k], k[0], k[1], median(ctx), rng(ctx), median(sc), rng(sc), ds))

    # ---- 量 vs 粒度の分離：ctx 帯が重なる D と E を直接比べる ----
    print("\n== 量と粒度の分離：ctx 帯が重なる D(coarse) と E(fine) ==\n")
    d = by_cond.get(("single_file", "coarse"), [])
    e = by_cond.get(("repo_sweep", "fine"), [])
    if d and e:
        print("  D  ctx %s  人格 中央%g  分布%s"
              % (rng([r["開始時コンテキストtok"] for r in d]),
                 median([r["人格残存度"] for r in d]),
                 sorted([r["人格残存度"] for r in d])))
        print("  E  ctx %s  人格 中央%g  分布%s"
              % (rng([r["開始時コンテキストtok"] for r in e]),
                 median([r["人格残存度"] for r in e]),
                 sorted([r["人格残存度"] for r in e])))
        print("\n  ctx が同水準で粒度だけ逆。差が小さければ量依存、大きければ粒度依存。")

    # ---- 用量反応：全30セルを ctx でビン分けする ----
    print("\n== 用量反応（条件を無視し、実測 ctx だけでビン分け） ==\n")
    bins = [(0, 12000), (12000, 16000), (16000, 20000), (20000, 24000), (24000, 10 ** 9)]
    print("  %-16s %5s %8s %8s" % ("ctx帯", "件数", "人格中央", "人格範囲"))
    for lo, hi in bins:
        sel = [r for r in rows if lo <= r["開始時コンテキストtok"] < hi]
        if not sel:
            continue
        sc = [r["人格残存度"] for r in sel]
        name = "%d-%d" % (lo, hi) if hi < 10 ** 9 else "%d+" % lo
        print("  %-16s %5d %8g %8s" % (name, len(sel), median(sc), rng(sc)))


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
