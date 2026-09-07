#!/usr/bin/env python3
"""fixture が無改変であることを検査する。

実験の前提は「同じコード、同じリポジトリの状況で、プロンプトだけを変える」こと。
fixture が一度でも書き換わると、それ以降の run は過去の run と比較できなくなる。
しかも書き換わったことに気づかないまま進むのが一番まずいので、run.py は
各セルの実行前後でこれを呼び、NG なら run 全体を中断する。

メンター定義（.claude/）は .git/info/exclude でローカル除外してあるため、
git からは見えない。よって「porcelain が空」がそのまま「無改変」を意味する。

使い方:
    python experiments/verify-fixture.py [--sha <expected>]

終了コード: 無改変なら 0、汚染されていれば 1
"""

import argparse
import io
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "experiments", "fixture")
PINNED_SHA = "913c103e062e05d23dfa78c980d83a65d1e3f1c1"
AGENT_REL = os.path.join(".claude", "agents", "learn.md")


def git(*args):
    return subprocess.run(
        ["git", "-C", FIXTURE] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def check(expected_sha):
    problems = []

    if not os.path.isdir(os.path.join(FIXTURE, ".git")):
        return ["fixture が存在しません: %s" % FIXTURE]

    head = git("rev-parse", "HEAD").stdout.strip()
    if head != expected_sha:
        problems.append("HEAD が固定 SHA と違います\n    期待: %s\n    実際: %s" % (expected_sha, head))

    # 追跡ファイルの変更・未追跡ファイルの両方を拾う。
    # .claude/ は .git/info/exclude 済みなので、ここに出てきたら除外設定が壊れている。
    porcelain = git("status", "--porcelain").stdout
    if porcelain.strip():
        problems.append("作業ツリーが汚れています:\n" + "\n".join(
            "    " + line for line in porcelain.rstrip().split("\n")))

    # porcelain は staged/unstaged を拾うが、念のため HEAD との差分も直接見る
    if git("diff", "--quiet", "HEAD").returncode != 0:
        problems.append("HEAD との差分があります（git diff HEAD が非空）")

    # メンター定義が消えていたら run は成立しない（別種の事故だが、ここで止めたい）
    if not os.path.exists(os.path.join(FIXTURE, AGENT_REL)):
        problems.append("メンター定義がありません: %s" % AGENT_REL)

    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default=PINNED_SHA, help="期待する commit SHA")
    ap.add_argument("--quiet", action="store_true", help="OK のときは何も出さない")
    args = ap.parse_args()

    problems = check(args.sha)
    if problems:
        print("NG   fixture が無改変ではありません")
        for p in problems:
            print("  - " + p)
        print("\n実験の前提が崩れています。run を続けないでください。")
        return 1

    if not args.quiet:
        print("OK   fixture は無改変です（%s）" % args.sha[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
