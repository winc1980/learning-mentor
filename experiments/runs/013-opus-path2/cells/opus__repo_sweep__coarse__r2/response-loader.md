一通り読みました。まず**場所だけ**挙げます（中身がどう動くかの説明はまだしません）。地図を渡すつもりで書いています。

## これは何のプロジェクトか

`package.json` の名前は `musiclive-timetable`。軽音サークルのライブのタイムテーブルを作るWebアプリです。README によると、**わざと壊れている箇所がある学習用リポジトリ**で、Issue 1〜7 を解いていく形式ですね。

技術構成は、React Router v8（フルスタックフレームワーク版）+ Drizzle ORM + libSQL + Tailwind + shadcn/ui、ランタイムは Bun。

## 大きく分けると6層

| 層 | 場所 | ファイル数の目安 |
|---|---|---|
| ルーティング定義 | `app/routes.ts`, `app/root.tsx` | 2 |
| 画面（ページ） | `app/routes/**` | 約22 |
| ミドルウェア | `app/middlewares/**` と `app/routes/**/*-middleware.tsx` | 4 + 3 |
| ドメイン（型・ビジネスルール） | `app/domain/**` | 9 |
| データ層 | `app/db/**`, `app/repositories/**` | 5 |
| 認証まわり | `app/sessions/**`, `app/lib/hash.ts` | 3 |
| 部品・ユーティリティ | `app/components/**`, `app/hooks/**`, `app/lib/**` | 約30 |

## 画面の構造（`app/routes/`）

URLの階層がそのままフォルダ階層になっています。

```
routes/
├─ root-layout.tsx / home.tsx / not-found.tsx   ← トップ周り
├─ auth/          login, logout, register        ← ログイン系
└─ app/           ログイン後の領域
   ├─ app-layout.tsx / app-middleware.tsx
   ├─ home.tsx
   ├─ api/        hello-react-router, live-application
   └─ live/       ライブ関連
      ├─ live-layout.tsx / live-middleware.tsx
      ├─ home, create, timetable, application
      └─ band/    バンド関連
         ├─ band-layout.tsx / band-middleware.tsx
         └─ home, create, availability, availability-day-card
```

`*-layout.tsx` と `*-middleware.tsx` が各階層に1組ずつ置かれているのが、この構成の特徴です。

## Issue との対応

課題がどのファイルを触るものか、ざっくり対応させるとこうです。

| Issue | 主な舞台 |
|---|---|
| 1 環境変数 | ルート直下（`.env` 系） |
| 2 トップの導線 | `app/routes/home.tsx` |
| 3 useEffect と通知 | `app/components/common/toast.tsx` 周辺 |
| 4 Biome | ルート直下の設定ファイル |
| 5 コンポーネント肥大化 | `app/routes/app/live/application.tsx` |
| 6 useEffect+fetch → loader | 同上 + `app/routes/app/api/` |
| 7 メアドのバリデーション | `app/routes/auth/register.tsx` + valibot |

## その他

- `docs/` — 環境構築、ワークショップの進め方
- `issues/` — 課題の元ファイル（`bun run setup` でGitHubに登録される）
- `.claude/agents/` — このセッションの設定ファイル

---

ひとつ確認です。README に「生成AIにコードを書かせない／エラーを解決させない」と明記されていますね。このセッションもまさにその方針で、**コードは書かず、解説と壁打ちだけ**をします。安心して聞いてください。

そのうえで聞きたいのですが、**この中でいま一番気になっているのはどこですか。**「全部ぼんやり」でも大丈夫ですし、「まず Issue 1 から始めたいので、そのあたり」でも構いません。

もし選びにくければ、こちらから1つだけ質問させてください（答えやすいところからで大丈夫です）：

**React Router は使ったことがありますか。** 「ある」「名前は知ってる」「初めて」のどれかで十分です。ここで説明の粒度がかなり変わるので。