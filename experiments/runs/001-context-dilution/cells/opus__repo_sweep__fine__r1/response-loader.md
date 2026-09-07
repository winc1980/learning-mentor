まず全体像から。このリポジトリは **React Router v8 製のWebアプリ + 学習用ワークショップ教材** の2つが1つに入っています。

## 1. これは何のアプリか

`README.md` によると「学習用軽音タイムテーブル」。DBスキーマ（`app/db/schema.ts`）を見ると素性がはっきり分かります。

- `live`（ライブ本体） ← `live_day`（開催日と時間帯）
- `user` / `band`（バンドとリーダー）
- `band_participation`（どのバンドがどのライブに出るか、承認フラグ付き）
- `band_availability`（バンドが「この日のこの時間なら出られる」と出す希望）
- `live_application`（トークン付きの出演申込リンク）

要するに「複数バンドの空き時間を集めて、ライブのタイムテーブルを組む」アプリです。

## 2. トップレベルの地図

| 場所 | 中身 |
|---|---|
| `app/` | アプリ本体。ほぼここ |
| `drizzle/` | DBマイグレーション履歴（`.sql` + スナップショット9世代） |
| `issues/` | **課題文が7本**。これが教材の中核 |
| `docs/` | 環境構築・ワークショップの進め方 |
| `scripts/setup/` | `bun run setup` の中身。GitHubのラベル/Issue/ブランチ保護を自動作成する |
| `.env.example` / `components.json` / `tsconfig.json` | 設定類 |

`issues/` の7本は「わざと壊してある箇所」に対応しています（環境変数、useEffect、リンター未導入、肥大化コンポーネント、`useEffect`+`fetch` のままのデータ取得、バリデーション欠落など）。**このリポジトリのコードには意図的な不備がある**という前提で読んでください。

## 3. `app/` の内部構造 ― 層になっています

下から順に：

```
db/          … Drizzle のスキーマと接続 (schema.ts, index.ts)
  ↑
repositories/ … DBアクセスを閉じ込める層 (band / live / user)
  ↑
domain/      … entities/ = ドメインの型と規則、service/ = 業務ロジック
  ↑
middlewares/ … リクエストごとに「文脈」を用意する層
  ↑
routes/      … 画面とサーバー処理（loader/action）
  ↑
components/  … ui/ = shadcn の部品、common/ = 自作の共通部品
```

補助として `lib/`（`result.ts`, `plain-date.ts` など汎用ユーティリティ）と `hooks/`。

## 4. ルーティングの形が特徴的です

`app/routes.ts` が全ルートの設計図で、URLとファイルが**入れ子**で対応しています。

```
/app/live/:liveId/band/:bandId/availability
```

このURLに来ると、外側から順に
`app-middleware` → `live-middleware` → `band-middleware` → 各 `*-layout` → `availability.tsx`
と通過します。

`app/middlewares/repositories.ts` を見ると、この仕組みの狙いが見えます。`repositoryMiddleware` が `context` に3つのRepositoryを詰め、以降のルートはそれを取り出して使う。**「毎回DB接続を作らず、リクエスト単位で用意して下に渡す」** という形です。`user.ts` / `live.ts` / `band.ts` の各ミドルウェアも同じ発想で、ログイン中のユーザーや対象ライブを事前に解決していると読めます。

---

ここまでが地図です。次にどこを掘るか決めたいので、2つだけ確認させてください。

**(1)** React Router の **loader / action**（サーバー側でデータを取る・受け取る仕組み）は使ったことがありますか？ ここを知っているかどうかで、`routes/` の説明の粒度を変えます。

**(2)** 軽い問いを1つ。正確じゃなくて大丈夫です、「たぶん〜」で構いません。

上の階層図で、`routes/` から **`db/` を直接呼ばず**、間に `repositories/` を挟んでいます。これは何のためだと思いますか？ 次のどれかに近いもので答えてもらえれば十分です。

- A: 速くするため
- B: DBの都合が画面側に漏れないようにするため
- C: なんとなくの慣習
- D: 分からない

「分からない」で全く問題ありません。そこから説明します。