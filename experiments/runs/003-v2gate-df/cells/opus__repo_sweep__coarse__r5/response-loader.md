一通り読みました。これは**軽音のライブ・タイムテーブル管理アプリ**で、Issue を解いて学ぶ学習用リポジトリですね（README にある Phase 2 の教材）。

まずは**場所だけ挙げます。中身がどう動くかの説明はまだしません。** 地図を先に渡して、どこから見るかはあなたに選んでもらいます。

## 全体の輪郭

React Router v8（フレームワークモード）+ Drizzle ORM + SQLite/libSQL、ランタイムは Bun。`app/` がアプリ本体、それ以外はほぼ設定・教材です。

## 1. アプリ本体（`app/`）

| 役割 | 場所 |
|---|---|
| URL とファイルの対応表 | `app/routes.ts` |
| 全ページの外枠 | `app/root.tsx` |
| 各ページの実体 | `app/routes/**`（`auth/`, `app/`, `app/live/`, `app/live/band/`, `api/`） |
| ルートごとの前処理 | `app/routes/**/*-middleware.tsx` と `app/middlewares/` |
| 画面部品（自作） | `app/components/common/` |
| 画面部品（shadcn 生成物） | `app/components/ui/` |
| 業務ルール・型 | `app/domain/entities/`, `app/domain/service/`, `app/domain/data/` |
| DB アクセス | `app/repositories/`（band / live / user） |
| DB 接続とテーブル定義 | `app/db/index.ts`, `app/db/schema.ts` |
| ログイン状態の保持 | `app/sessions/`（`sessions.ts`, `jwt.ts`） |
| 汎用ユーティリティ | `app/lib/`（日付・時刻、Result 型、ハッシュ、シリアライズ等） |
| React のカスタムフック | `app/hooks/` |

## 2. 教材・課題

| 役割 | 場所 |
|---|---|
| 課題 7 本の本文 | `issues/01〜07-*.md` |
| 環境構築・進め方 | `docs/環境構築.md`, `docs/ワークショップの進め方.md` |
| Issue や保護設定を自動作成 | `scripts/setup/` |

## 3. 設定まわり

`package.json`（スクリプト）、`react-router.config.ts`、`vite.config.ts`、`drizzle.config.ts`、`tsconfig.json`、`biome.jsonc`、`.env.example`、`drizzle/`（マイグレーション履歴）。

---

構成上の特徴を一つだけ言うと、**ルーティング → ミドルウェア → リポジトリ → DB** という縦の流れと、**domain / lib** という横串、この2軸で整理されています。ここが掴めると、どのファイルを開くべきか自分で判断できるようになります。

---

この中で、**いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。選びやすいように、よくある入り口を挙げておきます。

- **A** ページを開いてから画面が出るまでの流れ（`routes.ts` → middleware → route ファイル）
- **B** データの流れ（route → repository → DB）
- **C** ログイン・認証まわり（`sessions/`, `middlewares/user.ts`）
- **D** `domain/` と `lib/` に何を置いているのかという設計の話
- **E** そもそも Issue を1本解きたいので、それに必要な範囲だけ

あわせて一つだけ教えてください（説明の粒度を合わせたいので）。**React Router のいわゆる「フレームワークモード」（loader / action を書くやつ）は、触ったことありますか？** 「名前は聞いたことある」程度でも構いません。