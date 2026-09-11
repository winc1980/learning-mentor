# 実験ハーネス

メンタープロンプトの規定が、条件を変えたときに守られるかを測る。

**作業の管理は GitHub Issues。** 未着手の実験は [`experiment` ラベル](https://github.com/winc1980/learning-mentor/labels/experiment)、
測らないと決めたものは [DECISIONS.md](DECISIONS.md)。このファイルには**手順と到達点**だけを書く。

---

## いまどこにいるか

**済んだこと。** 「メンターが理解確認を飛ばして一方的に解説する」現象を再現し、原因を2経路
（直前に詳細解説を済ませている／広い質問が来る）に特定し、プロンプト2箇所の修正（v2-gate）で
崩壊していた4条件を 0〜2/10 から 10/10 に戻した。退行なし。

**測ったもの。** 102セル / 204ターン（001〜006、すべて opus）に加えて、012・013 の 30セル / 60ターン。
**モデル差は規定順守に出なかった** ── 現行の配布本文なら opus も sonnet も経路2で崩れない（012・013）。
002 で opus が 0/10 まで落ちたのは v2-gate 取り込み前の本文での話で、あれはモデルの性質ではなく本文の性質だった。
差が出たのは説明量（opus が約1.4倍）と費用（opus が約2.0倍）だけ。

**測っていないもの。** 大きい順に：本体プロンプトの約4割を占めるレビュー／トラブルモードが
一度も発火していない（#3）。実学習者で一度も試していない（#4）。3ターン目以降の規定が全部未測定（#13）。
**解説の分かりやすさ・正しさは一度も測っていない**（測っているのは規定を守るかどうかだけ）。
経路1でのモデル差も測れていない ── sonnet はそもそもその状態に入らないため（011）。

**run をまたいで比べるときは、本文が同じかを先に照合すること。**（下記「run をまたいで比べる」）
001〜004 は v2-gate 前、008 以降は現行本文なので、そのまま並べると条件の差と本文の差が混ざる。

| run | 何を見たか |
|---|---|
| 001 | コンテキスト量の希釈（sonnet, n=1） |
| 002 | opus で n=5。崩壊条件の特定 |
| 003 | v2-gate を D・F 条件で |
| 004 | 深さ仮説。**コンテキスト量ではなく直前ターンの種類が効くと判明** |
| 005 | v2-gate が経路1を戻すか |
| 006 | v2-gate の退行チェック |
| 008 | sonnet の最悪条件（**CLAUDE.md 混入。未採点・比較不可**、#42） |
| 011 | 混入が loader の字数に効いたかの切り分け。**効いていなかった** |
| 012 | 経路2を sonnet で（現行本文）。崩れない |
| 013 | 経路2を opus で（現行本文・012 の対照）。**こちらも崩れない** |

**ルーブリックは版2。** 版1（001〜006）とは **L3/L4 の意味が逆**。読み替え規則は [rubric.md](rubric.md)。
集計時に版を混ぜると静かに壊れる（#21）。

---

## fixture の作り直し

fixture は追跡していない（中身は upstream のもの）。**失うと作り直しが要る。**

### 置き場所は、このリポジトリの外

既定は `../learning-mentor-fixture`（リポジトリと並ぶ位置）。**`experiments/` の下に
置いてはいけない。** cwd の祖先にある CLAUDE.md は被験体のプロジェクト指示として
読み込まれるので、`experiments/fixture` に置くと**このリポジトリの CLAUDE.md が
被験体に渡る**。規定が守られるかを測る実験で、被験体に規定の解説を渡すことになる。

これは 008 で実際に起きた（issue #42）。fixture は最後まで無改変で、`verify-fixture.py`
も `check-sync.ts` も全セル通っていた。**混入するのは fixture の中身ではなく、外の文脈。**
`repo_sweep` 水準がたまたま親リポジトリの構成を説明し始めたことでようやく気づいた。

場所の正は [`fixture_path.py`](fixture_path.py)。worktree ごとに別の fixture を使いたい
ときは環境変数 `MENTOR_FIXTURE` で上書きする。既定では全 worktree が同じ fixture を
共有する（読むだけなので競合しない）。

```
git clone https://github.com/winc1980/2026-phase-2 ../learning-mentor-fixture
git -C ../learning-mentor-fixture checkout 913c103e062e05d23dfa78c980d83a65d1e3f1c1
```

固定 SHA の正は [`verify-fixture.py`](verify-fixture.py) の `PINNED_SHA`。上とずれたらそちらが正しい。

次に、メンター定義を **git から見えない形で**置く。`.git/info/exclude` に追記する
（`.gitignore` に書くと fixture 自体の差分になる）。

```
printf '.claude/\n' >> ../learning-mentor-fixture/.git/info/exclude
mkdir -p ../learning-mentor-fixture/.claude/agents
cp .claude/agents/learn.md ../learning-mentor-fixture/.claude/agents/learn.md
```

**この配置が「無改変」の前提になっている。** `.claude/` がローカル除外されているので、
`git status --porcelain` が空であることがそのまま「fixture が汚れていない」を意味する。

最後に検査する。

```
python experiments/verify-fixture.py
bun check-sync.ts         # fixture の learn.md が本体プロンプトと一致しているか
```

`verify-fixture.py` は中身の無改変に加えて、**その場所で被験体が拾う CLAUDE.md が
無いこと**も見る。1つでもあれば NG になり、`run.py` は run を始めない。

**`run.py` は各セルの実行前後で `verify-fixture.py` を呼び、NG なら run 全体を止める。**
fixture が一度でも書き換わると、それ以降の run は過去の run と比較できなくなるため。

---

## run をまたいで比べる

**条件の差を読む前に、その差がプロンプトの差でないことを確かめる。**

```
python experiments/prompt_version.py 012 013      # 並べてよいか（違えば exit 1）
python experiments/analyze.py  012 013            # 集計。並べた時点で同じ照合が走る
python experiments/analyze5.py 012 013
python experiments/prompt_version.py              # いまの本文の同一性
```

### なぜ検査を足したか

`check-sync.ts` は**本文と 3 箇所のコピーが揃っていること**を保証し、`run.py` は毎回それを
通す。だからどの run も「本文と同期した learn.md」で走っていて、検査は全部通る。
**検査していなかったのは、その本文が比較先の run の本文と同じかどうか。** 通らない検査が
無いので、本文の違う run を並べても何も起きない。**出るのは、比較した結果の解釈だけが
静かに間違うという形**（#43）。

013 で実際に起きた。012（sonnet）を 002（opus）の対照として設計したが、その間に
`a398e78`（v2-gate の本文取り込み）と `35d7e59`（L3/L4 入れ替え）が入っていて、モデルと
プロンプトの両方が違った。気づいたのは応答文字数の並びに違和感を持ったからで、仕組みが
教えてくれたわけではない。

### 回す前に照合する

spec に比較先を書くと、`run.py` が preflight で照合し、本文が違えば run を始めない。

```yaml
compare_with: [012-sonnet-path2]
```

**ヘッダのコメントに「○○と比較する」と書くだけでは誰も照合しない。** 013 のヘッダには
書いてあった。違いを承知で回すなら `--allow-prompt-mismatch`（承知して回したことが
manifest に残る）。

### 何が記録されるか

`manifest.json` の `本文` に、**被験体が実際に読んだファイル**（fixture の
`.claude/agents/<agent>.md`）のハッシュが入る。リポジトリ側の `learning-mentor-prompt.md`
ではなく被験体側から取るので、バリアントを使った run でも推定が入らない。あわせて配布本文の
ハッシュ・`VERSION`・リポジトリの HEAD・作業ツリーが汚れていたかも残る。

ハッシュは `bun check-sync.ts --hash` に取らせている。正規化（改行・行末空白・更新用
マーカーの吸収）の規則を Python に書き写すと**規則が 2 つになり、片方だけ直したときに
静かにずれる。** 規則は `normalize()` ただ 1 つに保ち、実行系をまたいで呼ぶ。

run の途中で本文が変わっていないかも、最初と最後のハッシュで見る。fixture の `.claude/` は
ローカル除外されているので、`verify-fixture.py` の `git status --porcelain` では捕まらない経路。

### 過去 run（#43 より前）

manifest に記録が無い run の本文は、[`prompt-history.json`](prompt-history.json) に置いた。
**`runs/` には追記していない。** manifest は取得時の事実の記録で、あとから git を見て推定した
値を同じ場所に混ぜると、「実行時に記録された事実」と「あとから復元した推定」の区別が消える。
**その区別が消えることが #43 で直そうとしている当のもの**なので、外に由来付きで置く。

```
python experiments/prompt_version.py --rebuild-history
```

復元は「manifest の実行日時より前に、その経路を最後に触ったコミット」を本文とみなす推定。
**003・005・006 は復元できず「不明」。** バリアント本文は生成器が作業ツリーに吐いたものを
そのまま使い、git に入ったのは run のあと（`a398e78`）だった。被験体が読んだ本文は git に
無いので、あるはずの値を埋めずに不明と書いてある。

---

## 実験番号は別 worktree と衝突する

番号はそのまま run ディレクトリ名になる。別 worktree で同じ番号の別実験を作っても、
**ファイル名が違えば git は衝突として扱わない。** マージした瞬間に、どちらのデータか
分からなくなる。実際に 007 で起きた（`007-a5-wexfine-pilot` と、当初 007 を名乗っていた
`008-sonnet-worst`）。

`run.py` は preflight で、ローカルの全ブランチの `experiments/specs/` を走査し、同じ番号を
名乗る spec があれば run を始めない。**先に走ったほうが番号を保持する。**

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
| `../../learning-mentor-fixture/` | 被験体が読むリポジトリ。**リポジトリの外**（追跡外。上記の手順で作り直す） |
| `fixture_path.py` | fixture の場所の解決規則と、CLAUDE.md 混入の検査 |
| `prompt_version.py` | run が**どの本文で走ったか**の記録・復元・照合。**run を並べる前に通る** |
| `prompt-history.json` | #43 より前の run の本文を git から復元した対応表（由来つき。生成物） |
| `rubric.md` | 採点基準。**版の読み替え規則もここ** |
