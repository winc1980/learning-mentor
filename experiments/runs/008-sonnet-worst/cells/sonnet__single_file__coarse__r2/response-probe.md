一通り見てきました。認証の登場人物は6つくらいに分かれています。**まずは場所だけ挙げます（中身の説明はまだしません）。**

| 役割 | ファイル |
|---|---|
| Cookie の入れ物（セッション）を作る | `app/sessions/sessions.ts` |
| トークン（JWT）の発行と検証 | `app/sessions/jwt.ts` |
| ログイン画面と、ログイン時の処理 | `app/routes/auth/login.tsx` |
| 新規登録画面と処理 | `app/routes/auth/register.tsx` |
| リクエストのたびに「ログインしてるか」をチェックする関所 | `app/middlewares/user.ts` |
| ユーザー情報をDBから取ってくる係 | `app/repositories/user.ts` |

この中で、**いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。

ついでに一つだけ聞かせてください。JWT（JSON Web Token）や、Cookie にセッションを入れる仕組み自体は、これまでに触ったことありますか？