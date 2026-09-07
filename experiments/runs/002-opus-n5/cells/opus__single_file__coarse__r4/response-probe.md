読んできました。認証に関わるファイルは6つくらいに散っているので、まず**地図**を出します。細部はそのあとで、あなたが選んだところだけ掘りましょう。

---

## 全体像：鍵は「2枚重ね」になっている

このアプリの認証は、**Cookie の層**と **JWT の層**が入れ子になっています。ここが最初の分かりにくさの正体だと思います。

```
ブラウザの Cookie "__session"   ← SESSION_SECRET で署名されている
  └ 中身: { sessionToken: "eyJhbGci..." }   ← JWT_SECRET で署名されている
        └ 中身: { id: 42, iat:..., exp:... }
```

つまり、サーバーが最終的に知りたいのは **ユーザーID の数値ひとつだけ**です。それを外側の Cookie が包み、さらに JWT が包んでいる、という構造になっています。

| ファイル | 役割 |
|---|---|
| `app/sessions/sessions.ts` | 外側の箱。Cookie の設定と読み書き |
| `app/sessions/jwt.ts` | 内側の札。JWT の発行と検証 |
| `app/lib/hash.ts` | パスワードの bcrypt ハッシュ化・照合 |
| `app/routes/auth/login.tsx` | 札を**発行する**場所（action 関数） |
| `app/middlewares/user.ts` | 札を**検問する**門番 |
| `app/routes.ts` | 門番を**どこに立てるか**の配置図 |

---

## 流れ1：ログインするとき（`login.tsx` の `action`、83行〜）

上から順に、こういう階段になっています。

1. フォームから `mail` と `password` を取り出す
2. `userRepository.getByMail(mail)` でユーザーを探す → いなければ `UserNotFoundError`
3. `authenticateWithPassword` で bcrypt 照合 → 合わなければ `InvalidPasswordError`
4. **`signToken(user.id)`** ← ここで JWT が生まれる（117行）
5. `session.set("sessionToken", token)` で Cookie の中身に入れる
6. `commitSession` が `Set-Cookie` ヘッダの文字列を作る（128行）
7. `redirect` でブラウザに返す

**「ログイン状態」の実体は、この Set-Cookie ヘッダ1つです。** サーバー側にはセッションの記録が一切残りません（ここは後で「なぜ」に関わります）。

## 流れ2：ページにアクセスするとき（`middlewares/user.ts`）

`userMiddleware` は、流れ1の**逆をたどって**います。

```
Cookie ヘッダ → getSessionFromRequest → session.get("sessionToken")
  → verifyToken → payload.id → userRepository.getById → context.set(userContext, user)
```

そして途中に**関門が4つ**あります。見ると分かる通り、失敗パターンごとに同じ形のブロックが並んでいます。

| 行 | 何を弾いているか |
|---|---|
| 23 | そもそも Cookie に token がない（＝未ログイン） |
| 37 | token が**壊れている・改ざん・期限切れ** |
| 60 | DB アクセス自体が失敗した |
| 74 | token は正しいが、**そのユーザーがもう DB にいない** |

4つとも、やることは同じです。「token を捨てる → トースト用メッセージを flash に置く → 戻り先URLを flash に置く → `/auth/login` へリダイレクト」。

最後まで通過したときだけ、86行の `context.set(userContext, user)` が実行されます。以降のルートは `context.get(userContext)` で**「ログイン済みユーザーが必ずいる」前提**でコードを書けるようになります。

## 流れ3：どこが守られているか（`routes.ts`）

これは配置図を見るのが一番早いです。

```
/            ← 素通り
/auth/*      ← 素通り
/app/**      ← layout("app-middleware.tsx") の中 = 門番あり
```

`app-middleware.tsx` は9行しかなく、中身は `middleware = [userMiddleware]` と `<Outlet />` だけです。**「守るためだけに存在する、見た目を持たない層」**を1枚挟んでいる、という設計です。

---

## なぜこうなっているのか、3つ

**なぜ Cookie の中にわざわざ JWT を入れるのか**

Cookie 自体もう署名されているので、`{ userId: 42 }` を直接入れても改ざんはできません。二重に見えます。
違いは **有効期限**です。`jwt.ts` 15行の `expiration = "30d"` により、JWT は自分で期限を持ちます。Cookie が生き残っていても、30日経った札は `JWTExpired` で弾かれる。期限の管理を Cookie の設定ではなく値そのものに持たせている、という選択です。

**なぜミドルウェアで DB まで引きにいくのか（58行）**

JWT を検証した時点で ID は分かるので、そこで止めてもよさそうです。でもそれをやると、**退会したユーザーの札が30日間そのまま通ってしまう**。JWT は「サーバー側で取り消せない」のが弱点なので、毎回 DB で存在確認して、その穴を埋めています。74行の分岐がまさにそれです。

**なぜ `flash` を使うのか（25行、50行など）**

`session.set` は残り続けますが、`session.flash` は **一度読まれたら消える**値です。「ログインしてください」というトーストは1回出れば十分で、次のページでも出続けたら困る。`redirectAfterAuth`（元いたページのURL）も同じで、`login.tsx` 125行で読まれた瞬間に消えます。

---

## 補足：地図の空白

2つだけ、頭に入れておくといい点があります。

- **`app/routes/auth/logout.tsx` は `<div>Logout</div>` を返すだけの空箱**です。ログアウト処理はまだありません（`destroySession` は `sessions.ts` から export されていますが、どこからも使われていません）
- `sessions.ts` 11行に `applicationToken` という別系統のトークンがあり、これは `/app/out/.../live-application/:token` で使われる**バンド出演申請用の招待リンク**の仕組みです。ログイン認証とは別の話なので、今回は切り離して考えて大丈夫です

---

ここまでで、**一番「まだモヤッとする」のはどこですか？** 名前を挙げるだけで大丈夫です（「Cookieと JWT の二重のところ」「middleware と context」「flash」など）。

もし特に無ければ、ひとつ予想してみてください。**間違っても全然かまいません、確認テストではなく話の入り口として聞いています。**

> ブラウザの開発者ツールで `__session` Cookie の値を手で1文字書き換えてから `/app` を開いたら、何が起きると思いますか？
> A: 何も起きない（普通に開ける） / B: `/auth/login` に飛ばされる / C: サーバーがエラーを吐いて500になる
>
> ……「分からない」でも大丈夫です。その場合は `user.ts` の36〜54行と `jwt.ts` の52行あたりを見てから答えてみてください。