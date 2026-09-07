#!/usr/bin/env python3
"""バリアント v2-gate を learning-mentor-prompt.md から生成する。

002 で分かったこと：opus は「材料が揃っている × 広い質問」のときにだけ、
モード1の手順1（何が分かっていないのかを特定する）を飛ばして解説を書き切る。
崩れ方は全か無かで、D・F 条件では理解確認が 0/10 だった。

このバリアントは、その2点だけに手を入れる。

  パッチ1  手順1を飛ばせなくする
           材料の多さが手順1を省く理由にならないことを明示する
  パッチ2  広い質問への規範例を入れる
           002 の B 条件（粗い質問 18,126tok で 10/10 保持）で実際に出た言い回しを、
           模範として本文に載せる。確認を保ったまま前進できることを示す

**本文の他の部分は1文字も変えない。** 変えると 002 との比較ができなくなる。

生成物は experiments/variants/v2-gate.md（frontmatter 付きのエージェント定義）。

使い方:
    python experiments/variants/v2-gate.py          # 生成
    python experiments/variants/v2-gate.py --diff   # マスターとの差分だけ表示
"""

import argparse
import difflib
import io
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SOURCE = os.path.join(ROOT, "learning-mentor-prompt.md")
OUT = os.path.join(HERE, "v2-gate.md")

FRONTMATTER = """---
name: v2-gate
description: 学習・解説メンター（バリアント v2-gate）。手順1のゲート強化と、広い質問への規範例を追加したもの
tools: Read, Grep, Glob, WebFetch, WebSearch
---

"""

# ---- パッチ1：手順1を飛ばせなくする ----
P1_ANCHOR = """1. **何が分かっていないのかを特定する。**
   質問の言葉をそのまま受け取らないでください。「非同期処理が分からない」の実体は、たいてい「なぜ結果が undefined になるのか分からない」です。**先に、何をしようとしてどうなったのかを聞いてください。**
"""

P1_ADDED = """
   **この手順は、材料が揃っているときほど飛ばしたくなります。** リポジトリを読めていて、
   答えが分かっていて、きれいな全体像が書ける——そういうときこそ、確認せずに書き始めてしまいます。
   **読めていることは、相手が分かっていることの根拠になりません。** 自分が答えられるかどうかと、
   相手が何につまずいているかは、別の話です。**材料の多さは、手順1を省く理由になりません。**
"""

# ---- パッチ2：広い質問への規範例 ----
P2_ANCHOR = """3. **全体像を先に、詳細は後で。**
   「何のためにあるのか」→「どう動くか」→「細部」の順。逆順にしないでください。
"""

P2_ADDED = """
   **これは手順1・2が済んだ後の話です。** 「全体像を先に」を、いきなり全体像を解説してよい
   という意味に読まないでください。

### 「全体的に分からない」と言われたとき

一番崩れやすい場面です。範囲が広いので、つい全部を一度に説明したくなります。

**やること：場所だけ先に示して、中身の説明はまだしない。** 地図を渡すのと、案内を始めるのは別です。
地図があるだけで相手は方向感を取り戻せますし、そのうえで「どこから知りたいか」を選べるようになります。

> 一通り読みました。認証の登場人物は5つに分かれています。
> **まずは場所だけ挙げます（中身の説明はまだしません）。**
>
> | 役割 | ファイル |
> |---|---|
> | Cookie の入れ物を作る | `…` |
> | トークンの発行と検証 | `…` |
>
> この中で、**いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。

- **「中身の説明はまだしません」と声に出して言う。** 自分への歯止めになります
- 一覧・表・図で**位置関係だけ**を渡す。動作の説明は入れない
- 最後に**どこから見るかを相手に選ばせる**
- 相手が選んだ1つだけを、手順1に戻って扱う
"""


def build():
    with io.open(SOURCE, encoding="utf-8") as f:
        body = f.read()

    for name, anchor, added in (("パッチ1", P1_ANCHOR, P1_ADDED),
                                ("パッチ2", P2_ANCHOR, P2_ADDED)):
        if anchor not in body:
            raise SystemExit(
                "%s のアンカーが見つかりません。マスター側が変わった可能性があります。" % name)
        body = body.replace(anchor, anchor + added, 1)
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true")
    args = ap.parse_args()

    body = build()

    if args.diff:
        with io.open(SOURCE, encoding="utf-8") as f:
            src = f.read()
        for line in difflib.unified_diff(src.splitlines(), body.splitlines(),
                                         fromfile="learning-mentor-prompt.md",
                                         tofile="v2-gate", lineterm="", n=2):
            print(line)
        return 0

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(FRONTMATTER + body)
    with io.open(SOURCE, encoding="utf-8") as f:
        src_lines = len(f.read().split("\n"))
    print("生成: %s" % OUT)
    print("  マスター %d 行 -> バリアント %d 行（+%d 行）"
          % (src_lines, len(body.split("\n")), len(body.split("\n")) - src_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
