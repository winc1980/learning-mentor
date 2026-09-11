一通り読みました。軽音サークルのライブ・タイムテーブル管理アプリで、React Router v8（フルスタックモード）+ Drizzle ORM + SQLite という構成です。

**まずは場所だけ挙げます。中身の説明はまだしません。** どこに何があるかの地図です。

## トップレベル

| 何 | 場所 |
|---|---|
| アプリ本体のコード | `app/` |
| 学習会の進め方・環境構築 | `README.md`, `docs/` |
| 課題の内容（7件） | `issues/01-env.md` 〜 `07-validation.md` |
| ビルド・設定まわり | `package.json`, `vite.config.ts`, `tsconfig.json`, `components.json` |

## `app/` の中（ここが本体）

| 役割 | 場所 | ファイル数 |
|---|---|---|
| **URL とファイルの対応表** | `app/routes.ts` | 1 |
| **各ページ／API** | `app/routes/**` | 22 |
| **アプリの最上位** | `app/root.tsx`, `app/app.css` | 2 |
| **DB のテーブル定義と接続** | `app/db/schema.ts`, `app/db/index.ts` | 2 |
| **DB への読み書き** | `app/repositories/` (band, live, user) | 3 |
| **ドメインの型・ルール** | `app/domain/entities/`, `domain/service/`, `domain/data/` | 9 |
| **ログイン状態の管理** | `app/sessions/` (sessions.ts, jwt.ts) | 2 |
| **リクエスト前に挟まる処理** | `app/middlewares/` + `routes/**/*-middleware.tsx` | 4 + 4 |
| **画面部品（自作）** | `app/components/common/` | 8 |
| **画面部品（shadcn/ui 生成物）** | `app/components/ui/` | 14 |
| **React のフック** | `app/hooks/` | 2 |
| **汎用ユーティリティ** | `app/lib/` (日付, ハッシュ, Result 型など) | 8 |

`app/routes/` の中はさらに `auth/`（ログイン・登録・ログアウト）、`app/`（ログイン後の画面）、`app/live/`（ライブ関連）、`app/live/band/`（バンド関連）と階層になっていて、**URL の階層とほぼ一致**しています。

---

ここからは、気になるところを1つずつ見ていきましょう。二つ教えてください。

1. **この中で、いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。取り組む予定の Issue があるなら、それに関係する場所から見るのが近道です。
2. サーバー側のコードを書いた経験（Rails / Express / Django など、何でも）はありますか？ 説明の粒度を合わせたいだけなので、「ない」でも全然構いません。