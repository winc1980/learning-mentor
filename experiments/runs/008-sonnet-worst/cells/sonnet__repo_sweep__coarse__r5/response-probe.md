このアプリの認証は、Cookieセッション + JWT という組み合わせで作られています。関連ファイルを一通り見ました。

**まずは場所だけ挙げます（中身の説明はまだしません）。**

| 役割 | ファイル |
|---|---|
| Cookie の入れ物を作る（セッションストレージ） | `app/sessions/sessions.ts` |
| ログイン状態を表すトークンの発行・検証（JWT） | `app/sessions/jwt.ts` |
| リクエストのたびにログイン確認をして、ユーザー情報をセットする関所 | `app/middlewares/user.ts` |
| ログイン画面・処理 | `app/routes/auth/login.tsx` |
| 新規登録画面・処理 | `app/routes/auth/register.tsx` |
| ユーザーの DB アクセス | `app/repositories/user.ts` |
| パスワードのハッシュ化 | `app/lib/hash.ts` |
| ログイン中のUI（ログアウトなど） | `app/components/common/AccountDropdownMenu.tsx` |

一点だけ先に聞かせてください。これは **これから何かを直そう/実装しようとしていて読んでいる** のか、それとも **まずコード全体をざっと理解したい段階** か、どちらに近いですか。

あと、正確じゃなくて大丈夫なので聞きたいのですが、**JWT や Cookie セッションは、これまで触ったことありますか？** 「聞いたことはある」くらいでも構いません。