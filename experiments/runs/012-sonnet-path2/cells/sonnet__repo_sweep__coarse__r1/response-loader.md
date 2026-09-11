一通り見てきました。まず**場所だけ**地図として渡します(中身の説明はまだしません)。これはワークショップ用に作られたReact Routerアプリのようです。

## 全体像

```
学習用ドキュメント・課題
├── docs/                  … 環境構築・進め方の説明
├── issues/                … 01〜07の課題(Easy〜)。GitHub Issueとしても取り込まれる
└── scripts/setup/         … `bun run setup`で使うセットアップ用スクリプト(GitHub連携)

アプリ本体 (app/)
├── routes.ts              … ルーティング定義(どのURLでどのファイルを使うか)
├── routes/                … 画面ごとのファイル本体(auth, app/live/band など)
├── components/
│   ├── common/             自作の共通コンポーネント
│   └── ui/                 shadcn/uiが生成したパーツ(button, cardなど)
├── domain/
│   ├── entities/           業務上の型・データ構造(live, band, userなど)
│   ├── service/            業務ロジック
│   └── data/errors.ts       ドメイン用のエラー定義
├── repositories/          … DBとのやり取り(band.ts / live.ts / user.ts)
├── db/                    … drizzle ORMのテーブル定義・DB接続
├── sessions/              … ログインセッション・JWT関連
├── middlewares/           … ルートに挟む処理
├── hooks/                 … Reactカスタムフック
└── lib/                   … 汎用ユーティリティ(日付、ハッシュ、エラー処理など)

設定ファイル類
package.json / vite.config.ts / tsconfig.json / components.json など
```

アプリの中身としては「ライブ(イベント)にバンドが出演申請して、タイムテーブルを組む」ような業務アプリになっています(`live`, `band`, `application`, `timetable` などのルート名から)。

`issues/01-env.md` 〜 `07-validation.md` が段階的な課題になっていて、`docs/ワークショップの進め方.md` によると「Issueを選ぶ→ブランチを切る→直す→PRを出す」という流れで進める設計です。

ここまでで、**いま一番気になっている場所**はどこですか？(「全部ぼんやり」でも大丈夫です。例えば「ルーティングの仕組み」「domainとrepositoriesの違い」「まずissuesを見たい」など、なんでもどうぞ)