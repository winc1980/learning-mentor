ひととおり読みました。全体像 → 層の分かれ方 → ディレクトリ対応、の順で説明します。

---

## 1. これは何のアプリか

**軽音楽サークルのライブのタイムテーブルを作るWebアプリ**です。ドメインモデル（`app/db/schema.ts`）を見ると登場人物がはっきり分かります。

```
ユーザー ──(リーダー)──> バンド
                          │
                          ├─ ライブに参加申請 (band_participation)
                          └─ 「この時間なら出られる」を登録 (band_availability)

ライブ ──> ライブ開催日 (live_day) ── 各日に開始/終了時刻
```

つまり「バンドの出演可能時間を集めて、ライブ当日のタイムテーブルを組む」のが主題です。

そしてもう一つ大事なこと ── **これは学習用の教材リポジトリです。** README に「所々、壊れて動かない箇所がある」と明記されていて、Issue 1〜7 を解きながら学ぶ構成になっています。なので、変なコードを見つけたときに「自分の理解不足か、意図的な壊れか」の両方を疑う必要があります。

---

## 2. 技術スタック

| 役割 | 使っているもの |
|---|---|
| フレームワーク | **React Router v8**（フレームワークモード。Remix の後継にあたる形態） |
| ビルド | Vite |
| DB | SQLite（libSQL）+ **Drizzle ORM** |
| UI | Tailwind CSS v4 + shadcn/ui（Radix UI ベース） |
| 認証 | bcrypt（パスワードハッシュ）+ jose（JWT/署名） |
| バリデーション | valibot |
| ランタイム | Bun |

ここで一つだけ用語を。**「フレームワークモード」**というのは、React Router がルーティングだけでなく、サーバー側のデータ取得（`loader`）やフォーム送信処理（`action`）まで面倒を見るモードのことです。だから「フロントエンドのライブラリ」ではなく、これ一つでバックエンドも兼ねています。`app/routes/` の中にサーバーで動くコードが混ざっているのはそのためです。

---

## 3. リクエストが流れる層

このリポジトリで一番押さえるべきはここです。1つのページ表示が、こういう順で処理されます。

```
ブラウザ
   ↓
app/routes.ts          … URL とファイルの対応表
   ↓
middlewares (*-middleware.tsx)  … 認証チェック・共通データの準備
   ↓
routes/**/*.tsx の loader        … データ取得（サーバーで動く）
   ↓
repositories/                    … DB アクセスの実装
   ↓
db/ (Drizzle) → SQLite
   ↓
routes/**/*.tsx の default export … 画面の描画（React コンポーネント）
```

**同じファイルの中に、サーバーで動く `loader` と、ブラウザで動くコンポーネントが同居している**のがこの構成の最大の特徴です。`app/routes/app/live/band/home.tsx` を開くと、上半分が `loader`（DB を触っている）、下半分が `BandHomePage`（JSX を返す）になっているのが見えます。

---

## 4. ディレクトリ対応表

### `app/` ── アプリ本体

| パス | 何が置いてあるか |
|---|---|
| `routes.ts` | **URL 定義の中心。まずここを読むと地図が手に入ります** |
| `root.tsx` | HTML の一番外側（`<html>` タグごと） |
| `routes/` | 各ページ。ファイル1つ = 1画面（+ そのサーバー処理） |
| `middlewares/` | 認証・共通データ準備。ルートより先に走る |
| `repositories/` | DB 読み書きの実装（`band` / `live` / `user` の3つ） |
| `domain/entities/` | アプリ内で使う型定義。`band.ts` は5行だけ |
| `domain/service/` | エンティティ単体に収まらないロジック |
| `db/` | Drizzle の接続 (`index.ts`) とテーブル定義 (`schema.ts`) |
| `sessions/` | ログインセッション（Cookie）の管理 |
| `components/ui/` | shadcn/ui から入れた汎用部品。**基本さわらない** |
| `components/common/` | このアプリ独自の部品。さわるならこっち |
| `hooks/` | 独自 React フック |
| `lib/` | 日付・時刻・ハッシュ・Result 型などの道具箱 |

### ルーティングの入れ子（`routes.ts` の形がそのままディレクトリ構造）

```
/                            トップ
/auth/login, register, logout 認証
/app                         ログイン後のホーム
/app/live/:liveId            ライブ個別
    ├ /application           出演申請
    ├ /band/create           バンド作成
    ├ /timetable             タイムテーブル
    └ /band/:bandId          バンド個別
        └ /availability      出演可能時間の登録
```

`*-middleware.tsx` と `*-layout.tsx` がペアで各階層に置かれていますね。**middleware が「入っていいか」を判定し、layout が「共通の見た目」を担当する**、という役割分担です。

### `app/` の外

| パス | 中身 |
|---|---|
| `drizzle/` | マイグレーション履歴（9個。DB スキーマの変更ログ） |
| `scripts/setup/` | GitHub の設定を自動化するスクリプト（`bun run setup` の実体）。**アプリ本体とは無関係** |
| `docs/` | 環境構築・ワークショップの進め方 |
| `.env.example` | 必要な環境変数のひな形（Issue 1 がこれ） |

---

## 5. 特徴的な設計を2つ

**① 依存性注入っぽい仕組み**
`middlewares/repositories.ts` で、リポジトリの実体を作って `context` に詰めています。各ルートは `context.get(repositoryContext)` で取り出すだけ。ルートが「DB の具体的な実装」を直接 import しない形になっています。

**② Result 型**
`app/lib/result.ts` があって、リポジトリは例外を投げずに `{ success: true/false }` を返しています。`home.tsx` の `if (!result.success)` がそれです。エラー処理を try-catch ではなく戻り値でやる流儀ですね。

---

## 最初に読むならこの順

1. `app/routes.ts` ── 地図
2. `app/db/schema.ts` ── データの形
3. `app/routes/app/live/band/home.tsx` ── loader → repository → 画面、の1往復が短くて分かりやすい

---

一気に話したので、ここで一つだけ確認させてください。**正確じゃなくて大丈夫です。単語だけでも「たぶん〜」でも構いません。**言葉にすると自分でどこが曖昧か見つかるので、その材料として聞いています。

**いまの説明の中で、一番しっくり来なかった／ピンと来なかったのはどこですか？**

「middleware のところ」「Result 型って何」「そもそも loader が分からない」みたいな粒度で大丈夫です。そこを次に掘ります。