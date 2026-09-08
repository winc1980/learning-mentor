リポジトリをひととおり見ました。全体像 → 各ディレクトリ、の順でいきます。

## まず、これは何のリポジトリか

**学習用の教材リポジトリ**です。README を読む限り、

- 題材は「軽音サークルのライブ タイムテーブル作成アプリ」
- **意図的に壊れている／未実装の箇所がある**
- それを Issue（全7件）として直しながら学ぶ

という構成です。なので「動いていないところがある」のは事故ではなく仕様です。ここを知らないとデバッグで消耗します。

## 技術スタック

| 領域 | 使っているもの |
|---|---|
| フレームワーク | **React Router v8**（フレームワークモード。旧 Remix 系。ルーティングだけでなくサーバー側の処理も持つ） |
| ビルド | Vite |
| DB | SQLite（libSQL）+ **Drizzle ORM** |
| 見た目 | Tailwind CSS v4 + shadcn/ui + Radix UI |
| 認証 | bcrypt（パスワードのハッシュ化）+ jose（JWT） |
| バリデーション | valibot |
| リンタ/フォーマッタ | Biome |
| ランタイム | Bun |

## ディレクトリの地図

```
├── README.md          ← まずここ。進め方と Issue 一覧
├── docs/              ← 環境構築、ワークショップの進め方
├── issues/            ← 課題7件の原稿（Markdown）
├── scripts/setup/     ← 初回セットアップ。GitHub に Issue を自動作成したりする
├── drizzle/           ← DB のマイグレーション履歴（自動生成。手で書かない）
└── app/               ← ★アプリ本体。ほぼここだけ触る
```

## app/ の中身 ── ここが本体

**レイヤーが分かれています。** 上から下に依存する形です。

```
routes/        画面 + サーバー処理（loader / action）
   ↓
middlewares/   共通の前処理（ログイン確認、リポジトリの注入など）
   ↓
repositories/  DB アクセスをまとめた層
   ↓
db/            Drizzle のスキーマ定義（テーブル定義）
```

それを横から支えるのが：

| ディレクトリ | 役割 |
|---|---|
| `domain/entities/` | アプリ上の「もの」の型定義。`live.ts` `band.ts` `user.ts` など。中身は素の型だけ |
| `domain/service/` | 型に収まらないドメインのロジック |
| `lib/` | 汎用ユーティリティ。`result.ts`（成功/失敗の表現）、`plain-date.ts` / `plain-time.ts`（日付・時刻）、`hash.ts`、`serde.ts` |
| `sessions/` | ログインセッションと JWT の発行・検証 |
| `components/ui/` | shadcn/ui が生成したパーツ（button, card, input…）。基本いじらない |
| `components/common/` | このアプリ独自の共通部品（`DateInput`, `PasswordInput`, `toast` など） |
| `hooks/` | React のカスタムフック |

## 画面の構造（`app/routes.ts`）

`routes.ts` が**ルーティングの設計図**です。ファイル名でなく、このファイルで URL とファイルの対応を明示的に書く方式。

```
/                          トップ
/auth/login | logout | register
/app                       ← app-middleware（ログイン必須の関門）
  /app                     ホーム
  /app/live/create         ライブ作成
  /app/live/:liveId        ← live-middleware
      /                    ライブのホーム
      /application         出演申請
      /band/create         バンド作成
      /timetable           タイムテーブル
      /band/:bandId        ← band-middleware
          /                バンドのホーム
          /availability    出演可能時間の登録
*                          404
```

**`layout(...)` の入れ子がそのまま画面の入れ子とアクセス制御の入れ子になっています。** `xxx-middleware.tsx` が各階層の入り口に立っていて、「ログインしているか」「そのライブは存在するか」「そのバンドのメンバーか」を手前でチェックしてから中に入れる、という設計です。

なぜこうするか：各ページで毎回「ログイン確認」を書くと、書き忘れた1ページが穴になります。関門を1箇所に集めれば漏れません。

## データモデル（`app/db/schema.ts`）

テーブルは7つ。関係はだいたいこうです。

```
user ──owner──> live ──> live_day（開催日と時間帯）
  │                │
  └──leader──> band ──band_participation──> live（参加。approved で承認制）
                 │
                 └──> band_availability（この日のこの時間なら出られる）

live_application（トークン付きの外部からの出演申請）
```

つまり **「ライブに複数の日程があり、バンドが各日程での出演可能時間を出し、それを元にタイムテーブルを組む」** アプリです。

---

ここまでで、地図としては足ります。

ひとつだけ聞かせてください。**正確じゃなくて大丈夫です。「たぶん」でも単語だけでも構いません**が、いま挙げた中で

**`middlewares/` と `repositories/` は、どちらが「DB を直接触る側」だと思いますか？**

（AかB、どちらかを選ぶだけでOK。「分からない」でも構いません）

ここの答えで、次にどこを詳しく見るか決めます。