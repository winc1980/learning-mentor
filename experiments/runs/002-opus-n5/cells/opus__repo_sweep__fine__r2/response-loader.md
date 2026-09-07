リポジトリをひととおり読みました。全体像 → ディレクトリごとの役割、の順で説明します。

---

## 1. まず、これは何のリポジトリか

**「学習用 軽音タイムテーブル」** という Web アプリで、**学習会（Phase 2）の教材**です。ここが普通のリポジトリと違う一番大事な点です。

README にこう書いてあります：

> - 所々、壊れて動かない箇所がある
> - Issueを解決しながら技術の実装を学ぶ

つまり **わざと壊されている／未実装の箇所がある** 前提のコードベースです。`issues/` に課題が7つ入っていて、これを潰していくのが目的になっています。

| # | 難易度 | 内容 |
|---|---|---|
| 1 | EASY | 環境変数を設定しよう |
| 2 | EASY | トップページから各ページへの導線がない |
| 3 | NORMAL | 通知の表示が `useEffect` で囲われていない |
| 4 | NORMAL | フォーマッター・リンターが未導入 |
| 5 | HARD | `application.tsx` のコンポーネントが肥大化 |
| 6 | HARD | データ取得が `useEffect` + `fetch` のまま |
| 7 | EXTREME | 早稲田メールのバリデーションがない |

アプリ自体のドメインは「**ライブ（イベント）に、バンドが出演申請して、各バンドの出られる時間帯を集めて、タイムテーブルを組む**」というものです。

---

## 2. 技術スタック（`package.json` から）

- **React Router v8**（フレームワークモード）— Next.js のようにルーティング・サーバー処理・ビルドまで面倒を見るフレームワークとして使われています
- **Drizzle ORM + SQLite（libsql）** — DB
- **shadcn/ui + Tailwind CSS v4 + Radix UI** — UI
- **valibot** — バリデーション
- **jose（JWT）+ bcrypt** — 認証
- **Biome** — リンター/フォーマッター（※ Issue 4 の通り、**まだ設定が入っていません**。依存だけある状態）
- **Bun** — スクリプト実行に使用（`bun run setup`）

---

## 3. ルートの構成

```
├── app/          ← アプリ本体。ほぼ全部ここ
├── drizzle/      ← DBマイグレーション履歴（9世代分）
├── docs/         ← 環境構築.md / ワークショップの進め方.md
├── issues/       ← 課題7つの本文（setup時にGitHub Issueとして登録される）
├── scripts/      ← setup用スクリプト
├── .env.example  ← Issue 1 で使う
└── README.md
```

---

## 4. `app/` の中 — ここが本体

**レイヤー（層）で分かれています。** 上から下に依存する形です。

```
routes/        画面とサーバー処理     ← ユーザーに一番近い
   ↓
middlewares/   リクエスト前の共通処理
   ↓
repositories/  DB読み書きの実装
   ↓
db/            スキーマ定義・接続
```

これに、層をまたいで使われる `domain/` `lib/` `components/` `hooks/` `sessions/` が横から刺さります。

### `app/routes/` — 画面 + サーバー処理

URL とファイルの対応は `app/routes.ts` が**明示的に**定義しています（ファイル名の規約ではなく、コードで書く方式）。ネストがそのまま URL のネストです。

```
/                          routes/home.tsx           トップ（Issue 2 の舞台）
/auth/login|logout|register                          認証
/app                       routes/app/home.tsx       ログイン後トップ
/app/live/create                                     ライブ作成
/app/live/:liveId          .../live/home.tsx          ライブ詳細
/app/live/:liveId/application                        出演申請（Issue 5 の舞台）
/app/live/:liveId/timetable                          タイムテーブル
/app/live/:liveId/band/:bandId/availability          バンドの出られる時間
/app/out/:_message/live-application/:token           外部向けURL（トークン認証）
/api/hello-react-router                              Issue 6 が絡むAPI
```

ここで**ファイル名の付き方に規則がある**ので覚えておくと読みやすいです：

- `*-layout.tsx` … 見た目の共通枠（ヘッダーなど）
- `*-middleware.tsx` … その配下に入る前の**認可チェック**（ログイン済みか、そのライブの権限があるか等）
- それ以外 … 実際のページ

### `app/db/` — DB定義

`schema.ts` に7テーブル。ここを読むとアプリの全体像が一番早く掴めます。

- `user` … ユーザー（`mail`, `passwordHash`）
- `live` … ライブイベント
- `live_day` … ライブの開催日と時間帯（1ライブに複数日）
- `band` … バンド
- `band_participation` … どのバンドがどのライブに出るか（`approved` フラグあり）
- `band_availability` … バンドが出られる時間帯
- `live_application_table` … 外部からの出演申請（`token` で識別）

### `app/domain/` — ビジネス上の「もの」の型

`entities/` は素朴な型定義です。たとえば `band.ts` は全体でこれだけ：

```ts
export type Band = { id: number; name: string; leaderId: number }
```

**DBのテーブル型（`BandTable`）とは別に、アプリ側の型を用意している**のがポイントです。DB の都合とアプリの都合を切り離すためですね。

### `app/repositories/` — DBアクセスの実装

`band.ts` / `live.ts` / `user.ts`。それぞれ **インターフェース（`BandRepository`）と実装（`BandRepositoryImpl`）** のペアになっています。

### `app/middlewares/` — リクエスト共通処理

`repositories.ts` が分かりやすい例です：

```ts
export const repositoryContext = createContext<{...}>()

export const repositoryMiddleware = async ({ context }) => {
  context.set(repositoryContext, {
    userRepository: new UserRepositoryImpl(db),
    ...
  })
}
```

リクエストごとにリポジトリ一式を作って context に詰め、各ルートはそこから取り出して使う。**ルートが `db` を直接触らないようにする**仕組みです。

### `app/components/`

- `ui/` … shadcn/ui の自動生成（button, card, dialog…）。基本さわらない
- `common/` … このアプリ独自（`DateInput`, `TimeInput`, `PasswordInput`, `toast` など）

### `app/lib/` — 汎用ユーティリティ

`plain-date.ts` `plain-time.ts` `plain-datetime-utils.ts`（日付時刻を文字列で扱う道具。schema が `"yyyy/mm/dd"` の text なのと対応）、`result.ts`（成功/失敗を型で表す）、`hash.ts`（bcrypt）、`serde.ts`（シリアライズ）。

### `app/sessions/`

`jwt.ts` と `sessions.ts`。jose で JWT を作ってクッキーセッションに載せる認証まわり。

---

## 5. 読む順のおすすめ

初見なら **`app/db/schema.ts` → `app/routes.ts` → 気になるルート1つ** の順が効率的です。データ構造と URL 構造が分かれば、残りは追いかけられます。

---

ここまでで、まず一点だけ確認させてください。**正確じゃなくて大丈夫です。単語だけでも「たぶん〜」でも、分からないでも構いません。** 言葉にすると自分でどこが曖昧か見つかるので、その材料として聞いています。

上の 4 層のうち、**「DB に対して実際にクエリを投げている」のはどれだと思いますか？**

- A: `app/routes/`
- B: `app/middlewares/`
- C: `app/repositories/`
- D: `app/domain/`

あわせて、もう一つだけ。**React Router を「フレームワークとして」使うのは初めてですか？**（Next.js などを触ったことがあるかどうかでも構いません）ここで説明の粒度を合わせたいので聞いています。