#!/usr/bin/env python3
"""実験セルを実行し、決定論的な指標を算出する。

被験体は `claude -p --agent learn` のサブプロセス。学習者が実際に使う
`claude --agent learn` と同一構成にするため、サブエージェント（Agent ツール）では
起動しない。理由は learning-mentor-ops-guide.md:58 を参照。

使い方:
    python experiments/run.py experiments/specs/001-context-dilution.yaml
    python experiments/run.py <spec> --only sonnet__none__fine__r1
    python experiments/run.py <spec> --dry-run       # プロンプト展開だけ見る
    python experiments/run.py <spec> --resume-run    # 完了済みセルを飛ばして再開

spec に `compare_with: [002-opus-n5]` と書くと、回す前に「比較先と同じ本文で走るか」を
照合し、違えば run を始めない（#43）。ヘッダのコメントに「○○と比較する」と書くだけでは
誰も照合しない。実際 013 はそれで、モデルと本文の両方が違う比較になった。
"""

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixture_path
import prompt_version

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# fixture はリポジトリの外に置く（issue #42）。experiments/ の下に置くと、
# cwd の祖先にあるこのリポジトリの CLAUDE.md が被験体に渡る。場所の正は fixture_path.py。
FIXTURE = fixture_path.resolve()
RUNS = os.path.join(ROOT, "experiments", "runs")

# メンターに渡ってよいツール。learn.md の tools: と一致していなければならない。
# resume でエージェント定義が外れると素の Claude になり、実験が黙って壊れる。
# それを検出するため、毎ターンの init イベントでこの集合と照合する。
EXPECTED_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch"}

TURN_TIMEOUT_SEC = 1200


# ---------------------------------------------------------------- 前提チェック

def spec_number_conflicts(spec_path, spec):
    """同じ実験番号を名乗る spec が他のブランチに無いか。

    番号はそのまま run ディレクトリ名になる。別 worktree で同じ番号の別実験が
    走ると、取り込んだ瞬間にどちらのデータか分からなくなる。git はファイル名が
    違えば衝突として扱わないので、マージするまで誰も気づかない。
    実際に 007 で起きた（008-sonnet-worst と 007-a5-wexfine-pilot）。
    """
    base = os.path.basename(spec_path)
    stem = re.sub(r"\.ya?ml$", "", base)
    problems = []

    if spec.get("id") != stem:
        problems.append("spec の id とファイル名が違います（id=%r / ファイル=%r）。\n"
                        "    run ディレクトリは id で作られるので、ここがずれると\n"
                        "    spec と結果が対応しなくなります。" % (spec.get("id"), stem))

    m = re.match(r"(\d{3})-", stem)
    if not m:
        return problems
    num = m.group(1)

    def git_out(*args):
        r = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.stdout if r.returncode == 0 else ""

    seen = {}
    refs = [x for x in git_out("for-each-ref", "--format=%(refname:short)",
                               "refs/heads").split("\n") if x.strip()]
    for ref in refs:
        for path in git_out("ls-tree", "-r", "--name-only", ref,
                            "--", "experiments/specs/").split("\n"):
            other = os.path.basename(path.strip())
            if other.startswith(num + "-") and other != base:
                seen.setdefault(other, []).append(ref)

    for other, branches in sorted(seen.items()):
        problems.append("実験番号 %s が衝突しています: %s（%s）\n"
                        "    どちらかを改番してください。先に走ったほうが番号を保持します。"
                        % (num, other, ", ".join(sorted(set(branches)))))
    return problems


def comparability(spec, allow_mismatch=False):
    """spec が `compare_with:` で比較先の run を宣言していれば、本文が同じか照合する。

    **これは回す前に効かなければ意味がない。** 013 では spec のヘッダに
    「002 と比較するため」と書いたが、その間に本文が 2 回変わっていた。回したあとに
    気づいても、比較先と揃った対照はもう一度取り直すしかない（実費がかかる）。

    宣言が無ければ何もしない。宣言するかどうかは spec を書く人の判断だが、
    ヘッダのコメントに「○○と比較する」と書くなら、ここにも書くこと。
    コメントは誰も照合しない。
    """
    targets = spec.get("compare_with") or []
    if not targets:
        return True

    now = prompt_version.current(agent_variant=spec.get("agent_variant"))
    ids = [{"run": "（この run）",
            "被験体本文sha256": now["被験体本文sha256"],
            "バリアント": now["バリアント"],
            "由来": now["由来"]}]
    ids += [prompt_version.of_run(t) for t in targets]

    hashes = set(i.get("被験体本文sha256") for i in ids)
    if len(hashes) == 1 and None not in hashes:
        print("比較先と本文が一致しています: %s" % ", ".join(targets))
        return True

    # 「違う」と「特定できない」を混ぜない。前者は取り直せば済むが、後者は
    # 比較先そのものが使えない（その run の本文はもう復元できない）。
    if None in hashes:
        print("NG   比較先の本文を特定できません（spec の compare_with）:")
    else:
        print("NG   比較先と本文が違います（spec の compare_with）:")
    for i in ids:
        print("  " + prompt_version.describe(i))
    print("  条件の差とプロンプトの差が分離できません。")
    print("  比較先を現行本文で取り直すか、比較先の宣言を直してください。")
    print("  違いを承知のうえで回すなら --allow-prompt-mismatch を付けます")
    print("  （承知して回したことが manifest に残ります）。")
    return bool(allow_mismatch)


def preflight(spec_path=None, spec=None, allow_prompt_mismatch=False):
    """本体プロンプトと fixture 側コピーがずれていないか、fixture が無改変か、
    実験番号が他のブランチと衝突していないか、比較先と本文が揃っているか。"""
    if spec_path and spec:
        problems = spec_number_conflicts(spec_path, spec)
        if problems:
            print("NG   spec の番号・命名に問題があります:")
            for p in problems:
                print("  - " + p)
            return False
        if not comparability(spec, allow_prompt_mismatch):
            return False

    print("fixture: %s" % FIXTURE)
    # check-sync は v0.2.0 で Bun に移った（配布物と同じ実行系で回す）。
    # 実験ハーネス側は Python のままなので、ここだけ実行系が混ざる。
    bun = shutil.which("bun")
    if bun is None:
        print("NG   bun が見つかりません。check-sync.ts を実行できないため中止します。")
        return False

    checks = (
        (bun, "check-sync.ts", "プロンプト同期"),
        (sys.executable, os.path.join("experiments", "verify-fixture.py"), "fixture 無改変"),
    )
    for runner, script, label in checks:
        r = subprocess.run([runner, os.path.join(ROOT, script)],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print("NG   %s の検査に失敗しました:" % label)
            print(r.stdout + r.stderr)
            return False
    return True


def fixture_clean():
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "experiments", "verify-fixture.py"), "--quiet"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stdout + r.stderr)


# ---------------------------------------------------------------- セル展開

def expand(spec):
    """factors を宣言順に直積展開する。宣言順が実行順（軽い条件を先に流す）。"""
    names = list(spec["factors"].keys())
    combos = [{}]
    for n in names:
        combos = [dict(c, **{n: v}) for c in combos for v in spec["factors"][n]]

    cells = []
    for c in combos:
        for rep in range(1, spec.get("reps", 1) + 1):
            cid = "__".join(str(c[n]) for n in names) + "__r%d" % rep
            cells.append(dict(c, id=cid, rep=rep))
    return cells


def turn_text(spec, turn, cell):
    """このターンの本文。vary が無ければ全条件で固定の台本。"""
    if "vary" in turn:
        return spec["levels"][turn["vary"]][cell[turn["vary"]]].strip()
    return turn["text"].strip()


# ---------------------------------------------------------------- 実行

def claude_bin():
    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("claude CLI が見つかりません")


def run_turn(text, model, session_id, first, agent="learn"):
    """1ターン実行し、(init イベント, result イベント) を返す。

    stream-json を使う理由：最初の init イベントに、ハーネスが実際に渡した
    ツール配列が入っている。モデルの自己申告ではない機械的な事実なので、
    「resume でエージェント定義が外れていないか」をこれで毎ターン検証できる。
    """
    cmd = [claude_bin(), "-p", text,
           "--output-format", "stream-json", "--verbose",
           "--model", model,
           "--permission-mode", "manual",
           "--permission-prompts", "none",
           "--strict-mcp-config",
           "--setting-sources", "project",
           "--disallowedTools", "Edit Write Bash PowerShell NotebookEdit",
           "--system-prompt-snapshot", "on"]
    if first:
        cmd += ["--agent", agent, "--session-id", session_id]
    else:
        cmd += ["--resume", session_id]

    proc = subprocess.run(cmd, cwd=FIXTURE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          timeout=TURN_TIMEOUT_SEC)

    init = None
    result = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init" and init is None:
            init = ev
        if ev.get("type") == "result":
            result = ev

    if result is None:
        raise RuntimeError("result イベントが返りませんでした。stderr 末尾: %s"
                           % proc.stderr[-1500:])
    return init, result


# ---------------------------------------------------------------- 指標（決定論的）

# 本体プロンプトの規定に対応する検出パターン。LLM 採点はノイズ源なので、
# 正規表現と JSON で取れるものは全部こちらで取る。
PATTERNS = {
    # prompt.md:95 採点の言葉を使わない
    "採点語": r"正解(です|でし|！|。|、)|違います|惜しい|理解度\s*\d+\s*[%％]",
    # prompt.md:61 説明を求める前のフレーミング
    "フレーミング": r"正確じゃなくて|正確でなくて|単語だけ|途中で止まって|ざっくりで",
    # prompt.md:208-213 重大度ラベル
    "重大度ラベル": r"壊れる|危ない|改善余地|好み",
    # ops-guide:172 実装代行の申し出（出たら開発セッションが応答している合図）
    "実装代行": r"代わりに実装|実装しましょうか|書きましょうか|私が(書|実装|直)|こちらで(修正|実装|書)",
    # prompt.md:76-78 はしごを降ろす動き（選択肢を出す・予測させる）
    "はしご降ろし": r"どれに近い|どちらに近い|選んでみて|消したら(何が|どう)|どうなると思",
}

_ident_cache = None


def fixture_identifiers():
    """fixture の export 名を集める。

    prompt.md:24 は「開発者のプロジェクトのファイル名・変数名・型・API を使わない」
    と規定している。例示コードにこれらが混ざっていれば違反の候補。
    手書きのリストだと漏れるので fixture から機械的に集める。
    """
    global _ident_cache
    if _ident_cache is not None:
        return _ident_cache
    pat = re.compile(r"export\s+(?:default\s+)?(?:async\s+)?"
                     r"(?:type|interface|class|function|const|let|enum)\s+([A-Za-z_$][\w$]*)")
    names = set()
    for dirpath, dirnames, filenames in os.walk(os.path.join(FIXTURE, "app")):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        for fn in filenames:
            if not fn.endswith((".ts", ".tsx")):
                continue
            try:
                with io.open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace") as f:
                    names.update(pat.findall(f.read()))
            except OSError:
                continue
    # 3文字以下は一般語と衝突するので落とす
    _ident_cache = set(n for n in names if len(n) > 3)
    return _ident_cache


def code_blocks(text):
    return re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL)


def measure(response, init, result):
    """応答1本から決定論的な指標を出す。判断が要るものは採点者に回す。"""
    m = {}
    m["応答文字数"] = len(response)
    m["疑問符数"] = response.count("？") + response.count("?")
    # 日本語の質問は「〜ですか。」のように句点で終わることが多く、？ だけでは拾えない。
    # 実測で、選択肢つきの確認質問を2つ含む応答の ？ が 0 件だった（opus/none/coarse）。
    # ？ の計数だけを根拠に「問いが無い」と判断してはいけない。
    m["質問文数"] = m["疑問符数"] + len(
        re.findall("(?:です|ます|でしょう|ました|ません|ある|近い)か[。\n]", response))
    # 人格が消えると一方的な解説になり、問い返しの密度が落ちるはず。
    # ただし長い解説ほど分母が増えるので、字数との交絡に注意して読むこと。
    m["問い返し密度"] = round(m["質問文数"] / max(len(response), 1) * 1000, 3)

    for label, pat in PATTERNS.items():
        m[label] = len(re.findall(pat, response))

    blocks = code_blocks(response)
    m["コードブロック数"] = len(blocks)
    m["コード最大行数"] = max([len(b.rstrip("\n").split("\n")) for b in blocks] or [0])
    # prompt.md:23 例示コードは目安10行以内
    m["コード10行超"] = int(m["コード最大行数"] > 10)

    idents = fixture_identifiers()
    leaked = sorted(set(i for b in blocks for i in idents
                        if re.search(r"\b%s\b" % re.escape(i), b)))
    m["固有識別子の混入"] = len(leaked)
    m["混入した識別子"] = ";".join(leaked[:8])

    # --- ハーネス由来の値 ---
    u = result.get("usage") or {}
    its = u.get("iterations") or []

    def ctx(d):
        return ((d.get("input_tokens") or 0)
                + (d.get("cache_read_input_tokens") or 0)
                + (d.get("cache_creation_input_tokens") or 0))

    # プローブが届いた時点でコンテキストがどれだけ埋まっていたか。
    # これが希釈仮説の独立変数。input_tokens 単独ではキャッシュ分が抜けて無意味
    # （実測で input_tokens=2 / cache_read=9966 だった）。
    m["開始時コンテキストtok"] = ctx(its[0]) if its else ctx(u)
    m["終了時コンテキストtok"] = ctx(its[-1]) if its else ctx(u)
    m["出力tok"] = u.get("output_tokens") or 0
    m["ツール往復数"] = max(len(its) - 1, 0)
    m["num_turns"] = result.get("num_turns")
    m["所要ms"] = result.get("duration_ms")
    m["コストUSD"] = result.get("total_cost_usd")
    m["is_error"] = int(bool(result.get("is_error")))
    m["stop_reason"] = result.get("stop_reason")

    tools = set((init or {}).get("tools") or [])
    m["ツール集合一致"] = int(tools == EXPECTED_TOOLS)
    m["余分なツール"] = ";".join(sorted(tools - EXPECTED_TOOLS))
    return m


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--only", help="このセルIDだけ実行")
    ap.add_argument("--dry-run", action="store_true", help="送信文の展開だけ表示")
    ap.add_argument("--resume-run", action="store_true", help="完了済みセルを飛ばす")
    ap.add_argument("--allow-prompt-mismatch", action="store_true",
                    help="compare_with の比較先と本文が違っても回す（manifest に残る）")
    args = ap.parse_args()

    with io.open(args.spec, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    cells = expand(spec)
    if args.only:
        cells = [c for c in cells if c["id"] == args.only]
        if not cells:
            raise SystemExit("該当セルなし: %s" % args.only)

    if args.dry_run:
        for c in cells:
            print("=" * 68)
            print(c["id"])
            for t in spec["turns"]:
                line = turn_text(spec, t, c).replace("\n", "\n          ")
                print("  [%-6s] %s" % (t["id"], line))
        print("\n合計 %d セル / %d ターン"
              % (len(cells), len(cells) * len(spec["turns"])))
        return 0

    if not preflight(args.spec, spec, args.allow_prompt_mismatch):
        return 1

    # プロンプト自体を実験条件にする場合。バリアント定義を fixture の
    # .claude/agents/ に置き、--agent でそれを選ぶ。マスターの learn.md は触らない
    # （触ると過去の run と比較できなくなる）。
    agent = "learn"
    variant = spec.get("agent_variant")
    if variant:
        vpath = os.path.join(ROOT, variant)
        if not os.path.exists(vpath):
            print("NG   バリアントがありません: %s" % vpath)
            return 1
        with io.open(vpath, encoding="utf-8") as f:
            vtext = f.read()
        m = re.search(r"^name:\s*(\S+)", vtext, re.MULTILINE)
        if not m:
            print("NG   バリアントの frontmatter に name がありません: %s" % vpath)
            return 1
        agent = m.group(1)
        dest = os.path.join(FIXTURE, ".claude", "agents", agent + ".md")
        with io.open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(vtext)
        print("バリアント使用: --agent %s （%s）" % (agent, variant))

    # この run がどの本文で走ったかを、**被験体が実際に読むファイルから**取る（#43）。
    # リポジトリ側の learning-mentor-prompt.md ではなく fixture 側のエージェント定義を
    # 見るので、推定が入らない。取るのは 1 セル目の前。manifest を書く最後に取ると、
    # run の途中で本文を編集したときに「走った本文とは違うハッシュ」が記録される。
    subject_agent = os.path.join(FIXTURE, ".claude", "agents", agent + ".md")
    body = prompt_version.current(subject_agent, variant)
    print("本文: %s （%s）" % (body["被験体本文sha256"][:12],
                            "配布本文と同一" if body["被験体本文sha256"] == body["配布本文sha256"]
                            else "バリアント"))

    run_dir = os.path.join(RUNS, spec["id"])
    os.makedirs(os.path.join(run_dir, "cells"), exist_ok=True)
    model_factor = spec.get("model_factor", "model")
    labels = spec.get("cell_labels", {})
    rows = []

    for c in cells:
        cell_dir = os.path.join(run_dir, "cells", c["id"])
        done = os.path.join(cell_dir, "done.json")
        if args.resume_run and os.path.exists(done):
            print("SKIP %s （完了済み）" % c["id"])
            with io.open(done, encoding="utf-8") as f:
                rows.append(json.load(f)["metrics_row"])
            continue
        os.makedirs(cell_dir, exist_ok=True)

        ok, msg = fixture_clean()
        if not ok:
            print("中断：セル実行前に fixture が汚れていました\n" + msg)
            return 1

        session_id = str(uuid.uuid4())
        model = c[model_factor]
        print("RUN  %s  (model=%s)" % (c["id"], model))

        row = {"cell": c["id"], "session_id": session_id,
               "label": labels.get("%s__%s" % (c.get("context_load"),
                                               c.get("probe_grain")), "")}
        row.update(dict((k, v) for k, v in c.items() if k != "id"))

        try:
            for i, t in enumerate(spec["turns"]):
                text = turn_text(spec, t, c)
                with io.open(os.path.join(cell_dir, "prompt-%s.txt" % t["id"]), "w",
                             encoding="utf-8", newline="\n") as f:
                    f.write(text)

                init, result = run_turn(text, model, session_id,
                                        first=(i == 0), agent=agent)

                # API エラーは result として返ってくる。本文にエラー文字列が入るだけなので
                # 採点に回ると「問いが無い応答」として点が付いてしまう（実際に起きた）。
                # ここで例外にして done.json を書かせず、--resume-run で再実行させる。
                if result.get("is_error") or result.get("terminal_reason") == "api_error":
                    raise RuntimeError("API エラー（turn=%s）: %s"
                                       % (t["id"], (result.get("result") or "")[:200]))

                with io.open(os.path.join(cell_dir, "raw-%s.json" % t["id"]), "w",
                             encoding="utf-8", newline="\n") as f:
                    json.dump({"init": init, "result": result}, f,
                              ensure_ascii=False, indent=2)

                resp = result.get("result") or ""
                with io.open(os.path.join(cell_dir, "response-%s.md" % t["id"]), "w",
                             encoding="utf-8", newline="\n") as f:
                    f.write(resp)

                tools = set((init or {}).get("tools") or [])
                if tools != EXPECTED_TOOLS:
                    print("  !! ツール集合が想定と違います（turn=%s）: %s"
                          % (t["id"], sorted(tools)))
                    print("     resume でエージェント定義が外れた可能性があります。")

                stats = measure(resp, init, result)
                if t.get("measure"):
                    row.update(stats)
                    row["turn_measured"] = t["id"]
                print("     [%s] %d字 / ctx開始 %s tok / ツール往復 %d / %s"
                      % (t["id"], len(resp), stats["開始時コンテキストtok"],
                         stats["ツール往復数"], model))
        except Exception as e:
            print("  !! セル失敗: %s" % e)
            row["error"] = str(e)[:300]

        ok, msg = fixture_clean()
        if not ok:
            print("中断：セル実行後に fixture が汚れました。実験の前提が壊れています。\n" + msg)
            return 1

        rows.append(row)
        # 失敗したセルは done.json を書かない。書いてしまうと --resume-run が
        # 失敗セルをスキップし、欠測に気づかないまま採点へ進んでしまう。
        # （実際に API エラーの応答が採点に回り、人格残存度1が付いたことがある）
        if row.get("error"):
            print("     -> done.json は書きません（--resume-run で再実行されます）")
        else:
            with io.open(done, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"cell": c, "metrics_row": row}, f, ensure_ascii=False, indent=2)

    # manifest：あとから「どういう条件で取ったデータか」を復元できるようにする
    #
    # 本文は 1 セル目の前に取ってある。ここでもう一度取って、run の途中で
    # 変わっていないかを見る。fixture の .claude/ はローカル除外されているので
    # verify-fixture.py の `git status --porcelain` では捕まらない経路。
    after = prompt_version.current(subject_agent, variant)
    if after["被験体本文sha256"] != body["被験体本文sha256"]:
        print("  !! run の途中で本文が変わりました。%s -> %s"
              % (body["被験体本文sha256"][:12], after["被験体本文sha256"][:12]))
        print("     セルごとに違う本文で走っています。この run は比較に使えません。")
        body = dict(body, 途中で変わった=True, 終了時sha256=after["被験体本文sha256"])

    head = subprocess.run(["git", "-C", FIXTURE, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    ver = subprocess.run([claude_bin(), "--version"],
                         capture_output=True, text=True).stdout.strip()
    with io.open(os.path.join(run_dir, "manifest.json"), "w",
                 encoding="utf-8", newline="\n") as f:
        json.dump({
            "spec_id": spec["id"],
            "実行日時": datetime.now(timezone.utc).isoformat(),
            "fixture_path": FIXTURE,
            # この run がどの本文で走ったか（#43）。fixture の SHA も claude の
            # バージョンも残っていたのに、**肝心の配布本文だけが残っていなかった。**
            # 無いと「過去の run と比較してよいか」を後から判定できず、比較した結果の
            # 解釈だけが静かに間違う。読み方と照合は prompt_version.py。
            "本文": body,
            # compare_with の不一致を承知で回したか。承知なら記録に残す。残さないと、
            # あとから見た人には「気づかずに回した run」と区別がつかない。
            "比較先との本文不一致を許可": bool(args.allow_prompt_mismatch
                                     and spec.get("compare_with")),
            # 被験体の文脈に混入した CLAUDE.md。preflight が空でなければ止めるので
            # 通常は [] になるが、記録が無いと後から「無かった」ことを示せない（#42）。
            "混入した CLAUDE_md": fixture_path.claude_md_in_scope(FIXTURE),
            "fixture_sha": head,
            "claude_version": ver,
            "spec": spec,
        "agent": agent,
        "agent_variant": spec.get("agent_variant"),
            "既知の単純化": [
                "--strict-mcp-config で MCP を全停止。learn.md の mcp__github-ro は無効。",
                "--setting-sources project でユーザーグローバル設定は読み込まない。",
                "fixture の README に『生成AIを使わないでほしい』の記述あり（全条件に等しくかかる定数）。",
            ],
        }, f, ensure_ascii=False, indent=2)

    # metrics.csv は「この実行で回したセル」ではなく「run ディレクトリにある全セル」から
    # 作り直す。--only や --resume-run で部分実行したときに、既存の行を消さないため。
    rows = []
    cells_root = os.path.join(run_dir, "cells")
    for cid in sorted(os.listdir(cells_root)):
        dj = os.path.join(cells_root, cid, "done.json")
        if os.path.exists(dj):
            with io.open(dj, encoding="utf-8") as f:
                rows.append(json.load(f)["metrics_row"])

    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with io.open(os.path.join(run_dir, "metrics.csv"), "w",
                 encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print("\n%d セル完了 -> %s" % (len(rows), os.path.join(run_dir, "metrics.csv")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
