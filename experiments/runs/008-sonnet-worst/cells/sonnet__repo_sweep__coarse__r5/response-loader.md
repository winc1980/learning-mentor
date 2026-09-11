まず先に共有しておきたいことがあります。作業ディレクトリの制約で、リポジトリ本体（`C:\Users\stama\winc\general\learning-mentor` 直下や `docs/`、`experiments/`）への実際のファイル読み取りは権限エラーでブロックされました。今作業できるのは `experiments/fixture` 配下だけのようです。

なので、これから出す地図は **`CLAUDE.md` に書かれている記述をもとに再構成したもの** です。実際のディレクトリを見たわけではない、という前提で聞いてください。

**中身の説明はまだしません。** まず位置関係だけです。

| 場所 | 何が入っているか（CLAUDE.md 記載ベース) |
|---|---|
| ルート直下 | 利用者に配る本体。`learning-mentor-prompt.md`（役割定義の正本）、`learning-mentor-setup.md`、`README.md`、`VERSION`、`learning-mentor-usage.md` など。**zip 配布物と一致する範囲** |
| `.claude/agents/learn.md` | 役割定義本文のコピー（`claude --agent learn` 用） |
| `docs/` | 企画意図・非配布の内部文書（`concept.md`、`tuning-options.md` など）。zip には入らない |
| `experiments/` | 規定が守られているかを測る実験ハーネス一式。`run.py`、`verify-fixture.py`、`blind.py`、`analyze.py`、`rubric.md`、`DECISIONS.md`、`fixture/`（被験体が読む実リポジトリ）、`runs/`（過去の実験データ）など |
| `.github/` | CI（`release.yml`）と issue テンプレート |

ここまでで、大きく3つの塊があることが分かります。

- **配布物**（ルート直下 + `.claude/agents/`）
- **内部文書**（`docs/`）
- **測定の仕組み**（`experiments/`）

一点、私が今いる `experiments/fixture` は、この中の「被験体が実際に読み込むリポジトリのコピー」に当たる場所のようです。

ここまでで、いったん止めます。**どこから詳しく知りたいですか？** 例えば

- このリポジトリで何をしようとしているのか（企画の全体像）
- 「役割定義が3箇所にコピーされる」という仕組みの理由
- 実験ハーネス（`experiments/`）が何を測っているか
- 今いる `fixture/` が何のためにあるのか

「全部ぼんやり知りたい」でも構いません。どこから広げるか一緒に決めましょう。