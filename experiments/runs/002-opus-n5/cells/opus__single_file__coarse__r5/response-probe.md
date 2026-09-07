認証まわりのファイルを一通り読みました。全体像から順に話します。細かいところは後回しにするので、まず「どこで何が起きるか」だけ掴んでください。

## 1. まず結論：このアプリは「Cookie の中に JWT を入れている」二階建て

ここが一番の特徴で、最初にここを押さえると残りが繋がります。

- **一階（外側）＝ Cookie セッション** — `app/sessions/sessions.ts`。ブラウザに `__session` という名前の Cookie を配る仕組み
- **二階（中身）＝ JWT** — `app/sessions/jwt.ts`。「このユーザーは id=42 だ」という事実に、サーバーの秘密鍵で署名した文字列

Cookie の中に `sessionToken` という名前で JWT が入っている、という入れ子構造です。**JWT**（JSON Web Token）は、中身のデータ＋署名がセットになった文字列で、サーバーが「これは自分が発行したもので、改ざんされていない」と検証できるのが要点です。

## 2. ログインするとき（`app/routes/auth/login.tsx` の `action`, 83行目〜）

上から順に、こういう流れです。

```
フォーム送信
 → メールでユーザーを探す（userRepository.getByMail）
 → パスワード照合（authenticateWithPassword → 中で bcrypt）
 → signToken(user.id) で JWT を作る
 → session.set("sessionToken", token) で Cookie に詰める
 → Set-Cookie ヘッダ付きで /app へリダイレクト
```

パスワードの照合は `app/lib/hash.ts` の `compareHashedPassword` に行き着きます。**平文のパスワードはDBに保存されていません。** bcrypt でハッシュ化した文字列だけを保存し、ログイン時は「入力を同じ手順でハッシュ化して一致するか」を見ています。

## 3. ログイン後、ページを守っているところ（ここが本題）

`app/routes.ts` の 18行目を見てください。

```
prefix("app", [ layout("./routes/app/app-middleware.tsx", [ ...中身全部... ]) ])
```

`/app` 以下のページが**全部**このファイルで包まれています。そして `app-middleware.tsx` の中身は実質2行で、`userMiddleware` を指定しているだけです。

つまり **`/app` 以下のどのURLを開いても、ページ本体の処理より先に `app/middlewares/user.ts` が必ず走る**。これが「認証の門番」です。ページごとに `if (!ログイン) return redirect(...)` を書かなくて済むのは、この構造のおかげです。

門番（`userMiddleware`）がやっているのは4つのチェックで、**どれかを落ちたら全部 `/auth/login` にリダイレクト**します。

| # | チェック | 落ちる例 |
|---|---|---|
| 1 | Cookie に `sessionToken` があるか（22行目） | そもそも未ログイン |
| 2 | JWT が有効か（36行目 `verifyToken`） | 期限切れ（30日）／改ざん |
| 3 | DBからユーザーを取れたか（58行目） | DB障害 |
| 4 | そのユーザーが存在するか（74行目） | 退会済みなど |

全部通ったら、最後の86行目で `context.set(userContext, user)` をします。これで**以降のページやローダーは、`userContext` からログイン中のユーザーを取り出せる**。DBを引き直す必要がありません。

## 4. リダイレクト時に持ち回っている2つの値

`userMiddleware` がリダイレクトする直前、毎回2つ書き込んでいます（例：25〜29行目）。

- `redirectAfterAuth` — 元々開こうとしていたURL。ログイン成功時に `login.tsx` の125行目がこれを読んで、そこへ戻します
- `toastPayload` — 「ログインしてください」などの通知メッセージ

どちらも `flash` で書かれています。flash は **一度読まれたら消える**書き方で、「同じトーストが次のページでも出続ける」のを防ぐためのものです。

---

ここまでが全体像です。**深掘りは2つくらいまでにしておきたい**ので、続きを選んでもらえますか。

そのために、答えやすい問いを2つ出します。「たぶん」で構いませんし、「分からない」でも大丈夫です。

**(a)** 一番引っかかったのは、次のどれに近いですか。
1. なぜ Cookie と JWT を**両方**使うのか（片方でいいのでは？）
2. middleware がどうやって「全ページの前」に割り込めるのか
3. `Result` 型（`result.success` で分岐しているやつ）の書き方
4. リポジトリ層（`userRepository`）が何をしている層なのか

**(b)** 予測してみてほしいのですが、`routes.ts` の18行目の `layout("./routes/app/app-middleware.tsx", ...)` の行を消して、中身を `prefix("app", [...])` の直下に置いたら、**アプリの挙動は何が変わると思いますか？**

（余談として一点だけ。`app/routes/auth/logout.tsx` は現状 `<div>Logout</div>` を返すだけで、Cookie を消す処理がまだ入っていません。今日の話とは別件ですが、頭の片隅に置いておくといいと思います）