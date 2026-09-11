一通り読みました。認証まわりは、大きく6つの役割に分かれています。
**まずは場所だけ挙げます(中身の説明はまだしません)。**

| 役割 | ファイル |
|---|---|
| ログイン/登録画面とその処理 | `app/routes/auth/login.tsx`, `register.tsx`, `logout.tsx` |
| Cookie(ブラウザに保存する小さなデータ)の入れ物を作る | `app/sessions/sessions.ts` |
| トークン(ログイン状態を証明する文字列)の発行・検証 | `app/sessions/jwt.ts` |
| ログイン必須ページを守るチェック | `app/middlewares/user.ts`, `app/routes/app/app-middleware.tsx` |
| ユーザー情報の読み書き(DBとのやり取り) | `app/repositories/user.ts` |
| パスワードのハッシュ化(平文で保存しないための変換) | `app/lib/hash.ts` |

正確じゃなくて大丈夫です。単語だけでも、「たぶん〜」でも構いません。

この中で、**いま一番気になっているのはどれですか?** それとも「全部ぼんやり」という感じですか?