認証まわり、いいところを選びました。このアプリで一番「層」が多い部分です。

まず全体像だけ話して、細部には入りません。長くなりすぎると3つ目の概念で必ず脱落するので。

---

## 1. 登場人物は5ファイル

```
app/sessions/sessions.ts    ← Cookieの読み書き
app/sessions/jwt.ts         ← トークンの発行と検証
app/lib/hash.ts             ← パスワードのハッシュ化（bcrypt）
app/middlewares/user.ts     ← 門番。ログイン済みかを毎回チェック
app/routes/auth/*.tsx       ← login / register / logout の画面と処理
```

---

## 2. 核になっている考え方：**Cookieの中にJWTが入っている**

ここが一番の「え、なんで？」ポイントだと思うので、先にこれだけ。

このアプリのCookieは、こういう入れ子になっています。

```
ブラウザのCookie「__session」
   └─ sessionToken という値
        └─ その中身が JWT（{ id: ユーザーID } が署名付きで入っている）
```

つまり **二段構え** です。

- **外側（Cookie）** … `sessions.ts` の `createCookieSessionStorage` が担当。React Router の機能で、`SESSION_SECRET` で署名されている
- **内側（JWT）** … `jwt.ts` が担当。`JWT_SECRET` で署名され、**30日**で期限切れ

`.env.example` に秘密鍵が2種類あるのは、これが理由です。

---

## 3. 2つの流れ

### ログインするとき（`routes/auth/login.tsx` の `action`）

```
フォーム送信
 → メールでユーザーを探す
 → パスワード照合（bcrypt。DBには平文でなくハッシュが入っている）
 → signToken(user.id) で JWT を作る
 → session.set("sessionToken", token)
 → Set-Cookie を付けてリダイレクト
```

### ログイン後、`/app` 配下にアクセスするとき（`middlewares/user.ts`）

```
Cookieを取り出す
 → sessionToken が無い          → /auth/login へ飛ばす
 → verifyToken で検証、失敗     → /auth/login へ飛ばす
 → payload.id でDBからユーザー取得
 → 取れなかった / いなかった     → /auth/login へ飛ばす
 → context.set(userContext, user)   ★ここまで来て初めて通す
```

`user.ts` が長くて読みづらいのは、**失敗パターンごとに違うメッセージを出しているだけ**で、やっていることは上の6行です。ここに気づくと一気に読みやすくなります。

そして `routes.ts` で `app-middleware.tsx` が `/app` 配下全部を包んでいるので、**この門番を通らずに `/app` の画面には入れない**構造になっています。各画面が個別に「ログインしてる？」と書く必要がない。

---

## 4. なぜこうなっているのか（重要な「なぜ」を3つだけ）

**なぜCookieだけでなくJWTも使うのか？**
Cookieセッション単体でもログイン状態は持てます。ただこの構成だと、有効期限・改ざん検知を `jwt.ts` 側に閉じ込められる。トレードオフとしては、単純に層が1つ増えて読みにくい。「必ずこうすべき」ではなく、この実装が選んだ設計です。

**なぜJWT検証に成功した後、わざわざDBを引くのか？**
JWTの中には `id` しか入っていません。名前もメールも入っていない。それに、**トークン発行後にユーザーが削除された可能性**がある。だから毎回DBで実在確認しています。`user === null` の分岐がそれです。

**なぜCookieに `httpOnly: true` が付いているのか？**
JavaScriptからCookieを読めなくするためです。これが無いと、XSSでトークンを盗まれます。

---

ここまでで、**まだ触れていないこと**が結構あります。`register.tsx`、`logout.tsx`、`redirectAfterAuth`（ログイン後に元のページへ戻す仕掛け）、`flash` と `toastPayload` の関係、`Result` 型。これらは深掘りしたいものから順に扱いましょう。

---

その前に一つだけ。**正確じゃなくて大丈夫です。「たぶん」でも、単語だけでも、途中で止まっても構いません。** 言葉にすると自分でどこが曖昧か見つかるので、その材料として聞いています。

> **ブラウザの開発者ツールで、`__session` Cookie の値を適当な文字列に書き換えてから `/app` を開いたら、何が起きると思いますか？**

「分からない」でも大丈夫です。その場合はそこから説明します。