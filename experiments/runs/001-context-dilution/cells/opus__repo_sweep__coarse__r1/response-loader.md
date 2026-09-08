リポジトリをひととおり見ました。まず**全体像**から、そのあと中身に降りていきます。

---

## 1. これは何か

`package.json` の名前は `musiclive-timetable`。**軽音サークルのライブのタイムテーブルを作るWebアプリ**です。

ただし、単なるアプリではなくて **学習用の教材リポジトリ** です。README にこう書いてあります。

> 所々、壊れて動かない箇所がある
> Issueを解決しながら技術の実装を学ぶ

つまり **意図的に壊してある／未実装にしてある箇所がある** 前提で読んでください。「なんでこんな書き方なんだ？」と思う箇所が、そのまま課題になっている可能性があります。

---

## 2. トップレベルの地図

```
README.md          ← 学習会の進め方。最初に読むのはここ
docs/              ← 環境構築、ワークショップの進め方
issues/            ← 課題7本の本文（01〜07）
app/               ← ★アプリ本体。ほぼ全部ここ
drizzle/           ← DBのマイグレーション履歴（自動生成。手で書くものではない）
*.config.ts        ← 設定ファイル群（vite / react-router / drizzle）
```

**最初に見るべきは `issues/` と `app/`** です。`drizzle/` の中の SQL や snapshot.json はツールが吐いたものなので、今の段階では読まなくて大丈夫です。

---

## 3. 使っている道具

| 何 | 役割 |
|---|---|
| **React Router v8** (framework mode) | ルーティング＋サーバー側の処理。ここが土台 |
| **Drizzle ORM** + libsql (SQLite) | DBアクセス |
| **shadcn/ui** + Tailwind CSS v4 | 見た目 |
| **valibot** | バリデーション |
| **jose / bcrypt** | 認証（JWT・パスワードハッシュ） |
| **Biome** | フォーマッター・リンター（※Issue 4 の題材） |

ここで一つポイントがあります。**React Router v8 は「ルーターライブラリ」ではなく、フレームワークとして使われています。** サーバー側でデータを取ってきて（loader）、フォーム送信を受け取る（action）役割まで担っています。Next.js のポジションに近いです。

---

## 4. `app/` の中の層構造 ← ここが本題

`app/` は **役割ごとにきれいに層で分かれています**。上から下に依存していく形です。

```
routes/         ← 画面とURL。ユーザーからの入り口
  ↓
middlewares/    ← ルートに入る前の共通処理（認証・権限チェック・DI）
  ↓
repositories/   ← DBへの読み書きを実際にやる場所
  ↓
db/             ← 接続(index.ts)とテーブル定義(schema.ts)
```

これと**横に**並ぶ形で、こういうものがあります。

```
domain/entities/   ← 「Band とは id と name と leaderId を持つ」という型定義だけ
domain/service/    ← DBに依存しないビジネスロジック
components/ui/     ← shadcn が生成したUI部品（基本さわらない）
components/common/ ← このアプリ独自のUI部品
hooks/             ← Reactのカスタムフック
lib/               ← 汎用ユーティリティ（日付、ハッシュ、Result型など）
```

`domain/entities/band.ts` は実際これだけです。

```ts
export type Band = {
	id: number
	name: string
	leaderId: number
}
```

**型定義しか置いていない。** これは意図的で、「アプリの中心にある概念」をDBやUIから切り離して置いておくための場所です。

---

## 5. URLとファイルの対応

このプロジェクトは**ファイル名からURLを推測できません**。`app/routes.ts` に手書きで全部書いてあります。ここが URL の唯一の正解です。

構造はこうなっています。

```
/                          トップ
/auth/login, logout, register    認証
/app/                      ログイン後のホーム
/app/live/:liveId/         あるライブの中
       ├ application       出演申込
       ├ timetable         タイムテーブル
       └ band/:bandId/     あるバンドの中
                └ availability   出演可能日時
```

注目してほしいのが、階層ごとに `〜-middleware.tsx` と `〜-layout.tsx` がペアで置かれていることです。

- **middleware** … 「そもそもここに入っていいのか」を判定する（ログイン済みか、このライブの関係者か）
- **layout** … 共通の見た目の枠

`/app/live/:liveId/band/:bandId/availability` を開くと、外側から順に `app-middleware` → `live-middleware` → `band-middleware` → ようやく `availability.tsx` が動きます。**内側のページは「認証済みで、ライブもバンドも取得済み」の状態から書き始められる**わけです。

DIもここでやっています。`middlewares/repositories.ts` が Repository の実体を作って context に入れ、各ページはそれを受け取って使います。

---

## 6. 課題7本（これがこのリポジトリの目的）

| # | 難易度 | 内容 | 触る場所 |
|---|---|---|---|
| 1 | EASY | 環境変数 | `.env.example` |
| 2 | EASY | トップから各ページへの導線がない | `routes/home.tsx` |
| 3 | NORMAL | 通知が `useEffect` で囲われていない | 通知まわり |
| 4 | NORMAL | Biome が導入されていない | 設定ファイル |
| 5 | HARD | コンポーネントが肥大化 | `routes/app/live/application.tsx` |
| 6 | HARD | データ取得が `useEffect`+`fetch` のまま | 同上 + `api/hello-react-router.ts` |
| 7 | EXTREME | 早稲田メアドのバリデーションがない | `routes/auth/register.tsx` |

Issue 6 が構造的には一番おもしろいところです。**さっき説明した「サーバー側の loader でデータを取る」という設計から外れている箇所を、正しい形に戻す**という課題になっています。

---

ここまでが地図です。ここから先は深さの調整をしたいので、2つだけ確認させてください。

1. **React Router の loader / action は使ったことがありますか？**（「名前は聞いたことある」「初めて見た」でも大丈夫です）
2. いま一番気になっているのは、**どのあたり**ですか。認証の流れ／DBまわり／画面の作り／それとも特定のIssue？

答えやすい方だけでも構いません。そこを掘っていきましょう。