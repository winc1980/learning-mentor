#!/usr/bin/env python3
"""fixture の場所を決め、被験体の文脈に何が入るかを検査する。

**fixture はリポジトリの外に置く。** `experiments/fixture` に置くと、cwd の祖先に
あるこのリポジトリの `CLAUDE.md` が被験体のプロジェクト指示として読み込まれる。
規定が守られるかを測る実験で、被験体に規定の解説を渡すことになる（issue #42）。

これは `verify-fixture.py` では捕まらない。あちらは fixture の**中身**しか見ない。
fixture が無改変のまま、外から文脈だけが混入する。実際 008 では 40 セル全部が
無改変チェックを通り、`repo_sweep` 水準がたまたま親リポジトリの構成を
説明し始めたことでようやく気づいた。他の水準では応答からは分からない。

そのため `run.py` は毎 run の preflight で `claude_md_in_scope()` を呼び、
拾われうる CLAUDE.md が1つでもあれば run を始めない。
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# worktree ごとに別 fixture を使いたいときは MENTOR_FIXTURE で上書きする。
# 既定では全 worktree が同じ fixture を共有する（読むだけなので競合しない）。
ENV_VAR = "MENTOR_FIXTURE"
DEFAULT = os.path.join(os.path.dirname(ROOT), "learning-mentor-fixture")


def resolve():
    """被験体が読むリポジトリの絶対パス。"""
    env = os.environ.get(ENV_VAR)
    return os.path.abspath(env) if env else DEFAULT


def claude_md_in_scope(fixture=None):
    """その cwd で被験体が読み込みうる CLAUDE.md を全部返す。

    Claude Code は cwd から祖先を遡って CLAUDE.md を探し、さらにユーザー
    グローバルのメモリ（~/.claude/CLAUDE.md）も読む。`--setting-sources project`
    は settings.json の話であって、CLAUDE.md の探索は止められない。
    """
    fixture = fixture or resolve()
    found = []

    d = os.path.abspath(fixture)
    while True:
        p = os.path.join(d, "CLAUDE.md")
        if os.path.isfile(p):
            found.append(p)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    user = os.path.join(os.path.expanduser("~"), ".claude", "CLAUDE.md")
    if os.path.isfile(user):
        found.append(user)

    return found
