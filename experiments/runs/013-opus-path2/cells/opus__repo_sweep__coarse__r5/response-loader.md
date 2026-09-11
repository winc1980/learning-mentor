一通り読みました。これは「学習用軽音タイムテーブル」というワークショップ用のリポジトリですね。React Router v8 + Drizzle ORM + SQLite(libsql) 構成のWebアプリです。

**まずは場所だけ挙げます。中身の説明はまだしません。** 地図があるだけで、どこから見るか選べるようになるはずなので。

## 大きく4つのかたまり

| かたまり | 場所 | ざっくり何の置き場か |
|---|---|---|
| ① ワークショップの運営まわり | `README.md` / `docs/` / `issues/` / `scripts/setup/` | 課題一覧、環境構築手順、セットアップ自動化 |
| ② アプリ本体 | `app/` | ここが開発対象 |
| ③ データベース定義 | `app/db/` / `drizzle/` | スキーマとマイグレーション履歴 |
| ④ 設定ファイル群 | `package.json` / `vite.config.ts` / `tsconfig.json` / `components.json` | ビルド・型・UIライブラリの設定 |

## ② `app/` の中の内訳

| 役割 | 場所 |
|---|---|
| URLとファイルの対応表（入口） | `app/routes.ts` |
| 画面そのもの | `app/routes/` 配下（`auth/`, `app/live/`, `app/live/band/` など） |
| ルートごとの前処理 | `app/middlewares/` と、各所の `*-middleware.tsx` |
| ログイン状態の保持 | `app/sessions/`（`sessions.ts`, `jwt.ts`） |
| DBへの読み書き | `app/repositories/`（band / live / user） |
| ドメインの型・ルール | `app/domain/`（`entities/`, `service/`, `data/`） |
| 自作の共通部品 | `app/components/common/` |
| shadcn/ui の既製部品 | `app/components/ui/` |
| 汎用ユーティリティ | `app/lib/`（日付・ハッシュ・Result型など） |
| カスタムフック | `app/hooks/` |

## ①の課題ファイル

`issues/01-env.md` 〜 `07-validation.md` の7本。環境変数、トップページの導線、useEffect、Biome、コンポーネント分割、loader、バリデーション、の順に並んでいます。

---

ここからが本題です。**この中で、いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫ですし、「まず取り組む予定の Issue に関係するところ」という選び方でも構いません。

あと、深さを合わせたいので1つだけ確認させてください。**React Router の loader / action は書いたことがありますか？** （「名前は聞いたことがある」「初めて見た」でもOKです）