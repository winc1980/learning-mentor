リポジトリの中身を一通り見てきました。まず全体像を掴んでもらって、そのあと気になったところを深掘りする、という順で進めますね。

## これは何のプロジェクトか

`package.json` の名前や README から、**「学習用軽音タイムテーブル」**という、ライブイベントの出演バンド管理・タイムテーブル作成アプリだと分かります。

README を見ると、これは実際のプロダクトではなく **学習会（Phase 2）用の演習リポジトリ**です。意図的に壊れている/未実装の箇所があり、それを Issue を解決しながら直していく、という使い方をするものです。

## 技術スタック（package.json から）

- **React Router v8** — 画面遷移だけでなく、データ取得やサーバー処理も担うフレームワーク（Next.jsに近い立ち位置）
- **Drizzle ORM** — TypeScriptでDB操作を書けるORM（ORM = SQLを直接書かずにコードでテーブルを操作するための道具）
- **libSQL**（SQLite系） — データベース本体
- **Tailwind CSS + shadcn/ui** — スタイリングとUI部品
- **valibot** — 入力値のバリデーション用ライブラリ
- **Biome** — フォーマッター/リンター

ここまでで「知ってる」「使ったことない」がある技術はありますか？

## トップレベルの構成

```
├── app/            ← アプリ本体（メイン。後で詳しく）
├── docs/           ← 学習会向けドキュメント（環境構築、進め方）
├── drizzle/        ← DBのマイグレーション履歴（自動生成）
├── scripts/setup/  ← 環境構築時にGitHub Issueを自動作成するスクリプト
├── .github/        ← CODEOWNERS等
├── package.json / tsconfig.json / vite.config.ts / drizzle.config.ts / react-router.config.ts / components.json
```

設定ファイル群はそれぞれ「TypeScriptの設定」「ビルドツール(Vite)の設定」「Drizzleの設定」「React Routerの設定」「shadcn/uiの設定」に対応しています。

## app/ の中身（一番重要）

`app/routes.ts` を見ると、URLの構造がそのまま見えます：

```
/                          → 認証前トップ
/auth/login, /register     → 認証系
/app/                      → ログイン後トップ
/app/live/create           → ライブ作成
/app/live/:liveId/         → 個別ライブ（タイムテーブル、出演申請など）
/app/live/:liveId/band/:bandId/  → 出演バンド個別ページ
```

これに対応して `app/routes/` 以下に、URL構造とほぼ同じ階層でページコンポーネントが並んでいます。`live-layout.tsx` や `band-layout.tsx` は「そのURL配下で共通のレイアウト（ヘッダーやタブなど）」、`*-middleware.tsx` は「そのページ群に入る前に必ず通す共通処理」（例えばログインチェックなど）を担っています。

それ以外のディレクトリは役割ごとに分かれています：

| ディレクトリ | 役割 |
|---|---|
| `components/ui/` | shadcn由来の汎用UI部品（ボタン、カードなど） |
| `components/common/` | このアプリ独自の共通コンポーネント |
| `domain/entities/` | Band, Live, User などのドメインモデル（アプリの中心概念） |
| `domain/service/` | ドメインロジック（複数エンティティにまたがる処理） |
| `repositories/` | DBアクセスをまとめる層 |
| `db/` | Drizzleのスキーマ定義とDB接続 |
| `middlewares/` | ルート横断の共通処理（認証など） |
| `sessions/` | JWT・セッション管理 |
| `lib/` | 日付処理、Result型、エラー処理などの汎用ユーティリティ |
| `hooks/` | カスタムフック |

---

ここまでで、全体のマップとしては大枠つかめたと思います。次にどこを深掘りしたいですか？例えば

- 「`middlewares/` と `routes.ts` のネストがどう対応してるのか分からない」
- 「`domain/` と `repositories/` の役割の違いがピンとこない」
- 「README にあった Issue の話（例：`useEffect`+`fetch` のまま、など）から見ていきたい」

のように、気になる箇所から一緒に見ていきましょう。