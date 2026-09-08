リポジトリをひととおり見ました。全体像から順に説明します。

## 1. これは何のアプリか

`README.md` によると、**学習用の「軽音楽ライブのタイムテーブル管理アプリ」** です。しかも普通のリポジトリではなく、**わざと壊してある学習教材** です。Issue 1〜7（EASY〜EXTREME）が用意されていて、それを直しながら学ぶ構成になっています。

DBのテーブル（`app/db/schema.ts`）を見ると、アプリのドメインがはっきり分かります：

- `live`（ライブ）→ `live_day`（ライブの開催日・時間帯）
- `user`（ユーザー）、`band`（バンド）
- `band_participation`（どのバンドがどのライブに出るか・承認済みか）
- `band_availability`（バンドがその日の何時〜何時なら出られるか）
- `live_application`（外部からの出演申込。トークン付きURL方式）

つまり「**ライブを作る → バンドが参加申請する → 各バンドの空き時間を集める → タイムテーブルを組む**」というアプリです。

## 2. 技術スタック

`package.json` から：

| 領域 | 使っているもの |
|---|---|
| フレームワーク | **React Router v8**（フルスタックモード。旧Remix系） |
| UI | React 19 / Tailwind CSS v4 / shadcn/ui / Radix UI |
| DB | SQLite（libSQL）+ **Drizzle ORM** |
| 認証 | bcrypt（パスワードハッシュ）+ jose（JWT） |
| バリデーション | valibot |
| リンタ | Biome ※ Issue 4「未導入」の対象 |
| ランタイム | Bun |

## 3. ディレクトリ構成

```
app/                    ← アプリ本体。ほぼここ
├─ routes.ts            ★ URL設計の全体地図
├─ root.tsx             HTMLの外枠
├─ routes/              ページ（URLごとのファイル）
├─ components/
│   ├─ ui/              shadcn/uiの自動生成物。基本いじらない
│   └─ common/          このアプリ独自の共通部品
├─ db/                  スキーマ定義とDB接続
├─ domain/              型定義とビジネスロジック
├─ repositories/        DBアクセス処理
├─ middlewares/         リクエストごとの前処理
├─ sessions/            ログインセッション・JWT
├─ hooks/               Reactの独自フック
└─ lib/                 汎用ユーティリティ（日付・時刻・Result型など）

docs/                   環境構築・進め方（日本語）
drizzle/                DBマイグレーション履歴（自動生成）
scripts/setup/          学習会用のGitHub自動セットアップ。アプリとは無関係
```

## 4. 一番大事なファイル：`app/routes.ts`

このアプリを理解する入口はここです。**URLとファイルの対応表** が全部書いてあります。抜粋すると：

- `/app/live/:liveId` → ライブのトップ
- `/app/live/:liveId/timetable` → タイムテーブル
- `/app/live/:liveId/band/:bandId/availability` → バンドの空き時間入力

そして `layout(...)` が入れ子になっています。たとえば `live-middleware.tsx` → `live-layout.tsx` → `home.tsx` という3重。

## 5. データの流れ（層構造）

このリポジトリは層がきれいに分かれています。

```
routes/（画面）
   ↓ contextから取り出す
middlewares/（前処理でrepositoryを準備）
   ↓
repositories/（SQLを書く場所）
   ↓
db/（Drizzleのスキーマ）
```

`app/middlewares/repositories.ts` がその要で、リクエストが来るたびに `UserRepository` / `LiveRepository` / `BandRepository` を作って context に詰めています。各ページはそこから取り出して使う、という形です。

そして `domain/entities/` には `Band = { id, name, leaderId }` のような **アプリ側の型** が定義されています。DBのテーブル型とは別に持っているのがポイントです。

---

ここまでで全体像です。ここから先、どこを掘るかは何に取り組むかで変わってきます。

**確認したいことが一つあります。** React Router（またはRemix / Next.js）のような「サーバーとクライアントが1ファイルに同居する」タイプのフレームワークは、触ったことはありますか？

ここの答えで次の説明の深さを変えます。というのも、このリポジトリで一番つまずきやすいのは `loader` / `action` / `middleware` の関係で、そこを知っているかどうかで話す順番が変わるからです。

「名前は聞いたことある程度」でも「Next.jsならある」でも構いません。