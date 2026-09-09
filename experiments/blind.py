#!/usr/bin/env python3
"""採点用の盲検バッチを作り、採点結果を条件に突合する。

採点者に条件が見えていると、期待した方向に採点が寄る。応答本文と不透明IDだけを
渡し、条件ラベルは key.json 側に隔離しておく。

  盲検バッチを作る:  python experiments/blind.py make 001-context-dilution
  採点結果を突合する: python experiments/blind.py join 001-context-dilution
  別ルーブリックを使う: python experiments/blind.py make 007-a5-wexfine-pilot --rubric experiments/rubric-a5.md

盲検の程度について（正直に書いておく）:
  - context_load（主要因）は **完全に盲検**。採点者は loader ターンを一切見ない
  - probe_grain は **部分的に露出**。モード判定などに入力文が要るため probe 文は見せる。
    fine と coarse は文面が違うので、そこは推測できてしまう
  - model も完全に盲検
"""

import argparse
import hashlib
import io
import json
import os
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "experiments", "runs")
BATCH_SIZE = 6


def load_cells(run_dir):
    cells_dir = os.path.join(run_dir, "cells")
    out = []
    for cid in sorted(os.listdir(cells_dir)):
        done = os.path.join(cells_dir, cid, "done.json")
        if not os.path.exists(done):
            continue
        with io.open(done, encoding="utf-8") as f:
            rec = json.load(f)
        turn = rec["metrics_row"].get("turn_measured")
        if not turn:
            continue
        base = os.path.join(cells_dir, cid)
        with io.open(os.path.join(base, "response-%s.md" % turn), encoding="utf-8") as f:
            resp = f.read().strip()
        with io.open(os.path.join(base, "prompt-%s.txt" % turn), encoding="utf-8") as f:
            prompt = f.read().strip()
        out.append({"cell": cid, "response": resp, "prompt": prompt,
                    "row": rec["metrics_row"]})
    return out


def cmd_make(run_dir, spec_id, rubric_path):
    cells = load_cells(run_dir)
    if not cells:
        raise SystemExit("採点対象の応答がありません。先に run.py を実行してください。")

    for c in cells:
        c["bid"] = hashlib.sha1((spec_id + "|" + c["cell"]).encode("utf-8")).hexdigest()[:8]

    # 条件がまとまらないよう混ぜる。seed 固定で再現可能にする。
    random.Random(spec_id).shuffle(cells)

    blind_dir = os.path.join(run_dir, "blind")
    os.makedirs(blind_dir, exist_ok=True)
    for old in os.listdir(blind_dir):
        if old.startswith("batch-"):
            os.remove(os.path.join(blind_dir, old))

    with io.open(rubric_path, encoding="utf-8") as f:
        rubric = f.read()
    print("ルーブリック: %s" % os.path.relpath(rubric_path, ROOT))
    if "| **5** | — |" in rubric:
        print("警告: rubric.md の人格残存度の段がまだ埋まっていません。")
        print("      このまま採点すると、最重要スコアの基準が採点者任せになります。\n")

    batches = [cells[i:i + BATCH_SIZE] for i in range(0, len(cells), BATCH_SIZE)]
    for n, batch in enumerate(batches, 1):
        path = os.path.join(blind_dir, "batch-%02d.md" % n)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(rubric)
            f.write("\n\n---\n\n# 採点対象（%d 件）\n" % len(batch))
            for c in batch:
                f.write("\n## ID: %s\n\n### 相手の発言\n\n```\n%s\n```\n"
                        % (c["bid"], c["prompt"]))
                f.write("\n### メンターの応答\n\n```\n%s\n```\n" % c["response"])
        print("  %s （%d 件）" % (path, len(batch)))

    key = dict((c["bid"], c["cell"]) for c in cells)
    with io.open(os.path.join(blind_dir, "key.json"), "w",
                 encoding="utf-8", newline="\n") as f:
        json.dump(key, f, ensure_ascii=False, indent=2)
    print("\n%d バッチ / %d 件。key.json は採点者に渡さないこと。"
          % (len(batches), len(cells)))


def cmd_join(run_dir, spec_id):
    """blind/judgments-raw/*.json（採点者の出力）を条件に戻して結合する。"""
    blind_dir = os.path.join(run_dir, "blind")
    raw_dir = os.path.join(blind_dir, "judgments-raw")
    if not os.path.isdir(raw_dir):
        raise SystemExit("採点結果がありません。%s に採点者の JSON を置いてください。" % raw_dir)

    with io.open(os.path.join(blind_dir, "key.json"), encoding="utf-8") as f:
        key = json.load(f)
    rows = dict((c["cell"], c["row"]) for c in load_cells(run_dir))

    judged = []
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.endswith(".json"):
            continue
        # judge-F.part1.json / judge-F.part2.json のように分割して書き出しても
        # 同一採点者として扱う（1エージェントで30件は落ちやすいため分割する）。
        judge = os.path.basename(fn).split(".")[0]
        with io.open(os.path.join(raw_dir, fn), encoding="utf-8") as f:
            for item in json.load(f):
                bid = item.get("id")
                cell = key.get(bid)
                if cell is None:
                    print("警告: 未知のID %r（%s）" % (bid, fn))
                    continue
                r = rows.get(cell, {})
                # 条件列は spec の要因名がそのまま入るので、決め打ちせず
                # metrics 行を丸ごと持ってくる（採点結果のキーは上書きしない）。
                merged = dict((k, v) for k, v in r.items() if k not in item)
                for drop in ("session_id", "cell", "judge"):
                    merged.pop(drop, None)
                judged.append(dict(item, cell=cell, judge=judge, **merged))

    out = os.path.join(run_dir, "judgments.jsonl")
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        for j in judged:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")

    judges = sorted(set(j["judge"] for j in judged))
    print("%d 件を突合（採点者 %d 名: %s） -> %s"
          % (len(judged), len(judges), ", ".join(judges), out))
    for jd in judges:
        missing = set(key.values()) - set(j["cell"] for j in judged if j["judge"] == jd)
        if missing:
            print("  %s の未採点: %s" % (jd, ", ".join(sorted(missing))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["make", "join"])
    ap.add_argument("spec_id")
    ap.add_argument("--rubric", default="experiments/rubric.md",
                     help="make で使うルーブリック（既定: experiments/rubric.md）")
    args = ap.parse_args()

    run_dir = os.path.join(RUNS, args.spec_id)
    if not os.path.isdir(run_dir):
        raise SystemExit("run がありません: %s" % run_dir)

    if args.cmd == "make":
        cmd_make(run_dir, args.spec_id, os.path.join(ROOT, args.rubric))
    else:
        cmd_join(run_dir, args.spec_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
