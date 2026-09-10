認証まわりに関わっていそうな場所は、ざっと見た感じこの6つです。**まだ中身の説明はしません**、まず場所だけ。

| 役割（たぶん） | ファイル |
|---|---|
| ログイン画面・処理 | `app/routes/auth/login.tsx` |
| ログアウト処理 | `app/routes/auth/logout.tsx` |
| 新規登録処理 | `app/routes/auth/register.tsx` |
| セッションの仕組み | `app/sessions/sessions.ts` |
| リクエストごとにユーザーを確認する処理 | `app/middlewares/user.ts` |
| ユーザー情報の型・DBアクセス | `app/domain/entities/user.ts`, `app/repositories/user.ts` |
| パスワードのハッシュ化 | `app/lib/hash.ts` |

その前に一つ確認させてください。

**「分からない」というのは、何かをしようとして詰まった結果ですか？ それとも、まだ何も触っていなくて、コードを読んでもピンと来ない、という状態ですか？**

- 前者なら、何をしようとして何が起きたか教えてください
- 後者なら、上の表の中で**一番気になる場所はどれですか**（「全部ぼんやり」でも大丈夫です）