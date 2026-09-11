一通り見てみました。認証まわりは、だいたい6箇所に分かれています。

**まずは場所だけ挙げます（中身の説明はまだしません）。**

| 役割 | ファイル |
|---|---|
| ログイン・登録・ログアウトの入口（画面とフォーム） | `app/routes/auth/login.tsx` `register.tsx` `logout.tsx` |
| Cookie セッションの入れ物を作る | `app/sessions/sessions.ts` |
| トークンの発行・検証 | `app/sessions/jwt.ts` |
| リクエストごとにログイン状態を確認する関所 | `app/middlewares/user.ts` |
| ユーザーの検索・パスワード確認・作成（DB とのやり取り） | `app/repositories/user.ts` |
| パスワードのハッシュ化 | `app/lib/hash.ts` |

この中で、**いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。