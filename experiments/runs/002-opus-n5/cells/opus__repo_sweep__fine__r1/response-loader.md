リポジトリをひととおり見ました。まず全体像から、順に細かくしていきます。

---

## 1. これは何のアプリか

**学習用の軽音ライブ・タイムテーブル管理アプリ**です。README を読むかぎり、これは「Phase 2」という学習会用の教材リポジトリで、**わざと壊してある箇所がある**のが特徴です。`issues/` に7つの課題（環境変数、useEffect、Biome導入、コンポーネント分割、loader化、バリデーション）が置いてあって、それを直しながら学ぶ、という作りになっています。

つまりこのリポジトリには2つの層があります。

| 層 | 場所 | 中身 |
|---|---|---|
| **アプリ本体** | `app/` | 実際のWebアプリのコード |
| **学習会の運営まわり** | `README.md` / `docs/` / `issues/` / `scripts/setup/` | 進め方の説明、課題文、環境セットアップ自動化 |

`scripts/setup/` は GitHub CLI を叩いて、ラベル作成・Issue登録・ブランチ保護・メンター招待などを自動でやるスクリプトです。アプリの動作とは無関係なので、いったん忘れて大丈夫です。

---

## 2. 技術スタック

`package.json` から読み取れる主なものです。

- **React Router v8**（フレームワークモード）— ルーティングだけでなく、サーバー側の処理も担当します
- **React 19**
- **Drizzle ORM + libSQL/SQLite** — DB
- **Tailwind CSS v4 + shadcn/ui + Radix UI** — 見た目
- **valibot** — バリデーション
- **jose**（JWT）+ **bcrypt** — 認証
- **Biome** — フォーマッタ／リンタ（※Issue 4 の「導入されていない」対象）
- **Bun** — パッケージマネージャ兼スクリプト実行

---

## 3. `app/` の中の構成 ← ここが本体

ここが一番大事なので、少し丁寧に。**下の層ほどDBに近い**と思って読んでください。

```
app/
├── routes.ts          ... URLとファイルの対応表（ルート定義の親玉）
├── root.tsx           ... アプリ全体のHTMLの外枠
│
├── routes/            ... 【画面 + サーバー処理】
├── components/        ... 【見た目の部品】
│   ├── ui/            ... shadcn/ui の汎用部品（button, card, input…）
│   └── common/        ... このアプリ独自の部品（DateInput, PasswordInput…）
├── hooks/             ... Reactのカスタムフック
│
├── middlewares/       ... リクエストごとの前処理（認証、依存の準備）
├── repositories/      ... 【DBアクセス】band / live / user
├── domain/            ... 【型とビジネスルール】
│   ├── entities/      ... Band, Live, User などの型定義
│   ├── service/       ... ドメイン固有の処理
│   └── data/errors.ts
├── db/                ... Drizzleの接続(index.ts)とテーブル定義(schema.ts)
└── lib/               ... 汎用ユーティリティ（日付、ハッシュ、Result型など）
```

**この層構造がこのリポジトリの設計の肝**です。`routes` が `repositories` を直接触らず、`middlewares` 経由で受け取る形になっています（`middlewares/repositories.ts` がそれをやっています）。

---

## 4. URLの構造

`app/routes.ts` を読むと、画面の全体像がそのまま出ています。

```
/                                          トップ
/auth/login, /auth/logout, /auth/register  認証
/app                                       ログイン後のホーム
/app/live/create                           ライブ作成
/app/live/:liveId                          ライブ詳細
  ├─ /application                          出演申し込み
  ├─ /timetable                            タイムテーブル
  ├─ /band/create                          バンド登録
  └─ /band/:bandId
       ├─ (index)                          バンドホーム
       └─ /availability                    出演可能時間の入力
/app/out/:_message/live-application/:token 外部向けリンク（API）
/*                                         404
```

`layout(...)` で囲まれている箇所が入れ子になっていて、`-middleware.tsx` と `-layout.tsx` がペアで各階層に置かれています。**middleware が「入っていいか／データを用意する」、layout が「共通の見た目」**という役割分担です。

---

## 5. DBのテーブル（`app/db/schema.ts`）

7つあります。関係はこうなっています。

```
user ──┬── live（ownerId）──┬── live_day（開催日と時間帯）
       │                    ├── band_participation ── band
       │                    ├── band_availability（バンドの空き時間）
       └── band（leaderId）  └── live_application（申し込み・token付き）
```

ざっくり言うと「**ユーザーがライブを立てる → バンドが参加申請する → 各バンドが出演可能時間を出す → タイムテーブルが組まれる**」というドメインです。

---

## 6. データの流れ（一本の線でまとめると）

```
ブラウザ
  ↓
routes.ts でURL解決
  ↓
middleware（認証チェック / repository を context に入れる）
  ↓
route の loader・action
  ↓
repository（Drizzle経由でSQLite）
  ↓
domain/entities の型に載せて返す
  ↓
コンポーネントが描画
```

---

ここまでが地図です。**一度に全部覚える必要はありません**が、ひとつだけ確認させてください。

**React Router の「フレームワークモード」（`loader` / `action` をファイルに書いて、サーバー側の処理もルートファイルが持つやり方）は使ったことがありますか？**

ここの経験があるかないかで、次にどこを掘るべきかが変わります。使ったことがなければ `routes/` と `middlewares/` の関係から、もう使い慣れているなら `domain` / `repositories` の層分けの意図（なぜこう分けているか）から見ていくのがよさそうです。

「たぶん触ったことある気がする」くらいの答えでも大丈夫です。