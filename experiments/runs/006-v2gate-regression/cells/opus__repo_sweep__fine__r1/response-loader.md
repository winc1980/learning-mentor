一通り読みました。**まずは「どこに何があるか」の地図だけ出します。中身がどう動くかの説明はまだしません。** 地図を見てから、気になるところを選んでもらう形にしたいです。

---

## これは何のリポジトリか

`README.md` によると、**学習会（Phase 2）用の教材リポジトリ**です。「軽音サークルのライブ・タイムテーブル管理アプリ」が題材で、**わざと壊してある箇所**があり、Issue を解いて直しながら学ぶ、という作りになっています。

技術スタックは `package.json` から読み取れる範囲で：React Router v8 / React 19 / Drizzle ORM + libSQL(SQLite) / Tailwind + shadcn-ui / valibot / jose(JWT) + bcrypt。

---

## 全体の区分け

このリポジトリは、大きく **3つの層**に分かれています。

| 区分 | 場所 | ざっくり何が置いてあるか |
|---|---|---|
| ① 学習会の運営まわり | `README.md` / `docs/` / `issues/` / `scripts/` / `.github/` | アプリ本体ではない。課題文・手順書・セットアップ自動化 |
| ② アプリ本体 | `app/` | 実際に動くWebアプリのコード。ここが主戦場 |
| ③ 設定・DBまわり | ルート直下の各設定ファイル / `drizzle/` | ビルド設定、DBマイグレーション |

---

## ① 学習会の運営まわり（アプリのコードではない）

| 役割 | 場所 |
|---|---|
| 全体の進め方・課題一覧 | `README.md` |
| 環境構築の手順 | `docs/環境構築.md` |
| Issue着手〜PRまでの手順 | `docs/ワークショップの進め方.md` |
| 課題7つの本文 | `issues/01-env.md` 〜 `issues/07-validation.md` |
| `bun run setup` の中身 | `scripts/setup/` |

---

## ② アプリ本体（`app/`）── ここが本題

`app/` の中がさらに層に分かれています。**上から下へ、画面に近い順**に並べます。

| 層 | 場所 | 置かれているもの |
|---|---|---|
| ルーティング定義 | `app/routes.ts` | URL と下のファイルの対応表 |
| 画面・エンドポイント | `app/routes/**` | 各ページ。`auth/`（ログイン・登録）と `app/live/**`（ライブ・バンド・タイムテーブル） |
| ミドルウェア | `app/middlewares/` + 各 `*-middleware.tsx` | リクエストの前段で走る処理 |
| セッション／認証 | `app/sessions/jwt.ts`, `sessions.ts` | ログイン状態の保持 |
| ドメイン | `app/domain/entities/`, `domain/service/` | `user` `band` `live` `live-day` などの「業務上の概念」 |
| データアクセス | `app/repositories/` | `band.ts` `live.ts` `user.ts` |
| DB接続・テーブル定義 | `app/db/index.ts`, `app/db/schema.ts` | |
| 汎用ユーティリティ | `app/lib/` | `result.ts` `hash.ts` `plain-date.ts` など |
| UI部品 | `app/components/ui/`（shadcn由来） / `components/common/`（このアプリ独自） | |
| Reactフック | `app/hooks/` | |

ルート直下は `app/root.tsx`（アプリの一番外側）と `app/app.css`。

---

## ③ 設定・DB

`vite.config.ts` / `react-router.config.ts` / `tsconfig.json` / `components.json` / `drizzle.config.ts`、そして `drizzle/` に9個のマイグレーション履歴。`.env.example` は課題①に直結しています。

---

ここまでが地図です。

**この中で、いま一番気になっているのはどれですか。**「全部ぼんやりしてる」でも大丈夫ですし、その場合はこちらから入り口を提案します。

参考までに、よくある入り口はこのあたりです：

- **A**「URLを開いてから画面が出るまでの流れ」（`routes.ts` → `routes/**` → repository → db の縦の線を1本追う）
- **B**「認証まわり」（`sessions/` + `middlewares/` + `routes/auth/`）
- **C**「domain / repositories / lib って何のために分かれてるの？」という層分けの意図
- **D** 特定のIssueを解くのに必要な範囲だけ

あと1つだけ確認させてください。**React Router（や Next.js のようなフレームワーク）で、サーバー側の処理を書いた経験はありますか？** ここが分かると、説明の粒度を合わせられます。