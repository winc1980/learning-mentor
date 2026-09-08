一通り読みました。地図から描きます。

## 登場人物は5つ

| ファイル | 役割 |
|---|---|
| `app/lib/hash.ts` | パスワードを bcrypt でハッシュ化する／照合する |
| `app/sessions/jwt.ts` | **ユーザーIDを、署名付きの文字列（JWT）に変換する／戻す**。有効期限30日 |
| `app/sessions/sessions.ts` | **その文字列を Cookie に出し入れする**。Cookie名は `__session` |
| `app/middlewares/user.ts` | **門番**。リクエストごとに Cookie を検証し、User を取り出す |
| `app/routes.ts` | **配線**。どのURLに門番を効かせるかを決めている |

## 流れは2本だけ

**A. ログインするとき**（`routes/auth/login.tsx` の `action`）

```
フォーム送信 (mail, password)
  → userRepository.getByMail でユーザーを探す
  → authenticateWithPassword でパスワード照合（中で bcrypt）
  → signToken(user.id) で JWT を作る
  → session.set("sessionToken", token) で Cookie に詰める
  → redirect（元いたページ or /app）
```

**B. ログインが必要なページを開くとき**（`middlewares/user.ts`）

```
リクエスト到着
  → Cookie から sessionToken を取り出す
  → 無ければ → /auth/login へリダイレクト
  → verifyToken で検証 → 失敗なら → /auth/login へ
  → payload.id で DB からユーザーを取得 → いなければ → /auth/login へ
  → context.set(userContext, user)   ← ここでやっと通す
```

Bが通ったあと、各ページは `context.get(userContext)` でログイン中のユーザーを受け取れます。

## どのURLが守られているか

`app/routes.ts` の18行目、`prefix("app", [ layout("./routes/app/app-middleware.tsx", [...]) ])` がその答えです。`app-middleware.tsx` の中身は5行だけで、`middleware = [userMiddleware]` と書いてあるだけ。つまり **`/app` 以下すべてが門番の内側**、`/auth/login` や `/auth/register` は外側、という区分けになっています。

---

ここまでが全体像です。この先どこを掘るか決めたいので、一つ選んでください。**「どれもピンと来ない」でも構いません。**

- **A**: `signToken` / `verifyToken` の中身 — JWTって結局何なのか、なぜ「署名」なのか
- **B**: Cookie とセッションの関係 — `SESSION_SECRET` と `JWT_SECRET` の2つが出てきますが、なぜ署名が2重にかかっているのか
- **C**: middleware と `context` の仕組み — なぜ各ページで書かずに、middleware に置くと全ページに効くのか
- **D**: `redirectAfterAuth` や `toastPayload` の `flash` — 通常の `set` と何が違うのか

あと、地図として正確に伝えておくと、**`routes/auth/logout.tsx` は現状 `<div>Logout</div>` を返すだけで中身がありません。** ログアウト処理はまだ実装されていない状態です。これが気になっていたなら、そこを扱うこともできます。