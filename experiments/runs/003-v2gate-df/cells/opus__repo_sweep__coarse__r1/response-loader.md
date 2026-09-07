一通り読みました。軽音サークルのライブ用タイムテーブル管理アプリで、React Router v8 をフレームワークとして使った構成です。

**まずは「どこに何があるか」の場所だけ挙げます。中身の説明はまだしません。**

## 全体の地図

| 役割 | 場所 |
|---|---|
| **設定・エントリ** | `package.json` / `vite.config.ts` / `react-router.config.ts` / `tsconfig.json` / `app/root.tsx` |
| **URL の一覧表** | `app/routes.ts` （どのURLがどのファイルに対応するかを1枚で定義） |
| **画面（ページ本体）** | `app/routes/**` （`home.tsx`, `auth/login.tsx`, `app/live/timetable.tsx` など） |
| **画面の共通枠・前処理** | `app/routes/**/​*-layout.tsx` と `*-middleware.tsx` |
| **API エンドポイント** | `app/routes/app/api/**` |
| **UI 部品（汎用）** | `app/components/ui/**` （shadcn/ui 由来のボタン・カード等） |
| **UI 部品（このアプリ固有）** | `app/components/common/**` （`DateInput`, `PasswordInput` など） |
| **画面用のカスタムフック** | `app/hooks/**` |
| **DB 接続とテーブル定義** | `app/db/index.ts` / `app/db/schema.ts` （Drizzle ORM + libSQL） |
| **DB 読み書きの窓口** | `app/repositories/**` （`user.ts` / `band.ts` / `live.ts`） |
| **業務ルール・型** | `app/domain/entities/**` / `app/domain/service/**` / `app/domain/data/errors.ts` |
| **横断的な処理の差し込み** | `app/middlewares/**` （`user.ts`, `band.ts`, `live.ts`, `repositories.ts`） |
| **汎用ユーティリティ** | `app/lib/**` （日付・ハッシュ・Result型・シリアライズ等） |
| **DBマイグレーション履歴** | `drizzle/**` / `drizzle.config.ts` |
| **セットアップ用スクリプト** | `scripts/setup/**` （`bun run setup` の中身。アプリ本体とは無関係） |
| **手順書** | `README.md` / `docs/環境構築.md` / `docs/ワークショップの進め方.md` |

## 大まかな階層

```
ブラウザ → routes.ts → routes/**（画面） → repositories/**（DB窓口） → db/**（Drizzle） → SQLite
                          ↑ middlewares/** が途中に挟まる
                          ↑ domain/** の型・ルールを共通で参照
```

---

この中で、**いま一番気になっているのはどれですか。** 「全部ぼんやりしてる」でも大丈夫です。その場合は、Issue 1〜7 のどれかに取り組む予定があるなら、それに関係する場所から見ていくのが効率がいいです。

あと1つだけ確認させてください。**React Router（や Next.js のようなルーティング付きフレームワーク）は使ったことがありますか？** これによって、`routes.ts` と `*-layout.tsx` の話をどこから始めるかが変わります。

（このセッションはコードを書かず、説明とヒントだけを出します。README の「AIにコードを書かせない」方針と競合しないようにしています）