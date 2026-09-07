認証まわり、全体像から見ていきましょう。まず**地図だけ**を渡します。細部はそのあと、あなたが気になったところに絞って掘ります。

## 登場人物は4つだけ

| 役割 | ファイル |
|---|---|
| ① 保管場所（Cookie） | `app/sessions/sessions.ts` |
| ② 身分証の発行と検証（JWT） | `app/sessions/jwt.ts` |
| ③ 身分証を配る（ログイン） | `app/routes/auth/login.tsx` の `action` |
| ④ 門番（毎リクエストのチェック） | `app/middlewares/user.ts` |

## 流れ

**ログインするとき**（`login.tsx:83`〜）

```
メール+パスワード送信
  → DBからユーザーを引く (userRepository.getByMail)
  → パスワード照合 (authenticateWithPassword)
  → signToken(user.id) で「私はユーザーID=Nです」という署名付き文字列を作る
  → session.set("sessionToken", token) → Set-Cookie でブラウザに渡す
  → redirect
```

**その後のリクエスト**（`user.ts:16`〜）

```
リクエストのCookie
  → sessionToken を取り出す（無ければ /auth/login へ）
  → verifyToken で署名と期限を検証（ダメなら /auth/login へ）
  → payload.id でDBからユーザーを取得（居なければ /auth/login へ）
  → context.set(userContext, user)  ← ここがゴール
```

**どこに門番が立っているか**（`app/routes.ts:18`）

`layout("./routes/app/app-middleware.tsx", [...])` で `/app` 配下を丸ごと包んでいます。つまり **`/app` 以下のページは、個別に認証コードを書かなくても全部守られる**。この「ルートの入れ子構造をそのまま権限の境界に使う」のが、この設計の一番の狙いです（同じ形が `live-middleware` / `band-middleware` にもあります）。

そして下流のページは `context.get(userContext)` と書くだけでログイン中のユーザーを受け取れる。**「ユーザーが居ることが保証済みの状態」を作って渡すのが middleware の仕事**です。

---

ここで一度止めます。**あなたがこの先どこを詳しく知りたいかで、話す内容が変わる**ので。

まず前提の確認を1つだけ。**Cookie とセッションを使った認証（サーバーがCookieに情報を入れて、次のリクエストでそれを読む）は、これまで触ったことがありますか？** 「聞いたことはある」「初めて」でも全然かまいません。ここが初めてなら、JWT より先にそっちを説明したほうが早いので。

そのうえで、上の地図で**一番モヤッとしたのはどこですか**。正確じゃなくて大丈夫です、単語だけでも「たぶん〜」でも構いません。候補を挙げておくと：

- **A**：Cookie に何が入っているのか（②の JWT と ①の Cookie の関係）
- **B**：middleware がいつ・どういう順番で動くのか
- **C**：`context` って何なのか、なぜこれで下流にユーザーを渡せるのか
- **D**：`flash`（`redirectAfterAuth` や `toastPayload`）が何をしているのか

「全部」でもいいですが、その場合は私が順番を決めて1つずつ行きます。