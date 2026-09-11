リポジトリを一通り読みました。まず全体像だけお伝えします（**中身の詳しい説明はまだしません**、位置関係の地図だけです）。

## このリポジトリの性質

`docs/ワークショップの進め方.md` と `issues/` を見る限り、これは**学習会・ワークショップ用の教材リポジトリ**です。`issues/01-env.md` 〜 `07-validation.md` という課題が用意されていて、1つずつ解いて Pull Request を出す、という進め方になっています。アプリ自体は「ライブイベントとバンドのタイムテーブルを管理するWebアプリ」（`musiclive-timetable`）のようです。

## 技術スタック（package.json より）

| 役割 | 使っているもの |
|---|---|
| フレームワーク | React Router（v8、ルーティングとサーバー処理を兼ねるフレームワークモード） |
| UI | React 19 + Tailwind CSS + shadcn/ui（`radix-ui`ベースのコンポーネント集） |
| DB | Drizzle ORM + libsql（SQLite系） |
| 認証まわり | jose（JWT）、bcrypt（パスワードハッシュ） |
| バリデーション | valibot |
| Lint/Format | Biome |
| パッケージ管理/実行 | bun |

## ディレクトリの地図

| 場所 | 何があるか |
|---|---|
| `app/routes.ts` | 全ルーティング定義（読んだ画面ページの一覧表） |
| `app/routes/` | 実際の画面・ページのコード（`auth/`＝ログイン等、`app/live/`＝ライブ関連、`app/live/band/`＝バンド関連） |
| `app/domain/entities/` | ドメインの型定義（Band, Live, User など） |
| `app/domain/service/`, `app/domain/data/` | ドメインロジック・エラー定義 |
| `app/repositories/` | DBへの読み書き処理 |
| `app/db/` | DBスキーマ・接続設定（Drizzle） |
| `app/middlewares/` | React Router のミドルウェア（認証チェックなど） |
| `app/sessions/` | セッション・JWT関連 |
| `app/components/ui/` | shadcnの汎用UI部品（button, cardなど） |
| `app/components/common/` | このアプリ固有の共通コンポーネント |
| `app/hooks/`, `app/lib/` | カスタムフック、汎用ユーティリティ |
| `issues/` | ワークショップの課題一覧 |
| `docs/` | 環境構築・進め方の手順書 |

一通りの位置関係は以上です。**いま一番気になっているのはどのあたりですか？**（例：「ルーティングの仕組み」「domain/repositoriesの分け方」「特定の画面の動き」など、「全部ぼんやり」でも大丈夫です）

ちなみに React Router のフレームワークモードや Drizzle ORM は、使ったことはありますか？それによって説明の始め方を変えたいです。