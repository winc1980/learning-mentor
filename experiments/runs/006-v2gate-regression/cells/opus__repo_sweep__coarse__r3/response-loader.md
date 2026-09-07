一通り読みました。まず**場所だけ**挙げます（それぞれが何をどう動かしているかの説明は、まだしません）。地図を先に渡して、そのあとどこから案内するかを選んでもらう形にします。

## これは何のリポジトリか

`musiclive-timetable` — 軽音ライブのタイムテーブル作成アプリで、**Phase 2 の学習用教材**です。README によると、意図的に壊れている／未実装の箇所があり、`issues/` にある7つの課題を解いていく形になっています。

## 大きく4つの層に分かれています

| 層 | 場所 | 置かれているもの |
|---|---|---|
| ルーティング・画面 | `app/routes.ts`, `app/routes/**` | URL とページの対応、各ページ本体 |
| ドメイン | `app/domain/**` | エンティティ定義、業務ルール |
| データアクセス | `app/db/**`, `app/repositories/**` | DBスキーマ、DB読み書き |
| 部品・道具 | `app/components/**`, `app/hooks/**`, `app/lib/**` | UI部品、共通ロジック |

## もう少し細かい内訳

**画面まわり**
- `app/routes.ts` — 全URLの一覧表。ここが**画面構成の目次**です
- `app/routes/auth/` — login / logout / register
- `app/routes/app/live/` — ライブ作成、応募、タイムテーブル
- `app/routes/app/live/band/` — バンド登録、出演可能日
- `app/routes/app/*-middleware.tsx` — 各階層に1つずつある「前処理」ファイル
- `app/middlewares/` — 上とは別の場所にある middleware 群（`user.ts` / `band.ts` / `live.ts` / `repositories.ts`）

**データまわり**
- `app/db/schema.ts` — テーブル定義（Drizzle ORM）
- `app/repositories/` — `user.ts` / `band.ts` / `live.ts`
- `app/domain/entities/` — user, band, live, live-day, live-application, band-availability, band-participation
- `drizzle.config.ts` — DB接続設定

**UI部品**
- `app/components/ui/` — shadcn/ui 由来の汎用部品（button, card, input など）。基本さわらない領域
- `app/components/common/` — このアプリ独自の部品（DateInput, PasswordInput, toast など）

**共通ロジック**
- `app/lib/` — `result.ts`, `hash.ts`, `plain-date.ts`, `serde.ts`, `error.ts` など
- `app/hooks/` — `useIsActive.ts`, `useLiveDayFormData.tsx`

**教材そのもの**
- `README.md` — 進め方と課題一覧
- `docs/環境構築.md`, `docs/ワークショップの進め方.md`
- `issues/01〜07.md` — 課題7本の本文

## 技術スタック（名前だけ）

React Router v8 / React 19 / TypeScript / Drizzle ORM + libSQL / Tailwind CSS v4 / shadcn/ui / valibot / jose（JWT）/ Biome / Bun

---

ここからが本題です。2つ教えてください。

1. **この中で、いま一番気になっているのはどこですか。** 「全部ぼんやり」でも大丈夫です。その場合は「最初のIssueに関係する場所」から案内します
2. 校正のために1つだけ — **React Router の loader / action は使ったことがありますか？** ここがあるかないかで、`routes/` の説明の入り口が変わります