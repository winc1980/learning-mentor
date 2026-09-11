このリポジトリ、ざっと読んできました。まず全体の性質だけ先にお伝えします。

## このリポジトリの正体

`docs/ワークショップの進め方.md` を見る限り、**学習用のワークショップリポジトリ**です。`issues/` フォルダに課題（`01-env.md`〜`07-validation.md`）があり、それを1つずつ解いてPull Requestを出す、という進め方をする教材のようです。

作っているアプリは「軽音ライブのタイムテーブル管理システム」（`package.json` の name が `musiclive-timetable`）。ライブを主催し、バンドを参加させ、各バンドの出演可能時間からタイムテーブルを組む、というドメインです。

## 技術スタック（ざっくり）

- **React Router v8**（フレームワークモード。Next.jsに近いファイルベースではなく `app/routes.ts` でルート定義を書く形式）
- **Drizzle ORM + libSQL**（DB。SQLite系）
- **valibot**（バリデーション）
- **jose + bcrypt**（JWTセッション、パスワードハッシュ）
- **shadcn/ui + Tailwind**（UI部品）
- **Biome**（フォーマッタ/リンタ。Issue 4で自分で導入する課題になっている）
- **Bun**（パッケージマネージャ兼実行環境）

## 場所だけ挙げます（中身の説明はまだしません）

`app/` の中は役割ごとにフォルダが分かれています。

| フォルダ | 役割（と思われるもの） |
|---|---|
| `app/routes/` | ページ・URLごとの画面（ルーティングの実体） |
| `app/routes.ts` | ルーティング定義（どのURLがどのファイルに対応するか） |
| `app/domain/entities/` | ドメインのデータ構造（`live`, `band`, `user` など） |
| `app/domain/service/`, `app/domain/data/` | ドメインロジック・エラー定義 |
| `app/repositories/` | DBとのやり取り（データ取得・保存） |
| `app/db/` | DBスキーマ定義・接続 |
| `app/sessions/` | ログインセッション・JWT関連 |
| `app/middlewares/` | ルートに挟み込む認証・データ取得処理 |
| `app/components/ui/` | shadcn由来の汎用UI部品 |
| `app/components/common/` | このアプリ独自の共通コンポーネント |
| `app/hooks/` | カスタムフック |
| `app/lib/` | 日付処理やエラー型などの汎用ユーティリティ |

その他：
- `issues/` … 取り組む課題一覧
- `docs/` … 環境構築・進め方のドキュメント
- `.claude/agents/` … このセッションのようなAIエージェント設定

---

ここまでで、**次はどこから知りたいですか？**

- 「ルーティングの仕組み（`routes.ts` の書き方）」
- 「`domain` / `repositories` / `routes` の役割分担」
- 「認証・セッション周り（`sessions/`, `middlewares/`）」
- 「DBスキーマ（テーブル同士の関係）」
- 「全部ぼんやり」でも大丈夫です

どれか選んでもらえれば、そこから掘っていきます。