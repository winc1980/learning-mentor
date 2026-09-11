#!/usr/bin/env python3
"""その run が「どの本文で走ったか」を記録し、run 同士が比較可能かを機械的に判定する。

**検査していなかったのは、本文とコピーの一致ではなく、本文どうしの一致だった。**
`check-sync.ts` は本文と 3 箇所のコピーが揃っていることを保証し、`run.py` は毎回
それを通す。だからどの run も「本文と同期した learn.md」で走っていて、検査は全部通る。
通らない検査が無いので、**本文が違う run を並べてもエラーは出ない。出るのは、
比較した結果の解釈だけが静かに間違うという形**（issue #43）。

013 で実際に起きた。012（sonnet）を 002（opus）の対照として設計したが、その間に
`a398e78`（v2-gate の本文取り込み）と `35d7e59`（L3/L4 入れ替え）が入っていて、
モデルとプロンプトの両方が違っていた。気づいたのは応答文字数の並びに違和感を
持ったからで、仕組みが教えてくれたわけではない。

## 何を同一性とするか

- **配布本文** = `learning-mentor-prompt.md` の内容ハッシュ
- **被験体本文** = 被験体が実際に読んだ本文。`agent_variant` を使った run では
  バリアントの本文、使っていなければ配布本文と同じ

比較の可否を決めるのは**被験体本文**のほう。配布本文だけ見ていると、同じ本文から
派生したバリアント同士を「同じ」と誤認する。

ハッシュは `bun check-sync.ts --hash` に取らせる。正規化（改行・行末空白・更新用
マーカーの吸収）の規則を Python に書き写すと規則が 2 つになり、片方だけ直したときに
静かにずれる。**規則は normalize() ただ 1 つに保ち、実行系をまたいで呼ぶ。**

## 過去 run をどう扱うか

`experiments/runs/` は書き換えない規約なので、**過去 run の manifest には追記しない。**
manifest は取得時の事実の記録で、あとから git を見て推定した値を同じ場所に混ぜると、
「実行時に記録された事実」と「あとから復元した推定」の区別が消える。**区別が消えることが
この issue で直そうとしている当のもの**なので、外の対応表に由来を明示して置く
（`experiments/prompt-history.json`）。

復元の経路は 2 つ。素の本文を使った run は当時の blob を引く。バリアントを使った run は
**blob を引いてはいけない場合がある** — バリアントは生成物なので本体の更新時に作り直されて
コミットし直され、引けば値が返るのに別の本文、という状態になる（`regenerate_variant` の注記）。
その場合は当時の master と当時の生成器から作り直す。

使い方:
    python experiments/prompt_version.py                  # いまの本文の同一性
    python experiments/prompt_version.py 012 013          # 並べてよいか判定（違えば exit 1）
    python experiments/prompt_version.py --rebuild-history # 過去 run の対応表を作り直す
"""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "experiments", "runs")
HISTORY = os.path.join(ROOT, "experiments", "prompt-history.json")

SOURCE = "learning-mentor-prompt.md"

# 由来。どの run も「ハッシュがある」状態にはできるが、**どうやって得た値か**で
# 言えることが違う。推定を事実として扱わないため、必ず一緒に持ち回る。
FROM_MANIFEST = "実行時に記録"
FROM_GIT = "git復元（推定）"
FROM_REGEN = "生成器で再生成（推定）"
UNKNOWN = "不明"


# ---------------------------------------------------------------- ハッシュ

def _bun():
    bun = shutil.which("bun")
    if bun is None:
        raise SystemExit("bun が見つかりません。本文ハッシュは check-sync.ts に取らせています。")
    return bun


def _hash(args, stdin=None):
    cmd = [_bun(), os.path.join(ROOT, "check-sync.ts"), "--hash"] + args
    r = subprocess.run(cmd, input=stdin, capture_output=True,
                       encoding="utf-8", errors="replace", cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError("本文ハッシュを取れません: %s" % (r.stdout + r.stderr).strip())
    return r.stdout.strip()


def hash_file(relpath, agent_body=False):
    """作業ツリーのファイルの本文ハッシュ。"""
    args = (["--agent-body"] if agent_body else []) + [relpath]
    return _hash(args)


def hash_blob(commit, relpath, agent_body=False):
    """git の中にある過去のファイルの本文ハッシュ。無ければ None。"""
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (commit, relpath)],
                       capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return None
    args = (["--agent-body"] if agent_body else []) + ["-"]
    return _hash(args, stdin=r.stdout)


# ---------------------------------------------------------------- git

def _git(*args):
    r = subprocess.run(["git", "-C", ROOT] + list(args),
                       capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def last_commit_before(relpath, when_iso):
    """その時刻より前に relpath を最後に触ったコミット。無ければ None。

    `--until` は committer date で切る。このリポジトリの履歴では author date と
    一致しているが、rebase の入った履歴では食い違いうる。復元が推定であることの
    一因なので、由来を FROM_GIT のまま扱うこと。
    """
    out = _git("log", "--until=" + when_iso, "-1", "--format=%H|%cI|%s",
               "--", relpath)
    if not out:
        return None
    sha, date, subject = out.split("|", 2)
    return {"commit": sha, "日時": date, "件名": subject}


def regenerate_variant(variant, master_commit, gen_commit):
    """当時の master と当時の生成器からバリアントを作り直し、本文ハッシュを返す。

    **git の blob を素直に引くと、間違った本文が返ることがある。** バリアントは
    生成物なので、本体が更新されると作り直されてコミットし直される。実際
    `a398e78` でコミットされた `v2-gate.md` は、同コミットの配布本文と本文が
    完全に一致する（v2-gate を本体に取り込んだあと、新しい本文から作り直したもの）。
    003・005・006 がその前に読んだ本文とは別物なのに、引けば値が返るので正しく見える。

    生成器は決定論的なので、当時の入力を揃えて回せば当時の出力が得られる。
    ただし**これも推定**である。生成後に手で直していれば分からない。

    復元できなければ None を返す。
    """
    name = os.path.splitext(os.path.basename(variant))[0]
    generator = os.path.join(os.path.dirname(variant), name + ".py").replace("\\", "/")

    master = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (master_commit, SOURCE)],
                            capture_output=True, encoding="utf-8", errors="replace")
    gen = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (gen_commit, generator)],
                         capture_output=True, encoding="utf-8", errors="replace")
    if master.returncode != 0 or gen.returncode != 0:
        return None

    # 生成器は自分の位置から ROOT を決める（HERE の2つ上）。その形に並べる。
    tmp = tempfile.mkdtemp(prefix="mentor-regen-")
    try:
        here = os.path.join(tmp, "experiments", "variants")
        os.makedirs(here)
        with io.open(os.path.join(tmp, "learning-mentor-prompt.md"), "w",
                     encoding="utf-8", newline="\n") as f:
            f.write(master.stdout)
        script = os.path.join(here, name + ".py")
        with io.open(script, "w", encoding="utf-8", newline="\n") as f:
            f.write(gen.stdout)

        # 履歴の中の生成器を実行する。--rebuild-history のときだけ通る道。
        r = subprocess.run([sys.executable, script], capture_output=True,
                           encoding="utf-8", errors="replace", cwd=tmp)
        out = os.path.join(here, name + ".md")
        if r.returncode != 0 or not os.path.exists(out):
            return None
        return hash_file(out, agent_body=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def head_state():
    return {
        "repo_head": _git("rev-parse", "HEAD"),
        # 作業ツリーが汚れていれば HEAD だけでは本文を特定できない。ハッシュは
        # 実物から取っているので値は正しいが、「どのコミットの本文か」は言えない。
        "repo_dirty": bool(_git("status", "--porcelain")),
    }


# ---------------------------------------------------------------- いまの状態

def current(subject_agent=None, agent_variant=None):
    """いまの本文同一性。run.py が manifest に書き込む形。

    `subject_agent` には、**被験体が実際に読むファイル**を渡す
    （fixture の `.claude/agents/<agent>.md`）。ここから取れば推定が一切入らない。
    渡さなければリポジトリ側のファイルから取る（回す前の照合など、fixture に
    まだ置いていない段階で使う）。
    """
    body = hash_file(SOURCE)
    variant_hash = None
    if subject_agent:
        variant_hash = hash_file(subject_agent, agent_body=True)
    elif agent_variant:
        variant_hash = hash_file(agent_variant, agent_body=True)

    version = ""
    path = os.path.join(ROOT, "VERSION")
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as f:
            version = f.read().strip()

    identity = {
        "配布本文sha256": body,
        "被験体本文sha256": variant_hash or body,
        "被験体本文の出どころ": subject_agent or agent_variant or SOURCE,
        "バリアント": agent_variant,
        "VERSION": version,
        "正規化": "bun check-sync.ts --hash（normalize() と同一規則）",
        "由来": FROM_MANIFEST,
    }
    identity.update(head_state())
    return identity


# ---------------------------------------------------------------- run の同一性

def _run_dir(run_id):
    """`012` のような前方一致でも引けるようにする（analyze.py の呼び方に合わせる）。"""
    if os.path.isdir(os.path.join(RUNS, run_id)):
        return run_id
    hits = [d for d in sorted(os.listdir(RUNS)) if d.startswith(run_id)]
    return hits[0] if len(hits) == 1 else None


def _load_history():
    if not os.path.exists(HISTORY):
        return {}
    with io.open(HISTORY, encoding="utf-8") as f:
        return json.load(f).get("runs", {})


def of_run(run_id):
    """run の本文同一性。manifest に記録があればそれ、無ければ対応表から。"""
    full = _run_dir(run_id) or run_id
    manifest = os.path.join(RUNS, full, "manifest.json")
    if os.path.exists(manifest):
        with io.open(manifest, encoding="utf-8") as f:
            m = json.load(f)
        if m.get("本文"):
            d = dict(m["本文"])
            d["run"] = full
            if d.get("途中で変わった"):
                # セルごとに違う本文で走った run。ハッシュは 1 つに定まらないので、
                # 「本文が同じ」と判定させてはいけない。
                d["被験体本文sha256"] = None
                d["由来"] = UNKNOWN
                d["理由"] = "run の途中で本文が変わっています（セルごとに違う本文）"
            return d

    hist = _load_history().get(full)
    if hist:
        d = dict(hist)
        d["run"] = full
        return d

    return {"run": full, "被験体本文sha256": None, "配布本文sha256": None,
            "由来": UNKNOWN, "理由": "manifest にも対応表にも記録がありません"}


def _short(h):
    return h[:12] if h else "????????????"


def describe(identity):
    """1 行で。ハッシュだけでなく由来まで出す（推定を事実に見せないため）。"""
    origin = identity.get("由来", UNKNOWN)
    # 不明な run に復元元コミットを添えない。特定できたように見えてしまう
    # （不明なのはバリアント側で、配布本文のほうは復元できている、という状態がある）。
    src = (identity.get("本文の出どころ") or {}) if origin != UNKNOWN else {}
    where = src.get("commit", "")[:7]
    tail = "%s%s" % (origin, " / " + where if where else "")
    variant = identity.get("バリアント")
    return "%-22s %s  (%s)%s" % (identity.get("run", "-"),
                                 _short(identity.get("被験体本文sha256")),
                                 tail,
                                 "  variant=%s" % os.path.basename(variant) if variant else "")


def compare(run_ids):
    """並べてよいかを判定する。(問題なし?, 表示する行) を返す。"""
    ids = [of_run(r) for r in run_ids]
    lines = ["== 並べた run の本文 ==", ""]
    lines += ["  " + describe(i) for i in ids]
    lines.append("")

    unknown = [i for i in ids if not i.get("被験体本文sha256")]
    hashes = set(i["被験体本文sha256"] for i in ids if i.get("被験体本文sha256"))

    if unknown:
        lines.append("!! 本文を特定できない run があります: %s"
                     % ", ".join(i["run"] for i in unknown))
        for i in unknown:
            if i.get("理由"):
                lines.append("     %s — %s" % (i["run"], i["理由"]))
        lines.append("   比較可能かどうかを判定できません。結論は保留すること。")
        return False, lines

    if len(hashes) > 1:
        lines.append("!! 本文の違う run を並べています。")
        lines.append("   条件の差とプロンプトの差が分離できません（issue #43 / 013 で実際に起きた）。")
        lines.append("   同条件の対照を現行本文で取り直すか、報告に本文が違うことを明記すること。")
        return False, lines

    lines.append("OK 本文は同一です。条件の差として読めます。")
    return True, lines


def warn_if_mixed(run_ids, out=None):
    """呼び出し側（analyze.py など）から使う。並べた時点で必ず通る道に置くこと。"""
    if len(run_ids) < 2:
        return True
    ok, lines = compare(run_ids)
    print("\n".join(lines), file=out or sys.stdout)
    print("", file=out or sys.stdout)
    return ok


# ---------------------------------------------------------------- 対応表の再生成

def rebuild_history():
    """過去 run の本文を git から復元して対応表に書く。復元できないものは不明と書く。

    manifest の実行日時より前に、その経路を最後に触ったコミットを本文とみなす。
    **これは推定である。** 作業ツリーに未コミットの変更があった状態で回した run の
    本文は、git からは復元できない。由来を FROM_GIT のまま残すのはそのため。
    """
    runs = {}
    for run_id in sorted(os.listdir(RUNS)):
        manifest = os.path.join(RUNS, run_id, "manifest.json")
        if not os.path.isdir(os.path.join(RUNS, run_id)) or not os.path.exists(manifest):
            continue
        with io.open(manifest, encoding="utf-8") as f:
            m = json.load(f)

        if m.get("本文"):
            # 実行時に記録された run。対応表は要らない（of_run が manifest を優先する）。
            continue

        when = m.get("実行日時")
        entry = {"実行日時": when, "バリアント": m.get("agent_variant")}

        if not when:
            entry.update({"配布本文sha256": None, "被験体本文sha256": None,
                          "由来": UNKNOWN, "理由": "manifest に実行日時がありません"})
            runs[run_id] = entry
            continue

        src = last_commit_before(SOURCE, when)
        entry["配布本文sha256"] = hash_blob(src["commit"], SOURCE) if src else None
        entry["本文の出どころ"] = src

        variant = m.get("agent_variant")
        if not variant:
            entry["被験体本文sha256"] = entry["配布本文sha256"]
            entry["由来"] = FROM_GIT if entry["配布本文sha256"] else UNKNOWN
            if not entry["配布本文sha256"]:
                entry["理由"] = "実行日時より前に %s を触ったコミットがありません" % SOURCE
        else:
            vsrc = last_commit_before(variant, when)
            vhash = hash_blob(vsrc["commit"], variant, agent_body=True) if vsrc else None
            entry["バリアントの出どころ"] = vsrc

            if vhash:
                entry["被験体本文sha256"] = vhash
                entry["由来"] = FROM_GIT
                runs[run_id] = entry
                continue

            # 003 / 005 / 006 がこれ。バリアント本文は生成器が作業ツリーに吐いたものを
            # そのまま使い、git に入ったのは run のあと（a398e78）。blob は引けないが、
            # 生成器は決定論的なので当時の入力から作り直せる。
            gen = os.path.join(os.path.dirname(variant),
                               os.path.splitext(os.path.basename(variant))[0] + ".py")
            gsrc = last_commit_before(gen.replace("\\", "/"), when)
            regen = (regenerate_variant(variant, src["commit"], gsrc["commit"])
                     if (src and gsrc) else None)
            entry["被験体本文sha256"] = regen
            if regen:
                entry["由来"] = FROM_REGEN
                entry["再生成の入力"] = {"master": src["commit"], "生成器": gsrc["commit"]}
                entry["復元の根拠"] = (
                    "実行時点で %s は git に無い（コミットは run のあと）。当時の master と"
                    "当時の生成器から作り直した。生成後に手で直していれば分からないので、"
                    "これも推定。" % variant)
            else:
                entry["由来"] = UNKNOWN
                entry["理由"] = ("実行時点で %s が git に無く、生成器からの再生成も"
                                "できませんでした" % variant)
        runs[run_id] = entry

    doc = {
        "これは何か": (
            "本文の同一性が manifest に残っていなかった時期の run（#43 より前）に"
            "ついて、当時の本文を git から復元した対応表。"),
        "runs を書き換えない理由": (
            "manifest は取得時の事実の記録。あとから推定で埋めた値を混ぜると、"
            "実行時に記録された事実と復元した推定の区別が消える。"
            "その区別が消えることが #43 で直そうとしている当のものなので、外に置く。"),
        "復元の限界": (
            "manifest の実行日時より前の最後のコミットを本文とみなす推定。"
            "未コミットの状態で回した run は復元できず、由来を「%s」とする。" % UNKNOWN),
        "生成": "python experiments/prompt_version.py --rebuild-history",
        "runs": runs,
    }
    with io.open(HISTORY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return runs


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id", nargs="*", help="並べる run（2つ以上で比較可否を判定）")
    ap.add_argument("--rebuild-history", action="store_true",
                    help="過去 run の本文を git から復元して対応表を作り直す")
    args = ap.parse_args()

    if args.rebuild_history:
        runs = rebuild_history()
        print("対応表を書きました -> %s" % HISTORY)
        for run_id, e in runs.items():
            print("  %-22s %s  (%s)" % (run_id, _short(e.get("被験体本文sha256")),
                                        e.get("由来")))
            if e.get("理由"):
                print("      %s" % e["理由"])
        return 0

    if not args.run_id:
        for k, v in current().items():
            print("%-16s %s" % (k, v))
        return 0

    if len(args.run_id) == 1:
        print(describe(of_run(args.run_id[0])))
        return 0

    ok, lines = compare(args.run_id)
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
