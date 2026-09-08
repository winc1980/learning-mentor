ひととおり見ました。全体像 →ディレクトリの役割 →データの流れ、の順で説明します。

---

## 1. まず、これは何のリポジトリか

2つの性格が同居しています。

**(A) 学習教材としてのリポジトリ**
- `README.md` … Phase 2（学習会）の進め方。**課題（Issue）が7つ**用意されていて、番号順に EASY→EXTREME
- `docs/` … 環境構築、ワークショップの進め方
- `issues/` … 上の課題7つの本文（Markdown）。`scripts/setup` がこれを読んでGitHubのIssueとして自動作成する
- `scripts/setup/` … フォーク後の初期セットアップ（ラベル作成・ブランチ保護・メンター招待など）。**アプリ本体とは無関係**

**(B) アプリ本体**
軽音サークルの**ライブのタイムテーブル管理アプリ**です（`package.json` の name は `musiclive-timetable`）。ライブを作る → バンドが参加申請する → 各バンドが出演可能時間を登録する → タイムテーブルを組む、という流れのものです。

**「所々わざと壊れている」**のがこの教材の肝で、Issueがその壊れた箇所に対応しています。

---

## 2. 技術スタック（`package.json` から）

| 役割 | 使っているもの |
|---|---|
| フレームワーク | **React Router v8**（フレームワークモード。Remixの後継にあたるもの） |
| DB | SQLite（libSQL）+ **Drizzle ORM** |
| UI | Tailwind CSS v4 + shadcn/ui（Radix UIベース） |
| 認証 | bcrypt（パスワードハッシュ）+ jose（JWT） |
| バリデーション | valibot |
| ランタイム/ツール | Bun、Vite、Biome（※Issue 4 で「まだ導入されていない」とされている） |

ここで一番大きいのは **React Router v8 がフレームワークとして使われている**点です。「ルーティングライブラリ」ではなく、サーバー側の処理（`loader` / `action`）まで持っています。これを知っているかどうかで、以降の読み方がかなり変わります。

---

## 3. `app/` の中の構造

役割ごとに層が分かれています。**外側（画面）から内側（DB）へ**並べると：

```
app/routes/       … URLに対応する画面 + サーバー処理（loader/action）
app/components/   … 画面の部品
app/middlewares/  … リクエストの前処理（認証・データの事前取得）
app/repositories/ … DBアクセスをまとめた層
app/domain/       … アプリ固有の「概念」の定義（型・変換・エラー）
app/db/           … Drizzleのテーブル定義と接続
app/lib/          … 汎用ユーティリティ（日付・時刻・ハッシュ・Result型など）
app/sessions/     … セッション / JWT
```

個別に補足すると：

- **`app/routes.ts`** … URLとファイルの対応表。ここが**地図**です。迷ったらまずここ。`/app/live/:liveId/band/:bandId/availability` のような入れ子が全部書かれています
- **`app/components/ui/`** … shadcn/ui が生成したもの（button, card, dialog…）。**自分で書いたコードではない**ので、読み込む必要は基本ありません
- **`app/components/common/`** … このアプリ独自の部品（`DateInput`, `TimeInput`, `PasswordInput` など）
- **`app/domain/entities/`** … `live`, `band`, `user`, `band-availability` など。DBの行そのままではなく、アプリで扱いやすい形に整えた型が置かれています
- **`app/lib/result.ts`** … 見つけましたが、このプロジェクトはエラーを **例外ではなく `Result` 型（成功/失敗を戻り値で表す）** で扱っています。`if (!result.success) throw result.error` という書き方が各所に出てきます
- **`drizzle/`** … マイグレーションSQLの履歴。手で書くものではなく、`schema.ts` から生成されたもの

---

## 4. データベースの構造（`app/db/schema.ts`）

7つのテーブルがあり、関係はこうなっています。

```
user ──owns──> live ──has──> live_day（開催日と時間帯）
  │              │
  └──leads──> band ──band_participation──> live （参加とその承認状態）
                 │
                 └──band_availability──> live_day（このバンドが出られる時間帯）

live_application（トークン付きの外部からの参加申請）
```

「ライブには複数の開催日があり、バンドは日ごとに出演可能時間を出す」という構造だと読み取れます。

---

## 5. 1リクエストの流れ（ここが一番大事）

`/app/live/3` を開いたときを例にすると：

```
routes.ts でURLを解決
  → app-middleware.tsx（ログイン確認・リポジトリ準備）
    → live-middleware.tsx（:liveId のライブを取得して context に入れる）
      → live/home.tsx の loader() がサーバーで走る
          context から liveContext / repositoryContext を取り出す
          bandRepository.getByLiveId() で参加バンドを取得
          return { live, bandParts }
        → 同じファイルの default export のコンポーネントが
          loaderData を受け取って描画
```

ポイントは2つあります。

1. **`middlewares/repositories.ts` が「依存を context に入れる」役割**をしていること。各ルートは `context.get(repositoryContext)` で取り出すだけで、DBのことを知らなくて済む
2. **1つのファイルの中にサーバー処理（`loader`）と画面（コンポーネント）が同居している**こと。上半分がサーバー、下半分がブラウザ、という読み方になります

そして──`README.md` の **Issue 6「データ取得が `useEffect`+`fetch` のままになっている」** は、まさにこの `loader` を使わずに書かれている箇所がある、という課題です。`app/routes/app/api/hello-react-router.ts` というファイルが残っているのも、その名残に見えます。

---

## 確認させてください（1つだけ）

説明の粒度を合わせたいので聞きます。

**React Router の `loader` / `action` を使った開発は、経験ありますか？**（あるいは Next.js のサーバー側の処理でも構いません）

- **触ったことがある** → 上の説明で足りているはずなので、次はどこか1つのIssueに絞って設計の話をしましょう
- **初めて / 名前は聞いたことがある程度** → 「なぜ `loader` があるのか」「`useEffect`+`fetch` と何が違うのか」から説明します。**このリポジトリの課題の半分くらいがそこに関係している**ので、ここを押さえるのが一番効率がいいです

---

次にどこを深掘りするかの候補も置いておきます（選んでもらう形で）：

- **A**: `loader` / `action` の仕組み（Issue 3・6 に直結）
- **B**: middleware と context の関係（このアプリ全体の骨格）
- **C**: repositories / domain / db の層分け（なぜ3つに分かれているのか）
- **D**: とりあえずIssue 1から手を動かしたい