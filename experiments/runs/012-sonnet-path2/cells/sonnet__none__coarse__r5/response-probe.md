リポジトリを一通り読みました。認証まわりは、大きく6つの役割に分かれています。**まずは場所だけ挙げます(中身の説明はまだしません)。**

| 役割 | ファイル |
|---|---|
| Cookieセッションの入れ物を作る | `app/sessions/sessions.ts` |
| セッション用トークン(JWT)の発行・検証 | `app/sessions/jwt.ts` |
| パスワードのハッシュ化・照合 | `app/lib/hash.ts` |
| ユーザーのDB操作(検索・作成・認証) | `app/repositories/user.ts` |
| ログイン/登録の画面と処理 | `app/routes/auth/login.tsx`, `register.tsx` |
| ログイン状態のチェック(認証ガード) | `app/middlewares/user.ts`, `app/routes/app/app-middleware.tsx` |

(ちなみに `logout.tsx` もありますが、中身がほぼ空でした。これは後で触れる機会があるかもしれません)

この中で、**いま一番気になっている/知りたいのはどれですか?**「全部ぼんやり」でも大丈夫です。

あわせて一つだけ聞かせてください。JWT(JSON Web Token、ログイン状態を表す改ざん検知付きの文字列トークン)や、Cookieセッションは、これまで触ったことありますか?聞いたことがある程度でも、初めてでも構いません。