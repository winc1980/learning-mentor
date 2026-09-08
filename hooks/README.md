# SessionStart hook の置き方

セッション開始時に、学習メンターの新版が出ていないかを自動で確認します。
確認するだけで、**書き換えはしません**（更新は `mentor-update.py --apply` を人が実行する）。

理由は2つ。メンターは `Read` / `Grep` / `Glob` / `WebFetch` / `WebSearch` しか持たない
**読み取り専用のセッション**なので、そもそも自分を書き換えられません。そして書き換えを
自動化すると、学習者に無断でメンターの挙動が変わります。

---

## 共通の前提

`mentor-update.py` の置き場所を決めて、絶対パスで指定します。以下は
`~/learning-mentor/mentor-update.py` に置いた例です。**自分の環境のパスに書き換えてください。**

Windows で `python` が PATH に無い場合は `py -3` に読み替えます。

---

## Claude Code

`~/.claude/settings.json`（全プロジェクト共通）か、`<repo>/.claude/settings.json`
（そのリポジトリだけ）の `hooks` に、`claude-code.settings.json` の中身を統合します。
すでに `hooks` がある場合は `SessionStart` の配列に足してください。

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          { "type": "command", "command": "python \"$HOME/learning-mentor/mentor-update.py\" --hook", "timeout": 10 }
        ]
      }
    ]
  }
}
```

---

## Codex CLI

`~/.codex/hooks.json` に `codex.hooks.json` の中身を置きます。加えて
`~/.codex/config.toml` に次が要ります。

```toml
[features]
codex_hooks = true
```

### ★ 置き場所に注意：リポジトリ直下ではなくユーザー直下に置いてください

`<repo>/.codex/config.toml` に hook を書くと発火しないという報告があります
（[openai/codex#17532](https://github.com/openai/codex/issues/17532)）。
ユーザー直下の `~/.codex/hooks.json` を使ってください。

### ★★ Codex では、hook が動かない可能性を前提にしてください

上記の issue は **2026-09-07 時点で open** です。報告の内容：

| 報告 | 版 | 結果 |
|---|---|---|
| `codex exec`（非対話） | 0.128.0 | **動く** |
| `codex`（対話TUI） | 0.128.0 / 0.132.0 | **動かない** |

OpenAI 側の担当者は `Stop` hook で再現しなかったと述べており、状況は確定していません。
確実なのは次の1点です。

> **動かなくてもエラーは出ません。**

これは運用ガイドが繰り返し警告している「配置に失敗しても黙って無視される」パターンそのものです。
だから Codex では、**hook を主たる経路にしないでください。** 学習会の節目などに

```
python mentor-update.py --check
```

を手で回すことを、正規の手順として案内してください。hook は動けば得をする補助です。

---

## 置いたあと、必ず確認してください

hook を書いただけでは、効いているかどうか分かりません。**セッションを1回起動してから**
次を実行します。

```
python mentor-update.py --check
```

出力の `hook :` の行が判定です。

| 表示 | 意味 |
|---|---|
| `hook : OK（最後の実行 0.2 時間前）` | 効いています |
| `hook : ★ 一度も動いていません` | **設定が効いていません。** パス・JSONの位置・Codex なら上記の制限を疑う |
| `hook : ★ ... から動いていません` | 途中で外れました。設定ファイルが上書きされた可能性 |
| `hook : ★ 最後の実行で失敗しました` | スクリプトは呼ばれたが中で落ちた。表示される理由を読む |

`--hook` は何があっても終了コード 0 を返し、セッションを止めません。ただし失敗は必ず
記録に残るので、`--check` で後から読めます。**その場では静かに、後から見えるように。**
