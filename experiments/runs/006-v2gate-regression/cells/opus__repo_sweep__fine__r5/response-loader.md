一通り読みました。まず **場所だけ挙げます（中身の説明はまだしません）。** 地図を渡す感じで、案内はそのあと、どこから見るか選んでもらってから始めます。

## まずこのリポジトリの性格

`README.md` と `issues/` を見ると、これは普通のプロダクトではなく **学習会（Phase 2）用の教材リポジトリ** ですね。「所々、壊れて動かない箇所がある」「Issueを解決しながら学ぶ」と書かれています。題材は軽音サークルのライブ用タイムテーブル管理アプリです。

## トップレベル

| 場所 | 何が置かれているか |
|---|---|
| `app/` | アプリ本体。ほぼすべてのコードがここ |
| `docs/` | 環境構築・ワークショップの進め方 |
| `issues/` | 課題7本の原文（01〜07） |
| `drizzle/` | DBマイグレーションの履歴（9世代分） |
| `scripts/setup/` | GitHub側の初期セットアップ用（学習会の運営用。アプリ本体とは無関係） |
| ルート直下の設定 | `package.json` / `vite.config.ts` / `react-router.config.ts` / `drizzle.config.ts` / `tsconfig.json` / `components.json` |

## `app/` の中の層

| 層 | 場所 |
|---|---|
| ルーティング定義（1ファイルに全部） | `app/routes.ts` |
| 画面とサーバー処理 | `app/routes/**` |
| ルートの入れ物 | `app/root.tsx`, `app/app.css` |
| 認証・認可の共通処理 | `app/middlewares/` （band / live / user / repositories） |
| セッションとトークン | `app/sessions/` （sessions.ts, jwt.ts） |
| DB接続とテーブル定義 | `app/db/` （index.ts, schema.ts） |
| DBアクセス | `app/repositories/` （band / live / user） |
| ドメインの型・ルール | `app/domain/entities/`, `app/domain/service/`, `app/domain/data/errors.ts` |
| 汎用ユーティリティ | `app/lib/` （result, serde, hash, plain-date 系, error, utils） |
| 画面部品（自作） | `app/components/common/` |
| 画面部品（shadcn/ui 由来） | `app/components/ui/` |
| React フック | `app/hooks/` |

## 画面の並び（`app/routes.ts` から読み取れる形）

```
/                        トップ
/auth/login, register, logout
/app/                    ログイン後ホーム
  /app/live/create
  /app/live/:liveId/            ライブ個別
        /application  /timetable  /band/create
        /band/:bandId/           バンド個別
              /availability
  /app/out/:_message/live-application/:token   外部向けURL
/api/hello-react-router
*                        404
```

`*-middleware.tsx` と `*-layout.tsx` が階層ごとにペアで置かれているのが、この構成の一番の特徴です。

---

ここまでが地図です。**この中で、いま一番気になっているのはどれですか。**「全部ぼんやりしている」でも大丈夫で、その場合はこちらから入り口を提案します。

あと1つだけ確認させてください（説明の粒度を合わせるためです）。**React Router のフレームワークモード（loader / action を書くやつ）は、触ったことありますか？** 「名前は聞いたことある」程度でも構いません。