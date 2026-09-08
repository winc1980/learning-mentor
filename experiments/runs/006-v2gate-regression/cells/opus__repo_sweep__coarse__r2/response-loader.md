一通り読みました。学習会用の「軽音タイムテーブル」アプリですね（React Router v8 + Drizzle + SQLite/libSQL）。

**まずは場所だけ挙げます。中身の説明はまだしません。** 地図があると、次に「どこを見るか」を選べるので。

## リポジトリの外枠

| 役割 | 場所 |
|---|---|
| 学習会の進め方・課題一覧 | `README.md` |
| 環境構築、PR の出し方 | `docs/` |
| 依存パッケージと `bun run dev` などのコマンド | `package.json` |
| 各種設定 | `vite.config.ts` / `react-router.config.ts` / `drizzle.config.ts` / `tsconfig.json` |
| DB のマイグレーション履歴（9世代） | `drizzle/` |

アプリ本体は全部 `app/` の下です。

## `app/` の中（レイヤーごと）

| 役割 | 場所 |
|---|---|
| URL とファイルの対応表 | `app/routes.ts` |
| 画面そのもの（ライブ、バンド、認証など） | `app/routes/**` |
| ルートに入る前に挟まる処理 | `app/middlewares/`（`user` / `live` / `band` / `repositories`）と `routes` 内の `*-middleware.tsx` |
| DB への読み書き | `app/repositories/`（band / live / user） |
| DB のテーブル定義・接続 | `app/db/schema.ts` / `app/db/index.ts` |
| 業務ルールと型（ライブ、バンド、参加可否など） | `app/domain/entities/` ほか |
| 汎用ユーティリティ | `app/lib/`（`result` / `serde` / `hash` / `plain-date` など） |
| 見た目の部品 | `app/components/ui/`（shadcn 生成物）と `app/components/common/`（自作） |
| React のカスタムフック | `app/hooks/` |

ざっくり言うと **routes → middlewares → repositories → db** という縦の流れがあって、その横に `domain` `lib` `components` が補助として置かれている、という形です。

---

ここからは1つずつ見ていきましょう。**いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。

よくある入り口だと、

- **A**: `routes.ts` と `routes/` — URL を叩いたとき、どのファイルが動くのか
- **B**: `middlewares/` — 一番見慣れない部分かもしれません
- **C**: `repositories/` と `db/` — データがどう出入りしているか
- **D**: `domain/` — なぜ `routes` から DB を直接触らずに層を分けているのか

あと1つだけ確認させてください。**React（コンポーネントや `useState`）はすでに書いたことがありますか？** そこが分かると説明の粒度を合わせられます。