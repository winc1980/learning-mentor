読み終わりました。認証まわりは **7つの役割** に分かれています。

**まずは場所だけ挙げます。中身の説明はまだしません。**

| 役割 | ファイル |
|---|---|
| Cookie の入れ物を作る・読み書きする | `app/sessions/sessions.ts` |
| トークンの発行と検証 | `app/sessions/jwt.ts` |
| パスワードのハッシュ化と照合 | `app/lib/hash.ts` |
| DB からユーザーを引く・パスワード認証 | `app/repositories/user.ts` |
| 入り口の画面と送信処理（ログイン / 登録 / ログアウト） | `app/routes/auth/login.tsx`, `register.tsx`, `logout.tsx` |
| 門番（未ログインなら弾いて `/auth/login` へ飛ばす） | `app/middlewares/user.ts` |
| 門番をどのURLに取り付けるか | `app/routes/app/app-middleware.tsx` + `app/routes.ts` |

別系統がもう1本あります（ログインとは別のトークンを使う招待URLの仕組み）：`app/domain/service/create-application-url.ts`, `app/routes/app/api/live-application.tsx`。これは後回しでいいと思います。

---

聞きたいことが2つあります。

**1.** この中で、**いま一番気になっているのはどれですか。** 「全部ぼんやり」でも大丈夫です。

**2.** そもそも今回、何がきっかけでここを見ようと思いましたか？ 「タスクで触ることになった」「ログイン周りで変な挙動があった」「なんとなく全体を把握したい」——どれかで、説明の入り口がかなり変わります。