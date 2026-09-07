一通り見ました。学習用の軽音タイムテーブルアプリ（React Router v8 + Drizzle ORM + SQLite/libSQL）ですね。

**まずは場所だけ挙げます。中身の説明はまだしません。** 地図を渡す段階です。

## 全体の地図

### ルート直下

| 何 | 場所 |
|---|---|
| 課題（Issue）一覧・進め方 | `README.md` |
| 環境構築・作業手順 | `docs/` |
| DBマイグレーション履歴 | `drizzle/` |
| セットアップスクリプト | `scripts/` |
| 環境変数のひな形 | `.env.example` |
| 設定類 | `package.json` / `tsconfig.json` / `biome.jsonc` / `components.json` |

### `app/` の中（アプリ本体）

| 役割 | 場所 |
|---|---|
| URL とファイルの対応表 | `app/routes.ts` |
| HTML の外枠 | `app/root.tsx` |
| 各ページの実体 | `app/routes/**` |
| DB 接続とテーブル定義 | `app/db/index.ts` / `app/db/schema.ts` |
| DB への読み書き | `app/repositories/` |
| ドメインの型・ルール | `app/domain/entities/` / `app/domain/service/` |
| リクエスト前に挟まる処理 | `app/middlewares/` |
| ログイン状態の保持・JWT | `app/sessions/` |
| 汎用ユーティリティ | `app/lib/` |
| 画面部品（自作） | `app/components/common/` |
| 画面部品（shadcn/ui 由来） | `app/components/ui/` |
| React のカスタムフック | `app/hooks/` |

### ページの階層

`app/routes.ts` を見ると、URL がこう入れ子になっています（ファイル名だけ追えば構造が分かります）。

```
/                     → routes/home.tsx
/auth/login | logout | register
/app                  → 認証チェック → レイアウト → home
/app/live/create
/app/live/:liveId     → live 用チェック → レイアウト
      ├ /             home
      ├ /application
      ├ /band/create
      ├ /timetable
      └ /band/:bandId → band 用チェック → レイアウト
            ├ /       home
            └ /availability
```

---

ここまでが地図です。**この中で、いま一番気になっているのはどこですか。**「全部ぼんやり」でも大丈夫です。選んでもらった1つだけを掘り下げます。

よくある入り口としては、たとえば：

- **`routes.ts` の `layout` / `prefix` / `route`** — この入れ子が実際に何をしているのか
- **`middlewares/` と `routes/**/*-middleware.tsx` の関係** — 似た名前が2箇所にあって混乱しやすい所です
- **`domain/` `repositories/` `db/` の3層** — なぜ分かれているのか
- **README の Issue のどれか** — 実際に手を動かす対象から逆算する

あと、粒度を合わせたいので1つだけ確認させてください。**React Router（や Next.js などのルーティング）を使ったことはありますか。** 「触ったことはある」「今回が初めて」くらいの粗さで大丈夫です。