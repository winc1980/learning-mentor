一通り見ました。認証まわりは大きく5つの役割に分かれているようです。

**まずは場所だけ挙げます（中身の説明はまだしません）。**

| 役割 | ファイル |
|---|---|
| Cookie の入れ物を作る・読み書きする | `app/sessions/sessions.ts` |
| トークン（JWT）の発行と検証 | `app/sessions/jwt.ts` |
| リクエストが来るたびログイン状態をチェックする | `app/middlewares/user.ts` |
| ログイン・登録画面の入り口 | `app/routes/auth/login.tsx`, `app/routes/auth/register.tsx` |
| ユーザー情報を DB から取ってくる | `app/repositories/user.ts` |

この中で、**いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。

（さっきの `plain-date.ts` の話、いったん置いておきますね。忘れてないので、あとで戻りましょう）