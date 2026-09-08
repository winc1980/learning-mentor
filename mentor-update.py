#!/usr/bin/env python3
"""配置済みの学習メンターを、GitHub Releases の最新版に追従させる。

このスクリプトは4つのモードを持つ。すべて1ファイルに入れてあるのは、
配布物を増やさないため（配るものが増えるほど、古いものが混ざる）。

    --setup     配置直後に1回だけ実行する。受領書を書き、hook を設置し、
                動作確認の手順を表示する（旧名 --register も受け付ける）
    --check     人が読む形で、新版の有無と hook の健康状態を表示する
    --apply     受領書を見て、配置済みのコピーを最新版に貼り直す
    --hook      SessionStart hook から呼ばれる。JSON を1行返して即座に終わる

なぜ導入を1コマンドに畳むか:
    受領書の記録・hook の設置・動作確認は、以前は利用者が別々に行う手順だった。
    そのうち hook の設置は、設定ファイルを手で開いて JSON を継ぎ足し、
    コマンドのパスを自分の環境に書き換える作業で、**失敗しても何のエラーも出ない**。
    この製品が最も嫌う失敗の型が、導入手順の中に3つ並んでいた。
    配置したAIが続けて1回実行すれば済むので、まとめてある。

なぜ受領書が要るか:
    learning-mentor-setup.md は、配置先をAIに判断させる設計になっている。
    このため置き場所は人によって違う。更新側から見ると、探し当てる手段が無い。
    配置した時点で記録しておく以外に方法がない。

なぜマーカーで囲むか:
    【A】常時適用型では本文が CLAUDE.md / AGENTS.md に埋め込まれる。そのファイルには
    学習者自身の記述も入りうるので、ファイルごと上書きしてはいけない。
    マーカー間だけを差し替える。マーカーの内側は本文と1バイトも変えないので、
    check-sync.py の一致検査はそのまま通る。

終了コード:
    0 = 最新（または処理成功） / 1 = エラー / 2 = 新版あり（--check のみ）
"""

import argparse
import datetime
import difflib
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

# Windows のコンソールは既定が UTF-8 でないことがあり、日本語が化ける
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = "winc1980/learning-mentor"
API_LATEST = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASES_PAGE = "https://github.com/%s/releases" % REPO

# 配置済みファイルの中で本文を囲む番兵。begin 側だけがバージョンを名乗る。
# 内側は learning-mentor-prompt.md と完全一致させる（check-sync.py と同じ規約）。
MARK_BEGIN = "<!-- learning-mentor:begin v%s -->"
MARK_BEGIN_RE = re.compile(r"<!--\s*learning-mentor:begin\s+v([0-9A-Za-z.\-]+)\s*-->")
MARK_END = "<!-- learning-mentor:end -->"

# --target の種別。ここに無い語は種別と見なさない（Windows のドライブレター対策も兼ねる）
#   agent    = .claude/agents/learn.md のような、frontmatter 付きの定義ファイル
#   embedded = CLAUDE.md / AGENTS.md のように、他の記述と同居しているファイル
TARGET_KIND_RE = re.compile(r"^(agent|embedded):(.+)$", re.DOTALL)

CHECK_INTERVAL_HOURS = 24  # 成功結果の寿命。GitHub API は未認証で 60回/時
FAILURE_INTERVAL_HOURS = 1  # 失敗の寿命。短いのは、復旧に早く気づけるようにするため
NETWORK_TIMEOUT = 5  # hook を待たせない。繋がらなければ黙って諦める


# --------------------------------------------------------------------------
# 保存場所
# --------------------------------------------------------------------------

def home():
    """受領書・キャッシュ・スタンプの置き場所。

    環境変数で差し替えられるようにしてあるのは、検証用に隔離した状態で
    動かせるようにするため（experiments/ が fixture を隔離しているのと同じ理由）。
    """
    override = os.environ.get("LEARNING_MENTOR_HOME")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".learning-mentor")


def path_in_home(name):
    return os.path.join(home(), name)


def read_json(path, default=None):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))
        f.write("\n")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def parse_iso(text):
    try:
        return datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def hours_since(iso_text):
    """iso_text から何時間経ったか。読めなければ None。"""
    stamp = parse_iso(iso_text)
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    delta = datetime.datetime.now(datetime.timezone.utc) - stamp
    return delta.total_seconds() / 3600.0


# --------------------------------------------------------------------------
# バージョン比較
# --------------------------------------------------------------------------

def version_key(text):
    """"1.2.10" -> (1, 2, 10)。数字でない部分は 0 として扱う。

    厳密な semver 実装ではない。プレリリース版を配る予定がないので、
    数値の組として比べれば足りる。
    """
    parts = re.split(r"[.\-+]", (text or "").strip().lstrip("vV"))
    key = []
    for part in parts:
        digits = re.match(r"\d+", part)
        key.append(int(digits.group()) if digits else 0)
    return tuple(key) or (0,)


def is_newer(latest, local):
    return version_key(latest) > version_key(local)


# --------------------------------------------------------------------------
# GitHub Releases
# --------------------------------------------------------------------------

def remember_failure(cache_path, cache, message):
    """失敗を短時間だけ覚える。直前までの成功結果は消さない。

    キャッシュごと上書きすると、オフラインになった瞬間に「前回 v1.1.0 を見た」
    という事実まで失われる。失敗は別のキーに積む。
    """
    cache = dict(cache or {})
    cache["failed_at"] = now_iso()
    cache["error"] = message
    try:
        write_json(cache_path, cache)
    except Exception:
        pass  # キャッシュが書けないこと自体は、処理を止める理由にならない
    return None, message


def fetch_latest(force=False):
    """最新リリースを取る。成功は24時間、失敗は1時間キャッシュする。

    戻り値は (info, error) の組。info は {"version", "url", "asset", "notes"}。
    ネットワークが無い環境でも hook を壊さないため、例外は投げずに error を返す。

    失敗もキャッシュするのは、オフラインのままセッションを開くたびに
    タイムアウト（最大 NETWORK_TIMEOUT 秒）を待たされるのを避けるため。
    通知の頻度は変わらない ── latest は None のままなので、decide_notice は
    キャッシュの有無にかかわらず同じ判断をする。
    """
    cache_path = path_in_home("cache.json")
    cache = read_json(cache_path, default={}) or {}

    if not force:
        age = hours_since(cache.get("checked_at", ""))
        if age is not None and age < CHECK_INTERVAL_HOURS and cache.get("latest"):
            return cache["latest"], None
        fail_age = hours_since(cache.get("failed_at", ""))
        if fail_age is not None and fail_age < FAILURE_INTERVAL_HOURS and cache.get("error"):
            return None, cache["error"]

    request = urllib.request.Request(
        API_LATEST,
        headers={
            "User-Agent": "learning-mentor-update",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return remember_failure(cache_path, cache, "リリースがまだ1つも公開されていません")
        return remember_failure(
            cache_path, cache, "GitHub API がエラーを返しました (HTTP %s)" % exc.code)
    except Exception as exc:  # ネットワーク断・DNS・タイムアウトなど
        return remember_failure(cache_path, cache, "取得できませんでした: %s" % exc)

    asset_url = None
    for asset in payload.get("assets", []):
        if asset.get("name", "").endswith(".zip"):
            asset_url = asset.get("browser_download_url")
            break

    info = {
        "version": (payload.get("tag_name") or "").lstrip("vV"),
        "url": payload.get("html_url") or RELEASES_PAGE,
        "asset": asset_url,
        "notes": (payload.get("body") or "").strip(),
    }
    # 成功したら失敗の記録は残さない（次に落ちたときの経過時間が狂うため）
    write_json(cache_path, {"checked_at": now_iso(), "latest": info})
    return info, None


# --------------------------------------------------------------------------
# 受領書
# --------------------------------------------------------------------------

def receipt_path():
    return path_in_home("receipt.json")


def load_receipt():
    return read_json(receipt_path())


def command_line(script, mode):
    """人にそのまま渡せるコマンド行を組む。

    受領書にスクリプトの絶対パスがあるならそれを使う。相対パスで案内すると、
    受け取った側は「どのディレクトリで打つのか」を自分で解く必要がある。
    """
    if script:
        return '"%s" "%s" %s' % (sys.executable, script, mode)
    return "mentor-update.py %s" % mode


def placed_version(target_path):
    """配置済みファイルが名乗っているバージョンを読む。

    受領書を失っても、置かれたファイル自体がバージョンを持っているので復旧できる。
    マーカーが無い（= このスクリプトを通さずに手で貼った）場合は None。
    """
    try:
        with io.open(target_path, encoding="utf-8") as f:
            text = f.read()
    except (IOError, OSError):
        return None
    found = MARK_BEGIN_RE.search(text)
    return found.group(1) if found else None


# --------------------------------------------------------------------------
# 通知するかどうかの方針
# --------------------------------------------------------------------------

def decide_notice(state):
    """新版の状況を見て、セッション冒頭に何を出すかを決める。

    ここがこの仕組みの性格を決める。「うるさくない」と「見逃さない」は両立しない。

    state に入るもの:
        local                 いま配置されているバージョン（例 "1.0.0"）。不明なら None
        latest                最新バージョン。取得できなかったなら None
        error                 取得に失敗した理由の文字列。成功していれば None
        last_notified         この端末に前回通知したバージョン。未通知なら None
        hook_last_run_hours   hook が最後に動いてから何時間か。初回なら None
        script                受領書に記録したスクリプトの絶対パス。無ければ None

    戻り値:
        セッション冒頭に差し込む文字列。何も出さないなら None を返す。

    採用した方針:
        新版の告知は、その版について一度だけ。ただし3日以上あいだが空いた起動では、
        前回を見逃している可能性があるので出し直す。
        取得の失敗は毎回、理由つきで出す（切り分けができないと直せないため）。
    """
    # --- ここから下を書き換える ---
    # 失敗は毎回出す。理由まで出さないと、DNS断・レート制限・リリース未公開の
    # どれなのかが切り分けられず、デバッグの役に立たない。
    if state["latest"] is None:
        return "学習メンターの更新確認に失敗しました（%s）" % (state["error"] or "理由不明")

    # 受領書が読めない = 更新できない状態。黙っていると誰も気づかない。
    if not state["local"]:
        return ("学習メンターの受領書が読めません。%s で確認してください。"
                % command_line(state.get("script"), "--check"))

    if not is_newer(state["latest"], state["local"]):
        return None

    # 一度伝えた版は繰り返さない。ただし3日以上あいだが空いたら、
    # 前回の通知を見逃している可能性があるので出し直す。
    already_told = state["last_notified"] == state["latest"]
    used_recently = (state["hook_last_run_hours"] is not None
                     and state["hook_last_run_hours"] < 72)
    if already_told and used_recently:
        return None

    # 更新コマンドは絶対パスで出す。ここに URL しか書かないと、受け取った人は
    # まず「スクリプトをどこに置いたか」を思い出すところから始めることになる。
    return "学習メンターの新版 v%s が出ています（いま v%s）。更新するには %s を実行してください（変更点: %s）。" % (
        state["latest"], state["local"], command_line(state.get("script"), "--apply"), RELEASES_PAGE
    )
    # --- ここまで ---


# --------------------------------------------------------------------------
# モード: --hook
# --------------------------------------------------------------------------

def cmd_hook(args):
    """SessionStart hook から呼ばれる。

    絶対に守ること: 何があってもセッションを壊さない。例外を投げない。終了コードは常に 0。
    ただし「黙って死ぬ」のはこの製品が最も嫌う失敗なので、失敗の記録は必ず残し、
    --check で人が読めるようにする。その場では静かに、後から見えるように。
    """
    previous = read_json(path_in_home("stamp.json"), {}) or {}
    stamp = {"ran_at": now_iso(), "ok": True, "error": None,
             "notified_version": previous.get("notified_version")}
    notice = None
    try:
        receipt = load_receipt()
        latest_info, error = fetch_latest()
        state = {
            "local": receipt.get("version") if receipt else None,
            "latest": latest_info["version"] if latest_info else None,
            "error": error,
            "last_notified": previous.get("notified_version"),
            "hook_last_run_hours": hours_since(previous.get("ran_at", "")),
            "script": (receipt or {}).get("script_path"),
        }
        notice = decide_notice(state)
        if notice and state["latest"]:
            stamp["notified_version"] = state["latest"]
        stamp["error"] = error
    except Exception as exc:
        stamp["ok"] = False
        stamp["error"] = "%s: %s" % (type(exc).__name__, exc)

    try:
        write_json(path_in_home("stamp.json"), stamp)
    except Exception:
        pass  # スタンプが書けないこと自体は、セッションを止める理由にならない

    if notice:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": notice,
            }
        }, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------
# モード: --check
# --------------------------------------------------------------------------

def cmd_check(args):
    receipt = load_receipt()
    if not receipt:
        print("受領書がありません（%s）" % receipt_path())
        print("配置直後に、置いた場所を指定してこれを実行してください:")
        print("  %s" % command_line(
            script_path(), "--setup --tool claude-code --target agent:/絶対パス/learn.md"))
        return 1

    local = receipt.get("version", "不明")
    print("配置済み : v%s（%s に配置）" % (local, receipt.get("installed_at", "日付不明")))
    print("運用     : %s / 運用型 %s" % (receipt.get("tool", "不明"), receipt.get("pattern", "不明")))
    print("配置先   :")
    for target in receipt.get("targets", []):
        path = target.get("path", "")
        stamped = placed_version(path) if os.path.exists(path) else None
        if not os.path.exists(path):
            note = "★ ファイルが見つかりません"
        elif stamped is None:
            note = "★ マーカーがありません（--apply で更新できません）"
        elif stamped != local:
            note = "★ 受領書は v%s だがファイルは v%s" % (local, stamped)
        else:
            note = "OK"
        label = target.get("kind", "?")
        if target.get("tool") and target["tool"] != "unknown":
            label = "%s/%s" % (target["tool"], label)
        print("  [%s] %s  %s" % (label, path, note))

    # hook が本当に動いているか。Codex の対話TUIでは発火しないという報告があり
    # （openai/codex#17532、2026-05-21 時点で open）、しかも失敗してもエラーが出ない。
    # 動いていないことを検出できないと、「更新確認しているつもり」で古いまま使い続ける。
    print()
    stamp = read_json(path_in_home("stamp.json"))
    if not stamp:
        print("hook     : ★ 一度も動いていません。hook の設定が効いていない可能性があります")
    else:
        age = hours_since(stamp.get("ran_at", ""))
        when = ("%.1f 時間前" % age) if age is not None else "不明"
        if not stamp.get("ok", True):
            print("hook     : ★ 最後の実行で失敗 — %s（%s）" % (stamp.get("error"), when))
        elif age is not None and age > 24 * 7:
            print("hook     : ★ %s から動いていません。設定が外れた可能性があります" % when)
        else:
            print("hook     : OK（最後の実行 %s）" % when)

    print()
    latest_info, error = fetch_latest(force=True)
    if error:
        print("最新版   : ★ 確認できませんでした — %s" % error)
        return 1
    latest = latest_info["version"]
    if is_newer(latest, local):
        print("最新版   : v%s ← 新版が出ています" % latest)
        if latest_info.get("notes"):
            print()
            for line in latest_info["notes"].splitlines()[:10]:
                print("    " + line)
        print()
        print("更新するには: %s"
              % command_line(receipt.get("script_path") or script_path(), "--apply"))
        return 2
    print("最新版   : v%s（最新です）" % latest)
    return 0


# --------------------------------------------------------------------------
# モード: --apply
# --------------------------------------------------------------------------

def replace_between_markers(text, body, version):
    """マーカー間の本文を差し替える。マーカーが無ければ (None, 理由) を返す。"""
    found = MARK_BEGIN_RE.search(text)
    if not found:
        return None, "開始マーカーがありません"
    end_at = text.find(MARK_END, found.end())
    if end_at == -1:
        return None, "終了マーカーがありません"
    head = text[: found.start()]
    tail = text[end_at + len(MARK_END):]
    return head + (MARK_BEGIN % version) + "\n" + body.strip() + "\n" + MARK_END + tail, None


def download_source(asset_url):
    """リリース zip を落として、本文（learning-mentor-prompt.md）を取り出す。"""
    import tempfile
    import zipfile

    request = urllib.request.Request(asset_url, headers={"User-Agent": "learning-mentor-update"})
    with urllib.request.urlopen(request, timeout=30) as response:
        blob = response.read()
    handle, tmp_path = tempfile.mkstemp(suffix=".zip")
    os.close(handle)
    try:
        with io.open(tmp_path, "wb") as f:
            f.write(blob)
        with zipfile.ZipFile(tmp_path) as archive:
            for name in archive.namelist():
                if name.endswith("learning-mentor-prompt.md"):
                    return archive.read(name).decode("utf-8"), None
        return None, "zip の中に learning-mentor-prompt.md がありません"
    finally:
        os.unlink(tmp_path)


def cmd_apply(args):
    receipt = load_receipt()
    if not receipt:
        print("受領書がありません。先に --setup を実行してください。")
        return 1

    latest_info, error = fetch_latest(force=True)
    if error:
        print("最新版を確認できませんでした — %s" % error)
        return 1
    latest = latest_info["version"]
    local = receipt.get("version", "0")
    if not is_newer(latest, local) and not args.force:
        print("すでに最新です（v%s）。貼り直すなら --force。" % local)
        return 0
    if not latest_info.get("asset"):
        print("リリース v%s に zip アセットが付いていません: %s" % (latest, latest_info["url"]))
        return 1

    body, error = download_source(latest_info["asset"])
    if error:
        print(error)
        return 1

    # まず全部の差分を見せる。書き換えるのは了解を得てから。
    plans = []
    for target in receipt.get("targets", []):
        path = target.get("path", "")
        if not os.path.exists(path):
            print("SKIP %s （見つかりません）" % path)
            continue
        with io.open(path, encoding="utf-8") as f:
            original = f.read()
        updated, error = replace_between_markers(original, body, latest)
        if error:
            print("SKIP %s （%s）" % (path, error))
            continue
        if updated == original:
            print("変更なし %s" % path)
            continue
        plans.append((path, original, updated))

    if not plans:
        print("書き換える対象がありませんでした。")
        return 1

    # 本文が全面的に書き換わると差分は数百行になり、流れるだけで判断の役に立たない。
    # 既定は「どこが何行変わるか」の要約。中身を見たいときだけ --diff。
    print()
    print("v%s → v%s" % (local, latest))
    if latest_info.get("notes"):
        print()
        for line in latest_info["notes"].splitlines()[:15]:
            print("  " + line)
    print()
    for path, original, updated in plans:
        diff = list(difflib.unified_diff(
            original.splitlines(), updated.splitlines(),
            fromfile="v%s" % local, tofile="v%s" % latest, lineterm="", n=1,
        ))
        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
        print("  %s" % path)
        print("      +%d 行 / -%d 行（マーカーの外は変えません）" % (added, removed))
        if args.diff:
            for line in diff:
                print("      " + line)

    if not args.diff:
        print()
        print("  中身を確認するなら --diff を付けて実行してください。")
    print()
    if not args.yes:
        answer = input("上記を v%s に更新します。よろしいですか [y/N]: " % latest).strip().lower()
        if answer not in ("y", "yes"):
            print("中止しました。")
            return 1

    for path, original, updated in plans:
        with io.open(path + ".bak", "w", encoding="utf-8", newline="") as f:
            f.write(original)
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(updated)
        print("更新 %s （元は %s.bak）" % (path, os.path.basename(path)))

    receipt["version"] = latest
    receipt["updated_at"] = now_iso()
    write_json(receipt_path(), receipt)
    print()
    print("v%s に更新しました。" % latest)
    # 更新は本文を丸ごと入れ替える。配置が効いているかの確認は、配置直後と
    # まったく同じ理由で毎回要る。案内を別ファイルに送らず、その場に出す。
    print_verification()
    return 0


# --------------------------------------------------------------------------
# hook の設置
# --------------------------------------------------------------------------

# ツールごとの差はこの表だけに閉じる。設定ファイルの場所・matcher・
# hook エントリに載る追加フィールドの3点しか違わない。
HOOK_TARGETS = {
    "claude-code": {
        "settings": ("~", ".claude", "settings.json"),
        "matcher": "startup",
        "fields": {"timeout": 10},
    },
    "codex": {
        "settings": ("~", ".codex", "hooks.json"),
        "matcher": "startup|resume",
        "fields": {
            "statusMessage": "学習メンターの更新を確認しています",
            "additionalContextLimit": 2000,
        },
    },
}


def script_path():
    return os.path.abspath(__file__)


def hook_command():
    """hook から呼ばせるコマンド行。

    `python` ではなく sys.executable を書く。--setup を実行できた解釈器は
    確実に存在するが、`python` が PATH にある保証はない（Windows では特に多い）。
    ここを間違えても hook は黙って何もしないので、推測できる箇所は推測しない。
    """
    return '"%s" "%s" --hook' % (sys.executable, script_path())


def hook_entry(tool):
    spec = HOOK_TARGETS[tool]
    inner = {"type": "command", "command": hook_command()}
    inner.update(spec["fields"])
    return {"matcher": spec["matcher"], "hooks": [inner]}


def is_mentor_entry(entry):
    """この仕組みが置いた hook エントリか。どのリポジトリのコピーでも真になる。

    スクリプトのパスは見ない。学習メンターは複数のリポジトリに配置されうるが、
    **更新通知は端末に1本あれば足りる。**「新版が出た」という事実はリポジトリごとに
    変わらないし、通知の重複はどのみち stamp.json の既通知判定で潰れる（2本目は
    何も出さない）。だからどのコピーが登録されていても「うちのもの」と見なし、
    最新の1本に集約する。
    """
    command = ((entry or {}).get("command") or "")
    return "mentor-update.py" in command and "--hook" in command


def consolidate_session_start(groups, desired):
    """SessionStart の配列を、メンターの hook がちょうど1本ある状態にする。

    **メンター以外のエントリには触らない。** メンターのエントリは、どのリポジトリの
    コピーを指していても取り除き、最後に desired を1つだけ足す。

    グループ単位ではなくエントリ単位で外すのが要点。1つのグループにメンターの
    hook と他人の hook が同居している場合、グループごと消すと無関係な設定まで
    巻き添えになる。

    戻り値: (新しい配列, 取り除いたメンターエントリの数)
    """
    kept_groups = []
    removed = 0
    for group in groups or []:
        entries = (group or {}).get("hooks")
        if not isinstance(entries, list):
            kept_groups.append(group)  # 想定外の形は解釈せず、そのまま残す
            continue
        kept = [entry for entry in entries if not is_mentor_entry(entry)]
        removed += len(entries) - len(kept)
        if kept:
            survivor = dict(group)
            survivor["hooks"] = kept
            kept_groups.append(survivor)
    return kept_groups + [desired], removed


def backup_and_write(path, text):
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as f:
            original = f.read()
        with io.open(path + ".bak", "w", encoding="utf-8", newline="") as f:
            f.write(original)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def install_hook(tool):
    """SessionStart hook を設定ファイルに書く。メンターの hook は常に1本に保つ。

    v0.1.1 までは「既存の SessionStart 設定があれば触らず報告」だった。実地で
    破綻した。**2つ目のリポジトリに配置すると、1つ目で自分が置いた hook を
    「他人の設定」と見なして拒否する。** リポジトリを増やすたびに手作業が要る。

    方針を次のように変えた。

        メンターの hook（どのリポジトリのコピーでも）→ 取り除いて、最新の1本に置き換える
        メンター以外の SessionStart 設定          → 一切触らず、自分のエントリを足す

    「触らず報告」を守るのはメンター以外の設定に対してだけにした。**自分が置いた
    ものを他人のものとして扱うのは、慎重さではなく取り違えでしかない。**

    集約する（追加しない）のは、通知が端末単位の情報だから。2本目の hook は
    stamp.json の既通知判定で黙るので、増やしても仕事がない。

    戻り値: (status, 表示する行のリスト)
        status は "installed" / "updated" / "already" / "skipped" / "failed"
    """
    if tool not in HOOK_TARGETS:
        return "skipped", [
            "hook     : ★ 設置していません（--tool %s は自動設置に未対応）" % (tool or "未指定"),
            "           対応しているのは %s です。" % " / ".join(sorted(HOOK_TARGETS)),
            "           手で入れる場合は hooks/README.md を見てください。",
            "           コマンドはこれです: %s" % hook_command(),
        ]

    path = os.path.expanduser(os.path.join(*HOOK_TARGETS[tool]["settings"]))
    settings = read_json(path, default=None)
    if settings is None and os.path.exists(path):
        return "failed", [
            "hook     : ★ %s を読めませんでした（JSON として壊れている可能性）" % path,
            "           直してから --setup をもう一度実行してください。",
        ]
    settings = settings if isinstance(settings, dict) else {}

    hooks = settings.get("hooks")
    hooks = hooks if isinstance(hooks, dict) else {}
    existing = hooks.get("SessionStart")
    existing = existing if isinstance(existing, list) else []

    updated, removed = consolidate_session_start(existing, hook_entry(tool))
    hooks["SessionStart"] = updated
    settings["hooks"] = hooks

    text = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
    try:
        with io.open(path, encoding="utf-8") as f:
            unchanged = f.read() == text
    except (IOError, OSError):
        unchanged = False
    if unchanged:
        return "already", ["hook     : 設置済み（%s）" % path] + ensure_codex_feature(tool)

    try:
        backup_and_write(path, text)
    except Exception as exc:
        return "failed", ["hook     : ★ %s に書けませんでした — %s" % (path, exc)]

    others = sum(len(g.get("hooks", [])) for g in updated[:-1] if isinstance(g.get("hooks"), list))
    if removed:
        lines = ["hook     : 更新しました（%s）" % path,
                 "           既にあった学習メンターの登録 %d 件を、このコピーの1本にまとめました"
                 % removed]
    else:
        lines = ["hook     : 設置しました（%s）" % path]
    if others:
        lines.append("           ほかの SessionStart 設定 %d 件はそのまま残しています" % others)
    lines.extend(ensure_codex_feature(tool))
    return ("updated" if removed else "installed"), lines


def ensure_codex_feature(tool):
    """Codex は hook 機能自体がフラグの裏にある。config.toml 側も面倒を見る。

    TOML を機械で書き換えるのは危ないので、安全に足せると分かる場合しか触らない。
    既に [features] テーブルがあるなら、そこへ追記すると重複テーブルで
    設定ファイル全体が読めなくなる。その場合は報告だけして手を引く。
    """
    if tool != "codex":
        return []
    path = os.path.expanduser(os.path.join("~", ".codex", "config.toml"))
    try:
        with io.open(path, encoding="utf-8") as f:
            text = f.read()
    except (IOError, OSError):
        text = None

    if text is None:
        try:
            backup_and_write(path, "[features]\ncodex_hooks = true\n")
        except Exception as exc:
            return ["           ★ %s を作れませんでした — %s" % (path, exc)]
        return ["           %s に [features] codex_hooks = true を書きました" % path]

    if re.search(r"^\s*codex_hooks\s*=\s*true", text, re.MULTILINE):
        return ["           config.toml の codex_hooks は有効です"]

    if re.search(r"^\s*\[features\]", text, re.MULTILINE):
        return [
            "           ★ %s に既に [features] があります。触っていません。" % path,
            "           そのテーブルに codex_hooks = true を手で足してください。",
        ]

    try:
        backup_and_write(path, text.rstrip("\n") + "\n\n[features]\ncodex_hooks = true\n")
    except Exception as exc:
        return ["           ★ %s に書けませんでした — %s" % (path, exc)]
    return ["           %s に [features] codex_hooks = true を足しました（元は .bak）" % path]


# --------------------------------------------------------------------------
# 個人の配置物をチームリポジトリに巻き込まない
# --------------------------------------------------------------------------
#
# なぜ要るか:
#   配置先はAIが環境ごとに判断する（learning-mentor-setup.md）。学習会の参加者が
#   普段の開発リポジトリに【B】呼び出し型で配置すると、置き場所はツール・OS・
#   本人の判断で人によって変わる。.gitignore に入れておかないと、次の
#   `git add` や `git status` に個人の配置物が混ざり、「AIメンター導入」だけの
#   PR が参加者の数だけ飛んでくる。チーム開発では無意味な差分でしかない。

GITIGNORE_MARK_BEGIN = "# learning-mentor:gitignore begin"
GITIGNORE_MARK_END = "# learning-mentor:gitignore end"


def find_repo_root(path):
    """path から上へ辿って .git のあるディレクトリを探す。無ければ None。"""
    current = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def gitignore_entry(repo_root, target_path):
    """.gitignore に書く1行。リポジトリ直下からの相対パスで、先頭に / を付けて
    同名ファイルが別の場所にあっても巻き込まないようにする。"""
    rel = os.path.relpath(os.path.abspath(target_path), repo_root).replace(os.sep, "/")
    return "/" + rel


def already_ignored(existing_lines, entry):
    """entry そのもの、または entry を含む親ディレクトリの除外が既にあるか。"""
    stripped = {line.strip().lstrip("/") for line in existing_lines}
    bare = entry.lstrip("/")
    if bare in stripped:
        return True
    parts = bare.split("/")
    for i in range(1, len(parts)):
        if "/".join(parts[:i]) + "/" in stripped:
            return True
    return False


def update_gitignore(repo_root, entries):
    """learning-mentor 専用ブロックを .gitignore に足す（無ければ作る）。

    既存のブロックがあれば中身を読み取って合流させる（再実行しても重複しない）。
    変更が無かった場合は書き込まない。
    戻り値: (path, 書き込んだかどうか)
    """
    path = os.path.join(repo_root, ".gitignore")
    try:
        with io.open(path, encoding="utf-8") as f:
            text = f.read()
    except (IOError, OSError):
        text = ""

    lines = text.splitlines()
    begin_at = next((i for i, l in enumerate(lines) if l.strip() == GITIGNORE_MARK_BEGIN), None)
    end_at = next((i for i, l in enumerate(lines) if l.strip() == GITIGNORE_MARK_END), None)

    if begin_at is not None and end_at is not None and end_at > begin_at:
        before, block_body, after = lines[:begin_at], lines[begin_at + 1:end_at], lines[end_at + 1:]
    else:
        before, block_body, after = lines, [], []

    existing_entries = [l for l in block_body if l.strip() and not l.strip().startswith("#")]
    merged = list(existing_entries)
    for entry in entries:
        if entry not in merged and not already_ignored(before + merged + after, entry):
            merged.append(entry)

    if not merged:
        return path, False
    if merged == existing_entries and begin_at is not None:
        return path, False

    block = [GITIGNORE_MARK_BEGIN,
             "# 学習メンターの個人導入物。配置先は人によって違うので追跡しない"] + merged + [GITIGNORE_MARK_END]

    new_lines = before + ([""] if before and before[-1].strip() != "" else []) + block
    if after:
        new_lines = new_lines + [""] + after

    new_text = "\n".join(new_lines).rstrip("\n") + "\n"
    if new_text == text:
        return path, False

    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    return path, True


def content_outside_markers(text):
    """マーカーで囲まれた本文を取り除いた残り。embedded 判定に使う。"""
    found = MARK_BEGIN_RE.search(text)
    if not found:
        return text
    end_at = text.find(MARK_END, found.end())
    if end_at == -1:
        return text
    return text[:found.start()] + text[end_at + len(MARK_END):]


def is_tracked_by_git(repo_root, path):
    """path が既に git 管理下にあるか。無ければ False（git が無い環境でも False）。"""
    rel = os.path.relpath(os.path.abspath(path), repo_root).replace(os.sep, "/")
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel],
            cwd=repo_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except (OSError, ValueError):
        return False


def protect_targets_from_git(targets):
    """配置先を調べ、リポジトリ内のものは .gitignore に足す。表示行のリストを返す。

    - agent（frontmatter 付きの単独ファイル）は無条件で対象にする
    - embedded（CLAUDE.md / AGENTS.md など）は、マーカーの外に本文が無い
      （＝このファイルが実質メンター専用ファイルとして新規に作られた）場合だけ
      対象にする。既存の記述と同居している場合は自動で除外できないので警告に回す
    """
    lines = []
    by_repo = {}
    no_repo = []
    warn_embedded = []
    tracked_already = []

    for target in targets:
        path = target["path"]
        kind = target["kind"]
        if kind == "embedded":
            try:
                with io.open(path, encoding="utf-8") as f:
                    remainder = content_outside_markers(f.read())
            except (IOError, OSError):
                remainder = None
            if remainder is None or remainder.strip():
                warn_embedded.append(path)
                continue

        root = find_repo_root(path)
        if root is None:
            no_repo.append(path)
            continue
        by_repo.setdefault(root, []).append(path)
        if is_tracked_by_git(root, path):
            tracked_already.append((root, path))

    for root, paths in by_repo.items():
        entries = [gitignore_entry(root, p) for p in paths]
        gpath, changed = update_gitignore(root, entries)
        if changed:
            lines.append("gitignore: %s に追記しました" % gpath)
        else:
            lines.append("gitignore: %s は既に対応済みです" % gpath)

    for root, path in tracked_already:
        lines.append("gitignore: ★ %s は既に git 管理下です。"
                      "`git rm --cached -- \"%s\"` で追跡を外してください"
                      % (path, os.path.relpath(path, root).replace(os.sep, "/")))

    for path in warn_embedded:
        lines.append("gitignore: ★ %s は既存ファイルへの同居配置（embedded）のため、"
                      "自動では除外できません" % path)
        lines.append("           他の記述と同じファイルにあるので、ファイルごと無視すると"
                      "チームの記述も消えます。共有リポジトリなら【A】の分離運用か、"
                      "個人用ファイルへの分離を検討してください。")

    for path in no_repo:
        lines.append("gitignore: %s は git リポジトリの外なので対象外です" % path)

    return lines


# --------------------------------------------------------------------------
# モード: --setup
# --------------------------------------------------------------------------

def read_version_file():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with io.open(os.path.join(here, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except (IOError, OSError):
        return None


VERIFY_QUESTION = "使えるツールの名前を、箇条書きで全部挙げてください。"


def print_verification():
    """配置が効いているかを人が確かめる手順を、その場に出す。

    ここだけは自動化できない。配置が効いているかは、そのセッションが実際に
    何を持っているかにしか現れず、外から観測する手段がないため。
    README と hooks/README.md を往復させないよう、必要なものは全部ここに出す。
    """
    print()
    print("─" * 60)
    print("★ 最後に、動作確認をしてください（ここを飛ばさないでください）")
    print()
    print("  置き場所を間違えても、エラーは出ません。黙って無視されるだけです。")
    print("  メンターを起動して、次の質問をそのまま貼ってください。")
    print()
    print("      %s" % VERIFY_QUESTION)
    print()
    print("  読み取り系だけ（Read / Grep / Glob など）  → 成功")
    print("  Edit / Write やシェル実行が入っている       → 失敗。置き場所か起動方法が違います")
    print()
    print("  「書き換えて」と頼んで断られたかどうかでは判定できません。ツールが無くても")
    print("  AIは「〜という設定なので、できません」と説明するだけで、区別がつかないためです。")
    print()
    print("  hook が本当に動いたかは、セッションを1回起動したあとに分かります:")
    print("      \"%s\" \"%s\" --check" % (sys.executable, script_path()))
    print("─" * 60)


def merge_targets(existing, incoming):
    """配置先をパスで合流する。同じ配置先なら上書き、違う配置先なら追加。

    受領書は端末に1つしかない。v0.1.1 まではここを丸ごと置き換えていたため、
    **2つ目のリポジトリに配置すると1つ目の配置先が受領書から消えていた。**
    消えた配置先は --apply の対象から外れ、二度と更新されない。しかも
    エラーは出ない ── この製品が最も嫌う壊れ方だった。

    戻り値: (合流後のリスト, 追加された数, 更新された数)
    """
    merged = [dict(target) for target in (existing or []) if isinstance(target, dict)]
    # Windows のパスは大文字小文字を区別しないので、normcase で突き合わせる
    index = {os.path.normcase(t.get("path", "")): i for i, t in enumerate(merged)}
    added = updated = 0
    for target in incoming:
        key = os.path.normcase(target["path"])
        if key in index:
            merged[index[key]] = target
            updated += 1
        else:
            index[key] = len(merged)
            merged.append(target)
            added += 1
    return merged, added, updated


def cmd_setup(args):
    """配置直後に1回実行する。受領書・hook・動作確認をまとめて片づける。

    setup.md の配置手順の最後で、AI にこれを実行させる想定。
    """
    version = args.version or read_version_file() or "0.0.0"
    targets = []
    for spec in args.target:
        # 種別は既知の語だけに限る。素朴に partition(":") で割ると、Windows の
        # ドライブレター（C:/Users/...）を区切りと誤認する。
        found = TARGET_KIND_RE.match(spec)
        kind, path = (found.group(1), found.group(2)) if found else ("agent", spec)
        targets.append({
            "kind": kind,
            "path": os.path.abspath(os.path.expanduser(path)),
            # 配置先ごとにツールを持たせる。複数リポジトリに配置すると、
            # リポジトリごとに別のツールを使っていることがある
            "tool": args.tool or "unknown",
            "registered_at": now_iso(),
        })

    previous = load_receipt() or {}
    merged, added, refreshed = merge_targets(previous.get("targets"), targets)

    write_json(receipt_path(), {
        "version": version,
        "installed_at": previous.get("installed_at") or now_iso(),
        "updated_at": now_iso(),
        "tool": args.tool or previous.get("tool") or "unknown",
        "pattern": args.pattern or previous.get("pattern") or "unknown",
        "source": "https://github.com/%s" % REPO,
        # 更新のたびにスクリプトを探させないため、自分の居場所を残す。
        # hook の通知文も --check の案内も、ここを読んで絶対パスで出す。
        "script_path": script_path(),
        "targets": merged,
    })
    print("受領書   : %s" % receipt_path())
    if added and len(merged) > added:
        print("  配置先 %d 件（今回 %d 件を追加。既存の登録は残しています）"
              % (len(merged), added))
    elif refreshed and len(merged) > refreshed:
        print("  配置先 %d 件（今回 %d 件を更新）" % (len(merged), refreshed))
    for target in merged:
        stamped = placed_version(target["path"])
        if not os.path.exists(target["path"]):
            print("  ★ %s が見つかりません（--apply の対象から外れています）" % target["path"])
        elif stamped is None:
            print("  ★ %s にマーカーがありません。本文を次の形で囲んでください:" % target["path"])
            print("      %s" % (MARK_BEGIN % version))
            print("      （本文）")
            print("      %s" % MARK_END)
        else:
            print("  OK %s （v%s）" % (target["path"], stamped))

    # .gitignore の面倒を見るのは今回指定された配置先だけ。既に登録済みの
    # 配置先は前回の --setup で処理済みだし、別リポジトリを勝手に触らない
    for line in protect_targets_from_git(targets):
        print(line)

    if args.no_hook:
        print("hook     : 設置していません（--no-hook）")
    else:
        _, lines = install_hook(args.tool)
        for line in lines:
            print(line)

    print_verification()
    return 0


# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="学習メンターの配置を最新版に追従させる")
    parser.add_argument("--hook", action="store_true", help="SessionStart hook から呼ぶ")
    parser.add_argument("--check", action="store_true", help="新版の有無と hook の状態を表示（既定）")
    parser.add_argument("--apply", action="store_true", help="配置済みのコピーを最新版に貼り直す")
    parser.add_argument("--setup", "--register", action="store_true", dest="setup",
                        help="配置直後に1回。受領書・hook・動作確認をまとめて行う")
    parser.add_argument("--target", action="append", default=[], metavar="KIND:PATH",
                        help="--setup 用。agent:/path/to/learn.md の形で複数指定できる")
    parser.add_argument("--tool", help="--setup 用。claude-code / codex。hook の置き場所を決める")
    parser.add_argument("--pattern", help="--setup 用。A（常時適用型）/ B（呼び出し型）")
    parser.add_argument("--no-hook", action="store_true", dest="no_hook",
                        help="--setup 用。更新のお知らせ（SessionStart hook）を設置しない")
    parser.add_argument("--version", help="--setup 用。省略時は VERSION ファイルを読む")
    parser.add_argument("--diff", action="store_true", help="--apply 用。差分を全文表示する")
    parser.add_argument("--force", action="store_true", help="--apply 用。同一版でも貼り直す")
    parser.add_argument("--yes", "-y", action="store_true", help="--apply 用。確認を省く")
    args = parser.parse_args(argv)

    if args.hook:
        return cmd_hook(args)
    if args.setup:
        return cmd_setup(args)
    if args.apply:
        return cmd_apply(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
