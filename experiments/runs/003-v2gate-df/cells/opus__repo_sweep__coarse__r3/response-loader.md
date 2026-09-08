一通り読みました。全体像の「地図」を先に渡します。**中身の説明はまだしません** — どこから知りたいかを選んでもらうためのものです。

## これは何のリポジトリか

学習会（Phase 2）用の教材です。**「軽音楽ライブのタイムテーブル管理アプリ」** が題材で、所々わざと壊してあり、Issue 1〜7 を解いて直しながら学ぶ、という作りになっています。

技術スタックは React Router v8（フレームワークモード）+ TypeScript + Drizzle ORM + SQLite(libSQL) + Tailwind + shadcn/ui です。

## 大きく4つのブロックに分かれています

| ブロック | 場所 | ざっくり何か |
|---|---|---|
| ① 学習教材そのもの | `README.md` / `docs/` / `issues/` | 進め方・環境構築・課題文 |
| ② アプリ本体 | `app/` | 実際に手を入れる場所。ここが本丸 |
| ③ DB定義とマイグレーション | `app/db/` / `drizzle/` / `drizzle.config.ts` | テーブル定義と、その変更履歴 |
| ④ セットアップ自動化 | `scripts/setup/` | `bun run setup` の中身。GitHub側の準備を自動でやる |

## ② アプリ本体（`app/`）の内訳

ここが一番ファイルが多いので、さらに分解します。

| 役割 | 場所 |
|---|---|
| ルーティングの定義（URLとファイルの対応表） | `app/routes.ts` |
| 各ページ（画面） | `app/routes/**` |
| リクエストの前処理 | `app/middlewares/` |
| DBアクセス | `app/repositories/` |
| ドメインの型・ルール | `app/domain/` |
| 見た目の部品（自作） | `app/components/common/` |
| 見た目の部品（shadcn/ui 由来） | `app/components/ui/` |
| 汎用ユーティリティ | `app/lib/` |
| React のカスタムフック | `app/hooks/` |

`app/routes/` の中はURL構造がそのままフォルダ構造になっています：

- `routes/home.tsx` … トップページ
- `routes/auth/` … ログイン・登録・ログアウト
- `routes/app/live/` … ライブ関連（作成・一覧・タイムテーブル・申込）
- `routes/app/live/band/` … バンド関連（作成・出演可能日）

## ここから

地図は以上です。次はどこか1つに絞って中身を見ていきましょう。

**いま一番気になっているのはどれですか？** 「全部ぼんやりしている」でも大丈夫です。よくある入り口としては：

- **A**: `app/routes.ts` と `routes/` の関係（URLとファイルがどう繋がるか）
- **B**: 1リクエストが届いてから画面が出るまでの流れ（middleware → loader → 画面）
- **C**: `domain` / `repositories` / `routes` という3層に分けている意図
- **D**: DB周り（`schema.ts` と `drizzle/` の関係）
- **E**: 特定のIssueを解きたいので、それに関係する場所

あわせて1つだけ確認させてください。**React Router（や Next.js などのフレームワーク）でのルーティングは、これまでに触ったことがありますか？** 説明の粒度を合わせたいだけなので、「ほぼ初めて」でも全然問題ありません。