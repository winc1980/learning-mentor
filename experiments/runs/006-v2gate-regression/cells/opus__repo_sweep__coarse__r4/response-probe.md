認証まわりですね。ここは登場人物が多いので、**まずは場所だけ挙げます。中身の説明はまだしません。**

その前に一つだけ聞かせてください（説明の入り口を決めたいので）。

**この質問が出てきたきっかけは何でしたか？** 例えば「Issueを読んでいて出てきた」「ログインしたのに弾かれた」「コードを追っていて `userMiddleware` で迷子になった」など。「なんとなく全体を知りたい」でも大丈夫です。

---

## 認証に関わるファイル（地図）

大きく **6つの役割** に分かれています。

| 役割 | ファイル |
|---|---|
| ① Cookieの入れ物を作る・読む・書く | `app/sessions/sessions.ts` |
| ② トークンの発行と検証 | `app/sessions/jwt.ts` |
| ③ 門番（ログイン済みかチェックする処理） | `app/middlewares/user.ts` |
| ④ 門番をどのURLに置くか | `app/routes.ts` / `app/routes/app/app-middleware.tsx` |
| ⑤ 入口と出口（画面と送信処理） | `app/routes/auth/login.tsx` `register.tsx` `logout.tsx` |
| ⑥ ユーザー本体（DB・型・パスワード） | `app/repositories/user.ts` / `app/db/schema.ts` / `app/domain/entities/user.ts` / `app/lib/hash.ts` |

補助的に、こんなものもぶら下がっています。

| | |
|---|---|
| 認証エラーの種類 | `app/domain/data/errors.ts` |
| 必要な環境変数（`SESSION_SECRET` / `JWT_SECRET`） | `.env.example` |

---

## 位置関係だけ

```
ブラウザ
  │  Cookie
  ▼
① sessions.ts  ──  ② jwt.ts
  │
  ▼
③ user.ts（門番）  ──  ⑥ repositories/user.ts → DB
  │
  ▼
④ /app 配下の各ページ
```

`⑤ login / register / logout` は、この輪の**外側から Cookie を作ったり消したりする**位置にいます。

---

この①〜⑥のうち、**いま一番気になっているのはどれですか。** 「全部ぼんやりしている」でも構いません。その場合はこちらから順番を提案します。

（前回聞きそびれた点も、もし答えやすければ：**Cookie や JWT は、これまで触ったことがありますか？** 「名前は知ってる」「初めて」でも大丈夫です）