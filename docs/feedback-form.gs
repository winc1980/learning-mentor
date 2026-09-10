/**
 * 学習メンター 利用者フィードバックフォームを作る（1回だけ実行する）
 *
 * 使い方:
 *   1. https://script.google.com/ で新しいプロジェクトを作る
 *   2. このファイルの中身を全部貼り付ける
 *   3. 関数 createFeedbackForm を実行（初回は権限の承認を求められる）
 *   4. 実行ログに出る「回答用URL」を配布し、「編集用URL」を運営で控える
 *
 * このスクリプトは実行するたびに新しいフォームを作る。作り直したら旧フォームは
 * 手で閉じること（回答受付を止める）。URL が2つ生きていると回答が分散する。
 *
 * これは運営が使う道具で、配布物ではない（docs/ の中身は zip に入らない）。
 * 参加者に渡すのは、ここで作られたフォームの回答用URLだけ。
 *
 * ── 項目を足したくなったときに読むこと ───────────────────────────
 *
 * 【聞かないもの：満足度・好き嫌い・「正解のコードが欲しかったか」】
 * 選好は「学習者が何を期待するか」の表明であって、学習に効いたかの証拠ではない。
 * 集めると判定がそちらに引きずられる。根拠は experiments/DECISIONS.md
 * 「参加者の選好を判定に使うこと」。代わりに Q9（そのあと、どうしたか＝行動）を
 * 必須にしてある。ここを削らないこと。
 *
 * 【Q11（動作確認を通したか）を落とさないこと】
 * 配置ミスは無言で起きる。ここが「いいえ」の報告は、「メンターの挙動が変」と
 * 「そもそも普通のAIと話していた」を区別できない。判断の前にこれを見る。
 *
 * 【この項目は .github/ISSUE_TEMPLATE/feedback.md と1対1で対応している】
 * 対応が崩れても、どちらもエラーを出さない。運営が回答を issue に写すときに
 * 「写す先の見出しが無い」で初めて気づくことになる。片方を直したら、必ず両方直す。
 * ────────────────────────────────────────────────
 */

var FORM_TITLE = '学習メンター 使ってみた報告';

var FORM_DESCRIPTION = [
  '学習メンター（AIに解説だけをさせる役割定義）を使ってみて、どうだったかを教えてください。',
  '',
  '5〜10分ほどです。1回の出来事につき1件、思い出せる範囲で構いません。',
  '',
  'うまくいかなかった話、途中で使うのをやめた話ほど知りたい内容です。',
  '良かった／悪かったの評価は聞きません。実際に何が起きて、そのあとどうしたかを書いてください。',
  '',
  '氏名・discord名などは任意です。'
].join('\n');

function createFeedbackForm() {
  var form = FormApp.create(FORM_TITLE);
  form.setDescription(FORM_DESCRIPTION);

  // 回答者を特定しない。連絡先は Q12 で任意にもらう。
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setAllowResponseEdits(true);
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(true);
  form.setConfirmationMessage(
    'ありがとうございます。ご報告いただいた内容は学習メンターの改善に活用させていただきます。\n' +
    '別の出来事についても報告できます（同じURLからもう一度どうぞ）。'
  );

  // ── Q1 いつ・どこで ─────────────────────────────
  form.addTextItem()
    .setTitle('いつ・どこで使いましたか')
    .setHelpText('学習会の回、またはプロジェクト名。日付も。例：「phase2 学習会 第4回 / 9月12日」「個人開発のポートフォリオ / 9月15日ごろ」')
    .setRequired(true);

  // ── Q2 使ったツール ─────────────────────────────
  form.addMultipleChoiceItem()
    .setTitle('使ったツール')
    .setChoiceValues(['Claude Code', 'Codex CLI'])
    .showOtherOption(true)
    .setRequired(true);

  // ── Q3 運用 ────────────────────────────────────
  form.addMultipleChoiceItem()
    .setTitle('どちらの運用で入れていましたか')
    .setHelpText('A＝そのリポジトリでは常にメンターとして応答する。B＝learn と呼び出したときだけメンターになる。分からなければ「分からない」で構いません。')
    .setChoiceValues([
      'A：常時適用（何もしなくてもメンターとして応答する）',
      'B：呼び出し型（learn と呼んだときだけメンターになる）',
      '分からない'
    ])
    .setRequired(true);

  // ── Q4 モデル / Q4b バージョン ──────────────────
  // feedback.md 側が「モデル」「バージョン」の2行なので、フォームも2項目に分ける。
  // 1項目にまとめると、転記のたびに人が分割することになる。
  form.addTextItem()
    .setTitle('使ったモデル（分かれば）')
    .setHelpText('例：Claude Opus 5 / GPT-5.6 Sol。既定のまま使っていて分からなければ空欄で構いません。')
    .setRequired(false);

  form.addTextItem()
    .setTitle('メンターのバージョン（分かれば）')
    .setHelpText('python mentor-update.py --check を実行すると v0.1.2 のように出ます。分からなければ空欄で構いません。')
    .setRequired(false);

  // ── Q5 何をしようとしていたか ───────────────────
  form.addParagraphTextItem()
    .setTitle('そのとき、何をしようとしていましたか')
    .setHelpText('取り組んでいた作業。例：「学習会のタスク2（ログイン画面）」「エラーが出て動かなくなった」')
    .setRequired(true);

  // ── Q6 どう使ったか ─────────────────────────────
  form.addMultipleChoiceItem()
    .setTitle('どう使いましたか')
    .setChoiceValues([
      '解説（分からないことを聞いた）',
      'レビュー（書いたコードを見てもらった）',
      'トラブル対応（動かないものを一緒に調べた）'
    ])
    .setRequired(true);

  // ── Q7 最初に送った一言 ─────────────────────────
  form.addParagraphTextItem()
    .setTitle('最初に送った一言（そのまま貼ってください）')
    .setHelpText('要約せず、実際に打った文をそのまま。覚えていなければ空欄で構いません。')
    .setRequired(false);

  // ── Q8 実際に起きたこと ─────────────────────────
  form.addParagraphTextItem()
    .setTitle('実際に何が起きましたか')
    .setHelpText('メンターが何を返したか。やり取りの本文が残っていれば、そのまま貼ってください（要約より原文の方が役に立ちます）。')
    .setRequired(true);

  // ── Q9 そのあと、どうしたか（ここが一番重要） ────
  form.addCheckboxItem()
    .setTitle('そのあと、どうしましたか（当てはまるもの全部）')
    .setHelpText('実際に起きたことを選んでください。「途中でやめた」も大事な情報です。')
    .setChoiceValues([
      'メンターとのやり取りだけで解決した',
      '人に聞いた',
      '普通のAI／通常の開発セッションに切り替えた',
      '自分で調べた',
      '手が止まったまま、その日は進まなかった',
      'メンターを使うのをやめた'
    ])
    .setRequired(true);

  // ── Q10 期待とのズレ ────────────────────────────
  form.addParagraphTextItem()
    .setTitle('期待とのズレ（任意）')
    .setHelpText('「こうなると思っていたが、こうだった」という形で書いてください。要望ではなく、ズレとして。')
    .setRequired(false);

  // ── Q11 動作確認（落とさないこと） ──────────────
  form.addMultipleChoiceItem()
    .setTitle('メンターを配置したあと、動作確認（ツール一覧の確認）を通しましたか')
    .setHelpText('README の「3. 動作確認する」の手順です。通していなくても構いません。正直に答えてもらう方が、こちらの判断が正確になります。')
    .setChoiceValues(['はい', 'いいえ', '覚えていない'])
    .setRequired(true);

  // ── Q12 連絡先 ──────────────────────────────────
  form.addTextItem()
    .setTitle('名前（追加で詳しい状況などを聞いてもよければ）')
    .setHelpText('氏名、Discordのユーザー名など。空欄で構いません。')
    .setRequired(false);

  // 回答をスプレッドシートに落とす（issue に写すときはここから読む）
  var ss = SpreadsheetApp.create(FORM_TITLE + '（回答）');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  Logger.log('回答用URL（これを配布する）: ' + form.getPublishedUrl());
  Logger.log('短縮URL: ' + form.shortenFormUrl(form.getPublishedUrl()));
  Logger.log('編集用URL（運営が控える）: ' + form.getEditUrl());
  Logger.log('回答スプレッドシート: ' + ss.getUrl());
}
