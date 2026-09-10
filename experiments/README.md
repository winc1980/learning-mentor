# 実験ハーネス

メンタープロンプトの規定が、条件を変えたときに守られるかを測る。

**作業の管理は GitHub Issues。** 未着手の実験は [`experiment` ラベル](https://github.com/winc1980/learning-mentor/labels/experiment)、
測らないと決めたものは [DECISIONS.md](DECISIONS.md)。このファイルには**手順と到達点**だけを書く。

---

## いまどこにいるか

**済んだこと。** 「メンターが理解確認を飛ばして一方的に解説する」現象を再現し、原因を2経路
（直前に詳細解説を済ませている／広い質問が来る）に特定し、プロンプト2箇所の修正（v2-gate）で
崩壊していた4条件を 0〜2/10 から 10/10 に戻した。退行なし。

**測ったもの。** 102セル / 204ターン / 全12名の盲検採点。すべて opus、すべて固定台本、すべて Claude Code。

**測っていないもの。** 大きい順に：本体プロンプトの約4割を占めるレビュー／トラブルモードが
一度も発火していない（#3）。実学習者で一度も試していない（#4）。3ターン目以降の規定が全部未測定（#13）。

| run | 何を見たか |
|---|---|
| 001 | コンテキスト量の希釈（sonnet, n=1） |
| 002 | opus で n=5。崩壊条件の特定 |
| 003 | v2-gate を D・F 条件で |
| 004 | 深さ仮説。**コンテキスト量ではなく直前ターンの種類が効くと判明** |
| 005 | v2-gate が経路1を戻すか |
| 006 | v2-gate の退行チェック |

**ルーブリックは版2。** 版1（001〜006）とは **L3/L4 の意味が逆**。読み替え規則は [rubric.md](rubric.md)。
集計時に版を混ぜると静かに壊れる（#21）。

---

## fixture の作り直し

`experiments/fixture/` は追跡していない（中身は upstream のもの）。**失うと作り直しが要る。**

```
git clone https://github.com/winc1980/2026-phase-2 experiments/fixture
git -C experiments/fixture checkout 913c103e062e05d23dfa78c980d83a65d1e3f1c1
```

固定 SHA の正は [`verify-fixture.py`](verify-fixture.py) の `PINNED_SHA`。上とずれたらそちらが正しい。

次に、メンター定義を **git から見えない形で**置く。`.git/info/exclude` に追記する
（`.gitignore` に書くと fixture 自体の差分になる）。

```
printf '.claude/\n' >> experiments/fixture/.git/info/exclude
mkdir -p experiments/fixture/.claude/agents
cp .claude/agents/learn.md experiments/fixture/.claude/agents/learn.md
```

**この配置が「無改変」の前提になっている。** `.claude/` がローカル除外されているので、
`git status --porcelain` が空であることがそのまま「fixture が汚れていない」を意味する。

最後に検査する。

```
python experiments/verify-fixture.py
bun check-sync.ts         # fixture の learn.md が本体プロンプトと一致しているか
```

**`run.py` は各セルの実行前後で `verify-fixture.py` を呼び、NG なら run 全体を止める。**
fixture が一度でも書き換わると、それ以降の run は過去の run と比較できなくなるため。

---

## 回し方

```
python experiments/run.py experiments/specs/006-v2gate-regression.yaml
python experiments/run.py <spec> --only sonnet__none__fine__r1   # 1セルだけ
python experiments/run.py <spec> --dry-run                       # プロンプト展開だけ見る
python experiments/run.py <spec> --resume-run                    # 完了済みを飛ばして再開
```

被験体は `claude -p --agent learn` のサブプロセス。**サブエージェント（Agent ツール）では起動しない。**
学習者が実際に使う `claude --agent learn` と同一構成にするため（理由は
`learning-mentor-ops-guide.md` の【B】呼び出し型の節）。

採点は盲検で行う。

```
python experiments/blind.py make 006-v2gate-regression   # 盲検バッチを作る
python experiments/blind.py join 006-v2gate-regression   # 採点結果を条件に突合する
python experiments/analyze.py 006-v2gate-regression      # 条件ごとに集計する
```

**採点者に条件を見せない。** 見えていると期待した方向に採点が寄る。応答本文と不透明IDだけを渡し、
条件ラベルは `key.json` に隔離する。盲検がどこまで効いているか（probe_grain は部分的に露出する）は
`blind.py` の冒頭に正直に書いてある。

**30件を1エージェントに渡すとストールする。** 15件程度で分割する（#23）。

---

## ディレクトリ

| | 中身 |
|---|---|
| `specs/*.yaml` | 実験の定義。要因・水準・反復数・モデル。**冒頭のコメントに、その実験で何を見るかを書く** |
| `variants/` | プロンプトのバリアント（`v2-gate.md`, `wex-fine.md`）。`.py` が生成元 |
| `runs/<id>/` | 実行結果。`blind/`, `judgments.jsonl`, `metrics.csv`, `report.md` |
| `fixture/` | 被験体が読むリポジトリ（追跡外。上記の手順で作り直す） |
| `rubric.md` | 採点基準。**版の読み替え規則もここ** |
