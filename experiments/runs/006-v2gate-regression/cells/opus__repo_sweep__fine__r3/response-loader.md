一通り読みました。学習用の教材リポジトリ（軽音タイムテーブル / Phase 2 課題）ですね。

**まずは場所だけ挙げます。中身がどう動くかの説明はまだしません。** 地図を先に渡して、そのうえでどこから見るか選んでもらうためです。

## 大きく4つのゾーン

| ゾーン | 場所 | 何が置かれているか |
|---|---|---|
| **アプリ本体** | `app/` | 画面もサーバー処理もここに全部 |
| **DBマイグレーション** | `drizzle/` | スキーマ変更の履歴（9世代分） |
| **課題** | `issues/` (7件) | `01-env.md` 〜 `07-validation.md` |
| **手順書** | `README.md`, `docs/` | 進め方・環境構築 |

## `app/` の中の内訳

| 役割 | 場所 |
|---|---|
| ルーティング定義（1ファイル） | `app/routes.ts` |
| 画面・エンドポイント | `app/routes/` — `auth/`（login・logout・register）、`app/`（home・live・band）、`app/api/` |
| ミドルウェア | `app/middlewares/` — user / band / live / repositories<br>※ `app/routes/` 内にも `*-middleware.tsx` が別途あります |
| セッション・認証 | `app/sessions/` — `jwt.ts`, `sessions.ts` |
| DB接続とスキーマ | `app/db/` — `index.ts`, `schema.ts` |
| DBアクセス層 | `app/repositories/` — user / band / live |
| ドメインモデル | `app/domain/entities/` （user, band, live, live-day, live-application ほか）, `domain/service/` |
| 汎用ユーティリティ | `app/lib/` — `result.ts`, `plain-date.ts`, `hash.ts`, `serde.ts` など |
| UIパーツ | `app/components/ui/`（shadcn の生成物）と `app/components/common/`（自前） |
| フック | `app/hooks/` |

## 技術スタック（package.json より）

React Router v8 / React 19 / Drizzle ORM + libSQL / valibot / jose（JWT）/ bcrypt / Tailwind v4 + shadcn / Biome / ランタイムは Bun。

---

ここで一度止めます。

この地図の中で、**いま一番気になっているのはどれですか。** 「全部ぼんやりしている」でも大丈夫です。その場合は、こちらから見る順番の案を出します。

もし取り組む予定の Issue が決まっていれば、それを教えてもらえると、関係する場所だけに絞って案内できます（例：Issue 6 のデータ取得なら `routes/` と `repositories/` の関係あたり）。