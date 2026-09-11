認証まわり、ざっと関係しそうなファイルを見てきました。登場人物は大きく6つに分かれています。

**まずは場所だけ挙げます（中身の説明はまだしません）。**

| 役割 | ファイル |
|---|---|
| ログイン画面とログイン処理 | `app/routes/auth/login.tsx` |
| 新規登録画面と登録処理 | `app/routes/auth/register.tsx` |
| Cookie セッションの入れ物 | `app/sessions/sessions.ts` |
| トークンの発行・検証 | `app/sessions/jwt.ts` |
| ログイン済みかどうかのチェック | `app/middlewares/user.ts` |
| ユーザー情報のDB操作・パスワード照合 | `app/repositories/user.ts` |

この中で、**いま一番気になっているのはどれですか？**「全部ぼんやり」でも大丈夫です。

ちなみに一つだけ先に聞いておきたいのですが、Cookie（クッキー）や JWT（JSON Web Token、ログイン状態を表す署名付きの文字列）という言葉は聞いたことありますか？