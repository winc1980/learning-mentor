リポジトリを一通り見ました。全体像から順に説明します。

## 0. まず、これは2重構造のリポジトリです

ここが最初のポイントで、ファイルが大きく **2種類** 混ざっています。

- **① 学習教材としてのファイル** — `README.md` / `docs/` / `issues/` / `scripts/setup/` / `.github/`
- **② 題材となるWebアプリ本体** — `app/` / `drizzle/` / 各種設定ファイル

README を読むと、これは「学習用軽音タイムテーブル」というアプリで、**わざと壊れている箇所がある**状態で配られ、Issue を解決しながら学ぶ、という作りになっています。なので「動かない箇所がある」のはバグではなく仕様です。

---

## 1. トップレベルの地図

```
README.md          ← 学習会の進め方。ここが入口
docs/              ← 環境構築、ワークショップの進め方
issues/            ← 課題7つの本文（01〜07のmdファイル）
scripts/setup/     ← bun run setup の中身。GitHub側の準備を自動化するやつ
app/               ← ★アプリ本体。ほぼ全部ここ
drizzle/           ← DBマイグレーション（SQLの履歴）
public/            ← favicon など
package.json 他    ← 依存・ビルド設定
```

`issues/01-env.md` 〜 `07-validation.md` が、README の表にある課題7つと対応しています。難易度は EASY → EXTREME の順です。

**使っている技術**（package.json より）：React Router v8（フレームワークモード）、Drizzle ORM + SQLite(libsql)、Tailwind CSS v4、shadcn/ui、valibot、Biome。

---

## 2. `app/` の中身 — ここが本体

`app/` は役割ごとにディレクトリが切られています。**下に行くほどDBに近い**、というイメージで並べます。

| ディレクトリ | 役割 |
|---|---|
| `routes/` | 画面とURLの実体。1ファイル＝1画面が基本 |
| `routes.ts` | URL と `routes/` のファイルの対応表 |
| `root.tsx` | アプリ全体の外枠（HTMLの`<html>`から書いてある） |
| `components/ui/` | shadcn/uiから入れた汎用部品（button, card, input…）。基本さわらない |
| `components/common/` | このアプリ独自の共通部品（DateInput, toast など） |
| `hooks/` | 独自Reactフック |
| `middlewares/` | 各ルートの**前**に走る共通処理（認証、DIなど） |
| `domain/` | このアプリ固有の「概念」の定義。バンド、ライブ、ユーザーなど |
| `repositories/` | DBへの読み書きをまとめた層 |
| `db/` | Drizzleのスキーマ定義とDB接続 |
| `lib/` | 汎用ユーティリティ（日付、ハッシュ、Result型など） |

---

## 3. リクエストが来たとき、どう流れるか

構成を「地図」ではなく「流れ」で見ると腹落ちしやすいので、こちらも。

```
URL
 → routes.ts で対応ファイルを決定
 → middlewares（認証チェック・repositoryをcontextに詰める）
 → routes/xxx.tsx の loader / action
 → repositories（DB操作）
 → db（Drizzle → SQLite）
```

`routes.ts` を見ると、この流れが入れ子で表現されているのが分かります。ざっくり4系統：

- `/` … トップページ
- `/auth/*` … login / logout / register
- `/app/*` … ログイン後の本体。`app-middleware.tsx` を通らないと入れない
- `/app/live/:liveId/*` … 特定のライブ配下。さらに `band/:bandId` が入れ子

`layout(...)` で囲まれているものは「その中の全ルートの親」です。だから `app-middleware.tsx` が `/app` 配下すべての門番になっています。

面白い設計として、`middlewares/repositories.ts` が **リポジトリ3つを生成して context に入れている**。各ルートは自分でDBを触らず、context から受け取る形です（依存性注入という考え方）。

---

## 4. `domain/` と `repositories/` の関係

ここがこのリポジトリで一番「意図を持って」作られている部分です。

- `db/schema.ts` … **DBのテーブル定義**。live, live_day, user, band, band_participation, band_availability, live_application の7テーブル
- `domain/entities/*` … 上のテーブルと概ね対応する、**アプリ側での型・ルール**
- `repositories/*` … DBの行 ⇄ ドメインの型 を橋渡しする

DBの都合とアプリの都合を分けておく、という構成です。たとえば `schema.ts` を見ると日付は `text` で `// yyyy/mm/dd` とコメントされていますが、アプリ内では `lib/plain-date.ts` のような型で扱う、という分業になっています。

---

ここまでが全体像です。ここで一つ、聞かせてください。**正確じゃなくて大丈夫です。単語だけでも「たぶん〜」でも構いません。**

> **React Router のフレームワークモード（loader / action を書くやつ）と Drizzle のような ORM、どちらか触ったことはありますか？**

これによって次の説明の粒度を変えたいだけなので、「両方はじめて」でも全く問題ありません。

あわせて、もし今すぐ深掘りしたい場所があれば教えてください。候補としてはこのあたりです。

- **A.** `routes.ts` の入れ子構造と middleware の走り方（このアプリで一番独特な部分）
- **B.** loader / action って結局なんなのか（Issue 6 に直結）
- **C.** `domain` / `repositories` / `db` の3層に分けている理由
- **D.** まずは Issue 01 から取りかかりたいので、その周辺だけ

「まだ決められない」でも大丈夫です。その場合はAから行くのがおすすめです。