認証まわりのファイルを一通り読みました。全体像 →流れ →なぜ、の順で話します。

## 登場するファイル（これで全部です）

| ファイル | 役割 |
|---|---|
| `app/sessions/sessions.ts` | Cookie の読み書き |
| `app/sessions/jwt.ts` | トークンの発行・検証 |
| `app/middlewares/user.ts` | 「ログインしてる？」の門番 |
| `app/routes/app/app-middleware.tsx` | 門番をどこに立てるかの設置場所 |
| `app/routes/auth/login.tsx` | ログイン処理本体 |
| `app/repositories/user.ts` | パスワード照合（DB） |

## 一番大事な構造：**入れ子が2段になっている**

ここが分かると全部つながります。

```
Cookie「__session」  ← react-router が署名する
   └ sessionToken: "eyJhbGc..."  ← これが JWT。jose が署名する
        └ { id: 3 }  ← 中身はユーザーIDだけ
```

つまり、**「署名付きCookie」の中に「署名付きトークン」が入っている**二重構造です。サーバー側にセッション table は無く、ユーザーが誰かという情報は全部このCookieだけが持っています。

## ログインの流れ

`login.tsx` の `action`（83行目〜）を上から追うと、そのまま流れになっています。

1. フォームから `mail` と `password` を取る
2. `userRepository.getByMail(mail)` でユーザーを引く → いなければ `UserNotFoundError`
3. `authenticateWithPassword(user.id, password)` → 中では `compareHashedPassword` で**ハッシュ同士を比較**（平文パスワードはDBに無い）
4. 合っていたら `signToken(user.id)` で JWT を作る（有効期限30日）
5. `session.set("sessionToken", token)` して `commitSession` → `Set-Cookie` ヘッダとしてブラウザに返す

## ログイン後、各ページで何が起きるか

`routes.ts` を見てください。18行目の `layout("./routes/app/app-middleware.tsx", [...])` が肝です。

`/app` 以下のルートは**全部この layout の子**になっています。そして `app-middleware.tsx` は中身がほぼ空で、やっているのは1行だけ：

```
export const middleware = [userMiddleware]
```

つまり、**ルーティングの入れ子構造をそのまま認可の境界として使っている**わけです。`/app/...` にアクセスすると、どのページであっても必ず先に `userMiddleware` が走る。逆に `/auth/login` はこの layout の外側にあるので、門番を通らずに入れます。

`userMiddleware`（`middlewares/user.ts`）がやることは、順に4つのチェックです：

1. Cookie に `sessionToken` があるか（22行目）
2. その JWT の署名と期限が正しいか（36行目 `verifyToken`）
3. 中の `id` でDBを引けるか（58行目）
4. そのユーザーが実在するか（74行目）

どれか1つでも失敗したら、全部同じ処理をします：`sessionToken` を消す → **flash** に「なぜ失敗したか」のトーストと `redirectAfterAuth`（今いたURL）を入れる → `/auth/login` へリダイレクト。

flash は「一度読んだら消えるセッション値」です。トーストメッセージや「元いたページ」のような、**1回きり使って捨てたい値**のための仕組みです。だから `login.tsx` の125行目で `redirectAfterAuth` を読み出して、ログイン成功後にそのページへ戻せる。

そして全部通過したら最後の1行、`context.set(userContext, user)`。ここで初めて User が context に入り、以降どの loader / component からも `context.get(userContext)` で取り出せるようになります。**「ここから先のコードでは、ユーザーは必ず存在する」という保証を作るのが門番の本当の仕事**です。

---

ここまでで一区切りです。「なぜCookieとJWTを二重にしているのか」という設計の話が残っていますが、先に一つ聞かせてください。

**正確じゃなくて大丈夫です。「たぶん〜」でも、途中で止まっても構いません。**言葉にすると自分でどこが曖昧か見つかるので、その材料として聞いています。

`app-middleware.tsx` の

```
export const middleware = [userMiddleware]
```

この行を消したとしたら、**アプリの挙動として何が起きると思いますか。** 「分からない」でも構いません。