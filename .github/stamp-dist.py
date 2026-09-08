#!/usr/bin/env python3
"""配布物に、更新用マーカーの実バージョンを打ち込む。

リリースを作るときだけ使う。配布物には含めない。

2つのことをする。

  1. .claude/agents/learn.md（参照実装）にマーカーを足して書き出す
     リポジトリ側のファイルにはマーカーを入れていない。
     experiments/fixture/.claude/agents/learn.md は検証ハーネスが被験体として
     起動する実体で、リポジトリ側と1バイトも変わらないことが前提になっているため。
     配る瞬間にだけ足す。

  2. learning-mentor-setup.md の仮置き（vX.Y.Z）を実バージョンに置換する
     こちらはマーカーが本文に必要（AI が貼り付ける対象なので）。ただし
     バージョンを直書きすると更新のたびに古くなるので、リポジトリ側は仮置きにしてある。

使い方:
    python .github/stamp-dist.py <配布物のディレクトリ> <バージョン>
"""

import io
import os
import re
import sys

AGENT = os.path.join(".claude", "agents", "learn.md")
SETUP = "learning-mentor-setup.md"
PLACEHOLDER = "<!-- learning-mentor:begin vX.Y.Z -->"


def stamp_agent(stage, version):
    """参照実装に frontmatter を残したままマーカーを足して書き出す。"""
    with io.open(AGENT, encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
    if len(parts) < 3:
        return "NG: %s の frontmatter が閉じられていません" % AGENT
    front, body = "---%s---" % parts[1], parts[2].strip()

    out_path = os.path.join(stage, AGENT)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("%s\n<!-- learning-mentor:begin v%s -->\n%s\n<!-- learning-mentor:end -->\n"
                % (front, version, body))
    print("OK %s （マーカー v%s を付与）" % (out_path, version))
    return None


def stamp_setup(stage, version):
    """配置用プロンプトの仮置きバージョンを実バージョンに置き換える。"""
    out_path = os.path.join(stage, SETUP)
    with io.open(out_path, encoding="utf-8") as f:
        text = f.read()
    if PLACEHOLDER not in text:
        return ("NG: %s に仮置きマーカー %s がありません。"
                "本文を貼り直したときに落としていないか確認してください。"
                % (SETUP, PLACEHOLDER))
    stamped = text.replace(PLACEHOLDER, "<!-- learning-mentor:begin v%s -->" % version)
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(stamped)
    print("OK %s （仮置きを v%s に置換）" % (out_path, version))
    return None


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    stage, version = sys.argv[1], sys.argv[2]

    for error in (stamp_agent(stage, version), stamp_setup(stage, version)):
        if error:
            print(error)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
