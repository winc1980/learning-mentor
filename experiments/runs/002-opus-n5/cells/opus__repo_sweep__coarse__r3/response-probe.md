認証まわり、読みました。登場人物が7ファイルに散っているので「分からない」となるのは自然です。**全体の流れ → 各ファイルの役割 → なぜそうなっているか** の順に説明します。

## 全体像：3つの箱に分かれている

認証の話は、実は独立した3つの仕事に分かれています。ここを混ぜて考えると分からなくなります。

| 仕事 | どこ |
|---|---|
| ① パスワードが合っているか確かめる | `lib/hash.ts` + `repositories/user.ts` |
| ② 「ログイン済み」の印を発行する／読む | `sessions/jwt.ts` + `sessions/sessions.ts` |
| ③ 保護したいページで、その印を毎回チェックする | `middlewares/user.ts` |

①はログインの瞬間だけ。②は印そのもの。③は**その後のリクエスト全部**で走ります。

## 流れ1：ログインするとき

`routes/auth/login.tsx` の下半分、`action` 関数がすべてです（上半分はただのフォーム）。

```
フォームPOST
  → userRepository.getByMail(mail)        メールでユーザーを探す
  → authenticateWithPassword(id, pass)    bcryptでハッシュを照合
  → signToken(user.id)                    印（JWT）を作る
  → session.set("sessionToken", token)    印をCookieに入れる
  → redirect(戻り先 ?? "/app")             Set-Cookie付きで返す
```

ポイントを2つ。

**パスワードは DB に平文で入っていません。** `db/schema.ts` の `userTable` にあるのは `passwordHash` です。`lib/hash.ts` の bcrypt が、登録時に一方向変換して保存し、ログイン時は `compare` で照合します。ハッシュからは元のパスワードを復元できないので、DB が漏れても直ちにパスワードが漏れるわけではない、という設計です。

**発行される印には、ユーザーIDしか入っていません。** `sessions/jwt.ts` を見ると `{ id: number }` だけです。これは後で理由を聞きます。

## 流れ2：ログイン後、保護されたページを開くとき

ここが「どう組まれているか」の核心です。`routes.ts` の入れ子と対応しています。

```
/app/** へのリクエスト
  ↓
root-layout.tsx      → repositoryMiddleware：リポジトリを context に置く
  ↓
app-middleware.tsx   → userMiddleware：ここで認証チェック
  ↓
app-layout.tsx 以下の各ページ → context.get(userContext) でユーザーが取れる
```

`routes/app/app-middleware.tsx` は5行しかない、`userMiddleware` を差し込むためだけのファイルです。**`/app` 配下は全部この下にぶら下がっているので、各ページに認証チェックを書く必要がない。** 書き忘れによる保護漏れが起きない、というのがこの構造の狙いです。

`middlewares/user.ts` の中身は、4段階の関門です。上から順に：

1. Cookie に `sessionToken` があるか → なければ弾く
2. `verifyToken` を通るか（署名が正しいか・期限内か）→ ダメなら弾く
3. その ID のユーザーが DB に実在するか → いなければ弾く
4. 全部通ったら `context.set(userContext, user)`

弾くときは毎回同じことをしています。`session.flash("redirectAfterAuth", request.url)` で**元々行きたかったURLを覚えさせ**、`session.flash("toastPayload", ...)` で理由のメッセージを積んで、`/auth/login` へリダイレクト。

`flash` は「次の1回読まれたら消える」置き場です。だから `login.tsx` の action 末尾で `session.get("redirectAfterAuth")` が読めて、ログイン後に元のページへ戻れる。トーストのほうは `root-layout.tsx` の loader が取り出して `showToast` に渡しています。

## なぜこうなっているのか

**なぜ印を Cookie に入れるのか（localStorage ではなく）**
`sessions/sessions.ts` の cookie 設定に `httpOnly: true` があります。これは JavaScript から読めない Cookie という意味です。もし localStorage に入れると、XSS（悪意あるスクリプトの混入）で盗まれます。代わりに Cookie は勝手に送信されるため CSRF が問題になるので `sameSite: "lax"` を付けている。**片方のリスクを別のリスクと交換している**わけです。

**なぜ鍵が2つあるのか**
`JWT_SECRET`（印そのものの署名）と `SESSION_SECRET`（Cookie の署名）で別物です。二重に署名がかかっています。`.env.example` に両方あるはずで、Issue #1 がこれです。

**なぜ JWT なのに、毎回 DB を引いているのか**
ここが一番面白い所です。JWT の売りは「署名を検証すれば DB を見ずに本人確認できる」ことなのに、`user.ts` は結局 `userRepository.getById` を呼んでいます。得るもの・失うものがあり、**設計判断として議論の余地がある**箇所です。

## ついでに気づいたこと

`routes/auth/logout.tsx` は今 `<div>Logout</div>` を返すだけです。`sessions.ts` に `destroySession` は用意されているのに、呼ばれていません。つまり**ログアウトは未実装**です。Issue 一覧にも無いので、意図的な穴か手つかずかは分かりません。

---

ここまでで、一番しっくり来なかったところはどこですか。**「全部ぼんやり」でも構いません**、それも情報です。

あと2つ、軽いものを。

**(1) 前提確認：** Cookie でログイン状態を保つ仕組みは、他の言語やフレームワークで触ったことがありますか？（PHP のセッション、Django、Express など。無ければ無いで大丈夫です）

**(2)** `sessions/jwt.ts` が印に入れているのが「ユーザーID だけ」で、名前もメールも入れていないのは、どれに近いと思いますか。**「分からない」でも構いません。**

- A. 入れられる情報量に制限がある
- B. 印の中身は誰でも覗けるので、入れたくない
- C. 名前は変わりうるので、印に焼き付けたくない