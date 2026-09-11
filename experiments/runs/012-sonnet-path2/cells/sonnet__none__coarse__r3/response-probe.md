一通り読みました。認証まわりは大きく5つの役割に分かれています。

**まずは場所だけ挙げます(中身の説明はまだしません)。**

| 役割 | ファイル |
|---|---|
| Cookie(ブラウザに保存する小さなデータ)の入れ物を作る | `app/sessions/sessions.ts` |
| ログイン状態を表すトークンの発行・検証 | `app/sessions/jwt.ts` |
| ログイン/新規登録/ログアウトの画面と処理 | `app/routes/auth/login.tsx`, `register.tsx`, `logout.tsx` |
| ユーザー情報の読み書き(DBとのやり取り) | `app/repositories/user.ts` |
| 「ログイン必須ページ」の入り口で全部チェックする関所 | `app/middlewares/user.ts`(と、それをルートに差し込む `app/routes/app/app-middleware.tsx`) |

あと、`app/routes.ts` を見ると、`/app` 以下が全部この関所を通る構造になっていて、`/auth` 以下(ログイン画面など)は通らない、という区分けも分かります。

この中で、**いま一番気になっているのはどれですか?** 「全部ぼんやり」でも大丈夫です。