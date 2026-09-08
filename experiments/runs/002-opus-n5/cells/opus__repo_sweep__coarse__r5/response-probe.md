認証まわり、ファイルを一通り読みました。**全体像 → 流れ → なぜそうなっているか** の順でいきます。

## 大前提：2階建てになっている

ここが一番の理解ポイントです。このアプリの認証は**2つの仕組みが入れ子**になっています。

```
Cookie（__session）
  └─ 中身：sessionToken という文字列
       └─ その正体：JWT（中に userId が入っている）
```

- **外側 = Cookie セッション**（`app/sessions/sessions.ts`）
  React Router の `createCookieSessionStorage` を使う。ブラウザに Cookie として保存され、`SESSION_SECRET` で署名されている（＝ユーザーが書き換えたらバレる）。
- **内側 = JWT**（`app/sessions/jwt.ts`）
  JSON Web Token。「userId は 5 です」というデータに `JWT_SECRET` で署名し、有効期限（30日）を付けた文字列。

**なぜ2階建てなのか**は後で触れます。まずは「Cookie の中に JWT が入っている」とだけ押さえてください。

## 登場するファイル

| ファイル | 役割 |
|---|---|
| `app/lib/hash.ts` | パスワードの**ハッシュ化と照合**（bcrypt） |
| `app/sessions/jwt.ts` | JWT の**発行**（`signToken`）と**検証**（`verifyToken`） |
| `app/sessions/sessions.ts` | Cookie の**設定と読み書き** |
| `app/middlewares/user.ts` | **関門**。Cookie → JWT検証 → DB照合 → ユーザーを context に置く |
| `app/routes/app/app-middleware.tsx` | 上の関門を `/app` 配下に**適用する**だけの3行 |
| `app/routes/auth/login.tsx` | ログイン画面 + ログイン処理 |
| `app/routes/auth/register.tsx` | 登録 |
| `app/routes/auth/logout.tsx` | ログアウト |

## 流れ① ログイン（`login.tsx` の `action`）

`<Form method="POST">` を送信すると、同じファイルの `action` がサーバー側で走ります。

```
1. フォームから mail / password を取り出す
2. userRepository.getByMail(mail)         → いなければエラーを画面に返す
3. authenticateWithPassword(id, password) → bcrypt でハッシュと照合
4. signToken(user.id)                     → JWT を作る
5. session.set("sessionToken", token)     → Cookie の中身に詰める
6. session.flash("toastPayload", ...)     → 「ログインしました」を仕込む
7. redirect(redirectAfterAuth ?? "/app", { "Set-Cookie": ... })
```

ここで **`flash`** という言葉が出ました。**一度読み出したら消えるセッションの値**です。トースト通知や「ログイン後に戻る先」のような、1回きりで使い捨てたい情報に使います。

パスワードは DB に**平文で入っていません**（`user.passwordHash`）。bcrypt は「ハッシュから元に戻す」ことができないので、照合は必ず `compare(入力, ハッシュ)` の形になります。

## 流れ② ログイン必須ページを開く（ここが中心）

`/app/...` を開いたとき、上から順に関門を通ります。

```
root-layout.tsx
  middleware: [repositoryMiddleware]   ← context に repository を用意
        ↓
app-middleware.tsx
  middleware: [userMiddleware]         ← ★認証の関門
        ↓
app-layout.tsx → 各ページ
```

`userMiddleware`（`app/middlewares/user.ts`）がやっていることを分解すると：

```
Cookie からセッションを読む
  ├ sessionToken が無い
  │    → 「ログインしてください」を flash
  │    → 今の URL を redirectAfterAuth に flash
  │    → /auth/login へリダイレクト
  │
  └ ある → verifyToken(token)
       ├ 失敗 → 理由を区別してメッセージを変える
       │         ・期限切れ  → ExpiredSessionTokenError
       │         ・改ざん    → InvalidSessionTokenError
       │        → 同じくログイン画面へ
       │
       └ 成功 → payload.id で DB からユーザーを取得
            ├ DBエラー / ユーザーが存在しない → ログイン画面へ
            └ OK → context.set(userContext, user)
```

最後の `context.set(userContext, user)` が肝です。**これ以降のルートは `context.get(userContext)` を呼ぶだけでログイン中のユーザーが取れる**。各ページで Cookie を解いたり JWT を検証したりする必要がありません。

そして `redirectAfterAuth` に元の URL を入れておくので、ログイン後に `login.tsx` の `action` がそれを読んで**元いたページへ戻す**。往復がつながっています。

## 流れ③ 通知の表示

`userMiddleware` が `flash` した「ログインしてください」は、`root-layout.tsx` の `loader` が取り出して、画面にトーストとして出します。**認証の失敗理由がユーザーに伝わる経路**がここです。

---

ここまでで、一度止めます。**用語（Cookie / セッション / JWT / middleware）のうち、初めて聞くものはありましたか？** あれば、そこから丁寧にやり直します。

---

## なぜこの設計なのか

分かる範囲で「なぜ」を3つ。

**1. なぜ関門を `app-middleware.tsx` に集約するのか**
各ページの `loader` に「ログイン確認」を書く方法もあります。が、20ページあれば20回書き、**1つ書き忘れたらそこが穴**になります。ルートの入れ子の入口に1つ置けば、その下は全部守られる。追加したページが自動で守られるのが利点です。

**2. なぜ JWT の中身が `{ id: number }` だけなのか**
名前やメールも入れれば DB アクセスを1回減らせます。でもそうすると、**ユーザーが退会・改名しても、30日間 Cookie の中の古い情報が生き続ける**。だから ID だけ入れて、実体は毎回 DB から引く。`userMiddleware` が JWT 検証の後に必ず `getById` しているのはこのためです。

**3. なぜ Cookie の中に JWT なのか（＝2階建ての理由）**
実はここは**議論の余地があるところ**です。Cookie セッション自体が `SESSION_SECRET` で署名済みなので、改ざん検知だけなら JWT は要りません。JWT を重ねて得ているのは主に**有効期限（30日）**と、トークンを他所へ持ち出せる形式にしてあること。「冗長だ」という見方も、「関心が分かれていて良い」という見方も成り立ちます。

## 気づいたこと（解決はしません）

`app/routes/auth/logout.tsx` の中身は、いま **`<div>Logout</div>` を返すだけ**です。`action` がありません。この教材は「壊れている箇所を直す」形式なので、意図的なものかもしれません。

---

最後に一つだけ。**当てるのが目的ではないので、「たぶん」で構いません。**

> `.env` の **`JWT_SECRET` の値だけを別の文字列に変えて**サーバーを再起動したら、すでにログイン済みだったユーザーは次にページを開いたときどうなると思いますか？
>
> A. 何も起きない（そのまま使える）
> B. ログイン画面に飛ばされる
> C. サーバーがエラーで落ちる

選ぶだけでOKです。「分からない」でも構いません。ここの答えで、次に `verifyToken` の中を詳しく見るか、`context` の仕組みに進むかを決めます。