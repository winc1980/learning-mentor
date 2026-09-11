一通り読みました。全体像をつかみたいとのことなので、**まずは「どこに何があるか」の地図だけ渡します。中身が何をしているかの説明は、まだしません。** 一度に全部やると確実に飽和するので、地図を見てから見たい場所を選んでもらうほうが早いです。

## まず、このリポジトリの性格

READMEを見るかぎり、これは**学習会（Phase 2）用の教材リポジトリ**です。軽音サークルのライブ用タイムテーブル管理アプリで、**わざと壊してある／未実装の箇所**があり、`issues/01〜07` の課題を潰していく形になっています。

技術スタックは `package.json` から読むと、React Router v8 + React 19 + Drizzle ORM + SQLite(libsql) + Tailwind + shadcn/ui + valibot、パッケージマネージャは bun です。

（なお README の「諸注意」に、生成AIにコードを書かせない・調べさせない方針が明記されていました。このセッションはもともとコードを書かないので方針とは衝突しませんが、私の使い方も「答えをもらう」ではなく「解説してもらう」に寄せてもらうのが安全だと思います。）

## トップレベルの地図

| 場所 | 役割 |
|---|---|
| `README.md` / `docs/` | 学習会の進め方、環境構築手順、画像 |
| `issues/01〜07.md` | 課題文そのもの（`bun run setup` でGitHub Issueとして起票される） |
| `app/` | **アプリ本体。ほぼ全部ここ** |
| `drizzle/` | DBのマイグレーション履歴（SQLとスナップショット、10世代ぶん） |
| `scripts/setup/` | 初回セットアップ用スクリプト（Issue作成やブランチ保護設定） |
| `package.json` / `tsconfig.json` / `vite.config.ts` / `components.json` | 各種設定 |
| `.github/CODEOWNERS` / `.vscode/` | レビュー担当設定、エディタ設定 |

## `app/` の中の地図

| 場所 | 役割 |
|---|---|
| `app/root.tsx` / `app/routes.ts` | アプリの最外殻と、**URLとファイルの対応表** |
| `app/routes/` | 画面とサーバー処理。ここが一番厚い |
| `app/middlewares/` | `user.ts` `live.ts` `band.ts` `repositories.ts` |
| `app/sessions/` | `sessions.ts`（Cookie）、`jwt.ts`（トークン） |
| `app/db/` | `schema.ts`（テーブル定義）、`index.ts`（接続） |
| `app/repositories/` | `user.ts` `band.ts` `live.ts` |
| `app/domain/entities/` | `user` `live` `live-day` `band` `band-availability` `band-participation` `live-application` |
| `app/domain/service/` `app/domain/data/` | `create-application-url.ts` / `errors.ts` |
| `app/components/ui/` | shadcn/ui 由来の汎用部品（button, input, card …） |
| `app/components/common/` | このアプリ独自の共通部品（DateInput, PasswordInput, toast …） |
| `app/hooks/` | `useIsActive.ts` `useLiveDayFormData.tsx` |
| `app/lib/` | `result.ts` `error.ts` `hash.ts` `serde.ts` `utils.ts` `plain-date/time` 系 |
| `app/app.css` | スタイル |

## URLと画面の対応（`app/routes.ts` より）

| URL | ファイル |
|---|---|
| `/` | `routes/home.tsx` |
| `/auth/login` `/logout` `/register` | `routes/auth/` |
| `/app` | `routes/app/home.tsx` |
| `/app/live/create` | `routes/app/live/create.tsx` |
| `/app/live/:liveId` | `routes/app/live/home.tsx` |
| `/app/live/:liveId/application` | `routes/app/live/application.tsx`（課題5の肥大化コンポーネント） |
| `/app/live/:liveId/timetable` | `routes/app/live/timetable.tsx` |
| `/app/live/:liveId/band/create` | `routes/app/live/band/create.tsx` |
| `/app/live/:liveId/band/:bandId` | `routes/app/live/band/home.tsx` |
| `/app/live/:liveId/band/:bandId/availability` | `routes/app/live/band/availability.tsx` |
| `/api/hello-react-router` ほか | `routes/app/api/` |

`*-layout.tsx` と `*-middleware.tsx` が各階層に対で置かれていて、これが `routes.ts` の入れ子構造と対応しています。

---

地図はここまでです。次に、**あなたが選んだ1箇所だけ**を掘ります。

いま一番気になっているのはどれですか。「全部ぼんやり」でも大丈夫です。

- **A**: `routes.ts` の入れ子と `layout` / `middleware` の関係（アプリの骨格）
- **B**: リクエストが来てから画面が出るまでの流れ（route → middleware → repository → db）
- **C**: `domain` / `repositories` / `db` が分かれている理由（レイヤ構成）
- **D**: 認証まわり（`sessions/` と `middlewares/user.ts`）
- **E**: まず課題を1つ選んで、その周辺から逆算して読みたい

あわせて1つだけ確認させてください。**React Router の `loader` / `action` は触ったことがありますか？**（「名前は見たことある」「初めて」でも大丈夫です）ここの答え次第で、説明の入り口を変えます。