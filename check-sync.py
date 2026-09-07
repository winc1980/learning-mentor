#!/usr/bin/env python3
"""役割定義の本文が、コピー先とずれていないか確認する。

`learning-mentor-prompt.md` が唯一のソース。本文はほかに2箇所へコピーされている。

  1. learning-mentor-setup.md の「--- ここから下が本文 ---」以降（配置用プロンプトに埋め込む用）
  2. .claude/agents/learn.md の frontmatter 以降（`claude --agent learn` 用の参照実装）
  3. experiments/fixture/.claude/agents/learn.md（検証ハーネスが被験体として起動する実体）

本体を更新したあと、このスクリプトを実行してコピー先の貼り直し漏れを検出する。

使い方:
    python3 check-sync.py

終了コード: 一致していれば 0、ずれていれば 1
"""

import difflib
import io
import os
import re
import sys

# Windows のコンソールは既定が UTF-8 でないことがあり、日本語が化ける
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE = "learning-mentor-prompt.md"

SETUP = "learning-mentor-setup.md"
SETUP_MARKER = "--- ここから下が本文 ---"

AGENT = os.path.join(".claude", "agents", "learn.md")

# 検証ハーネスが fixture 内に置くコピー。fixture 自体は git 管理外だが、
# 本体を更新したときの貼り直し漏れはここでも起きる。しかもここでずれると
# 「途中でメンターのプロンプトが変わった run」という最悪の事故になるため、
# experiments/run.py は起動時にこの検査を通してから実行する。
FIXTURE_AGENT = os.path.join("experiments", "fixture", ".claude", "agents", "learn.md")


def read(relpath):
    path = os.path.join(ROOT, relpath)
    if not os.path.exists(path):
        return None
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def normalize(text):
    """比較用に正規化する。

    改行コードの差（CRLF/LF）と行末の空白は、内容のずれではないので吸収する。
    前後の空行も、切り出し方の都合で増減するため落とす。
    """
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def extract_from_setup(text):
    """配置用プロンプトのコードフェンス内に埋め込まれた本文を取り出す。"""
    if SETUP_MARKER not in text:
        return None, "「%s」の行が見つかりません" % SETUP_MARKER
    after = text.split(SETUP_MARKER, 1)[1]
    # 本文は貼り付けプロンプトのコードフェンス内にあるので、次に現れる ``` が終端
    end = re.search(r"^```\s*$", after, re.MULTILINE)
    if not end:
        return None, "本文を閉じるコードフェンス (```) が見つかりません"
    return after[: end.start()], None


def extract_from_agent(text):
    """エージェント定義の frontmatter を取り除いて本文を取り出す。"""
    if not text.startswith("---"):
        return None, "frontmatter (先頭の ---) がありません"
    parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
    if len(parts) < 3:
        return None, "frontmatter が閉じられていません"
    return parts[2], None


def report_diff(label, expected, actual):
    diff = list(
        difflib.unified_diff(
            expected, actual, fromfile=SOURCE, tofile=label, lineterm="", n=1
        )
    )
    print("  ずれている行:")
    for line in diff[:40]:
        print("    " + line)
    if len(diff) > 40:
        print("    ... 他 %d 行" % (len(diff) - 40))


def main():
    source_text = read(SOURCE)
    if source_text is None:
        print("NG: %s が見つかりません" % SOURCE)
        return 1
    expected = normalize(source_text)

    targets = [
        (SETUP, extract_from_setup),
        (AGENT, extract_from_agent),
        (FIXTURE_AGENT, extract_from_agent),
    ]

    failed = False
    for relpath, extract in targets:
        text = read(relpath)
        if text is None:
            print("SKIP %s （ファイルが存在しません）" % relpath)
            continue

        body, err = extract(text)
        if err:
            print("NG   %s — %s" % (relpath, err))
            failed = True
            continue

        actual = normalize(body)
        if actual == expected:
            print("OK   %s （%d 行）" % (relpath, len(actual)))
        else:
            print("NG   %s — 本文が %s とずれています" % (relpath, SOURCE))
            report_diff(relpath, expected, actual)
            failed = True

    print()
    if failed:
        print("ずれがあります。%s を唯一のソースとして、コピー先を貼り直してください。" % SOURCE)
        return 1
    print("すべて一致しています。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
