/**
 * phase2 学習会 導入前／事後アンケートを作る（運営向け）
 *
 * 使い方:
 *   1. https://script.google.com/ で新しいプロジェクトを作る
 *   2. このファイルの中身を全部貼り付ける
 *   3. 9/12 の学習会の前に  createPreSurveyForm()  を実行する
 *      9/26 の LT 会の前に   createPostSurveyForm() を実行する
 *   4. 実行ログに出る「回答用URL」を配布し、「編集用URL」を運営で控える
 *
 * これは運営が使う道具で、配布物ではない（docs/ の中身は zip に入らない）。
 * 参加者に渡すのは、ここで作られたフォームの回答用URLだけ。
 *
 * 利用者フィードバック（随時受け付ける「使ってみた報告」）は別物で、
 * docs/feedback-form.gs が持つ。こちらは 9/12 と 9/26 の2点でしか取らない。
 *
 * ══════════════════════════════════════════════════════════════
 * 触る前に読むこと
 * ══════════════════════════════════════════════════════════════
 *
 * 【導入前と事後は「同一文面・同一尺度」でなければ意味がない】
 * 成功の判定は導入前後の差分である。文面や尺度が変わると、差分は
 * 「変化」ではなく「言い方が変わったこと」を測ってしまう。
 * だから共通設問は COMMON_ITEMS に1回だけ書き、2つのフォームはそこから生成している。
 * **ここを2箇所にコピーしないこと。**
 *
 * ずれても Google フォームはエラーを出さない。気づくのは 9/26 に集計しようとして
 * 「導入前と文面が違う」と分かった時で、**その時点ではもう取り直せない。**
 *
 * 【9/12 に回答が入った後、フォームの編集画面で文面を直さない】
 * 直すと、すでに集まった回答が古い文面のものになり、後から区別できない。
 * どうしても直すなら、このファイルを直して**両方を作り直し、旧フォームは閉じる**。
 *
 * 【COMMON_ITEMS の4項目は docs/concept.md の「成功の条件」と1対1】
 * concept.md 側の文言を変えたら、こちらも変える。逆も同じ。
 * check-sync.ts はこの対応を見ていない（見ているのは役割定義の本文だけ）。
 * **この対応が壊れたことを機械的に知る方法は無い。**
 *
 * 【どの設問がどの判定に効いているか】
 * 消すと判定そのものが不能になる設問がある。「答えにくそうだから」で落とさないこと。
 *
 *   設問                       | 何の判定に使うか                          | どちらのフォーム
 *   ---------------------------|-------------------------------------------|------------------
 *   COMMON_ITEMS の4項目       | 成功の条件（導入前後の変化）              | 両方
 *   人への質問の頻度           | 中止条件「質問が0になった」               | 両方
 *   GitHub ユーザー名          | 導入前後・リポジトリの記録との突合        | 両方
 *   有料AIの契約状況           | 中止条件「導入できない人が3割以上」        | 導入前
 *   メンターの利用度（5段階）  | 中止条件「2以下が半数以上」／散布図の横軸 | 事後
 *   メンターを外したか         | 中止条件「アンインストールした人が複数」  | 事後
 *
 * 【「外した」と「使わなくなった」を1つの選択肢にまとめないこと】
 * 後者は自然消滅だが、前者は**普通のAIを使うために能動的に取り除いた**という
 * もっと強い拒否のサインで、中止条件はこちらだけを指している。
 * まとめた瞬間に中止条件が判定不能になる。しかもそれは集計時まで見えない。
 *
 * 【満足度・好き嫌い・「便利だったか」は聞かない】
 * 選好は学習者が何を期待するかの表明であって、学習に効いたかの証拠ではない。
 * 根拠は experiments/DECISIONS.md「参加者の選好を判定に使うこと」。
 * ══════════════════════════════════════════════════════════════
 */

// ── 期間の文言 ──────────────────────────────────────────────
// 設問文に必ず埋め込む。「8月」「9月」で切らない理由：9月には導入前の11日間が
// 含まれるため、月で聞くと回答者ごとに違う期間を思い浮かべる。n=10 では
// その揺れが、測りたい効果より大きくなる。
var PERIOD_PRE = 'phase2開始〜9/11';
var PERIOD_POST = '9/12〜9/26';

/**
 * 導入前・事後の両方で聞く設問。docs/concept.md の「成功の条件」と1対1。
 * {period} は各フォームの期間に置き換わる。
 */
var COMMON_ITEMS = [
  {
    title: '【{period}】質問できる人がいない場所でも、学習を一人で進められている',
    help: 'この期間を振り返って答えてください。',
    low: '1 ほとんど進められなかった',
    high: '5 問題なく進められた'
  },
  {
    title: '【{period}】新しく学んだ概念を、人に説明できるレベルまで深く理解することができている',
    help: '「動かせた」ではなく「説明できる」かどうかで答えてください。',
    low: '1 ほとんどできなかった',
    high: '5 よくできた'
  },
  {
    title: '【{period}】分からないことを、自分で解決できている（ネット検索・AI利用等を含む）',
    help: '手段は問いません。人に聞かずに解決までたどり着けたかどうかです。',
    low: '1 ほとんどできなかった',
    high: '5 よくできた'
  },
  {
    title: '【{period}】の時点での、phase3 の開発プロジェクトへのモチベーション',
    help: 'いま現在どう感じているかで構いません。',
    low: '1 まったく湧かない',
    high: '5 とても高い'
  }
];

/**
 * これも両方で聞く。中止条件「人間のメンターへの質問が0になった」の判定用。
 * 0 になったかどうかは、元が何件かを知らないと言えない。
 */
var HUMAN_QUESTION_ITEM = {
  title: '【{period}】学習会や Discord で、人（メンター・他の参加者）に質問しましたか',
  help: 'AI にではなく、人に聞いた回数です。',
  choices: [
    'ほぼ毎回の学習会で聞いた',
    '何度か聞いた',
    '1回だけ聞いた',
    '一度も聞いていない'
  ]
};

/** {period} を実際の期間に置き換える。 */
function fill_(text, period) {
  return text.replace('{period}', period);
}

/** 回答者の識別。導入前・事後・リポジトリの記録を突合する唯一の鍵。 */
function addIdentifier_(form) {
  form.addTextItem()
    .setTitle('GitHub のユーザー名')
    .setHelpText(
      'fork したリポジトリの URL に出てくる名前です（例：github.com/【ここ】/2026-phase-2）。\n' +
      '導入前と導入後の回答を、同じ人のものとして突き合わせるためだけに使います。\n' +
      '回答は運営のみが見ます。個人ごとに点数を付けたり、成績として扱ったりはしません。'
    )
    .setRequired(true);
}

/** 共通設問を追加する。導入前・事後で同じ順番・同じ尺度になる。 */
function addCommonItems_(form, period) {
  for (var i = 0; i < COMMON_ITEMS.length; i++) {
    var item = COMMON_ITEMS[i];
    form.addScaleItem()
      .setTitle(fill_(item.title, period))
      .setHelpText(item.help)
      .setBounds(1, 5)
      .setLabels(item.low, item.high)
      .setRequired(true);
  }

  form.addMultipleChoiceItem()
    .setTitle(fill_(HUMAN_QUESTION_ITEM.title, period))
    .setHelpText(HUMAN_QUESTION_ITEM.help)
    .setChoiceValues(HUMAN_QUESTION_ITEM.choices)
    .setRequired(true);
}

/** 回答をスプレッドシートに落とし、URL をログに出す。 */
function finish_(form, title) {
  var ss = SpreadsheetApp.create(title + '（回答）');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  Logger.log('回答用URL（これを配布する）: ' + form.getPublishedUrl());
  Logger.log('短縮URL: ' + form.shortenFormUrl(form.getPublishedUrl()));
  Logger.log('編集用URL（運営が控える）: ' + form.getEditUrl());
  Logger.log('回答スプレッドシート: ' + ss.getUrl());
}

// ══════════════════════════════════════════════════════════════
// 導入前アンケート（9/12 の学習会で、メンターを配置する前に取る）
// ══════════════════════════════════════════════════════════════

/**
 * **配置作業のあとに取ってはいけない。** 配置を体験した直後だと、その場の印象が
 * 「導入前はどうだったか」の回答に混ざる。
 *
 * 9/26 にまとめて「導入前はどうでしたか」と聞くのは、もっと悪い。メンターを使った人は
 * 「ツールを入れた」という自覚があるので、導入前の自分を低く見積もる動機を持つ。
 * 対照側にはこの動機がない。**このバイアスは検出したい効果とまったく同じ向きに乗る**
 * ので、効果がゼロでも散布図が右上がりになる。
 */
function createPreSurveyForm() {
  var title = 'phase2 学習会 アンケート（導入前・9/12）';
  var form = FormApp.create(title);

  form.setDescription([
    'phase2 の学習会で AI 学習メンターを試すにあたって、いまの状態を記録しておくためのアンケートです。',
    '',
    '3分ほどです。9/26 に同じ設問をもう一度お聞きして、変化を見ます。',
    '',
    'これはテストではありません。低く答えても誰にも不利益はありませんし、',
    '正直な数字でないと、そもそも比較ができなくなります。',
    '',
    '回答は運営のみが見ます。個人ごとの点数化や、成績としての利用はしません。'
  ].join('\n'));

  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setAllowResponseEdits(true);
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage(
    'ありがとうございます。このあと、学習メンターを配置する作業に進んでください。'
  );

  addIdentifier_(form);
  addCommonItems_(form, PERIOD_PRE);

  // ── 中止条件「導入できない人が3割以上」の判定用 ───────────
  // 当日その場で人数を数える（issue #30）のとは別に、ここでも記録を残す。
  // 口頭で数えた人数は当日の記憶に依存するが、こちらは残る。
  form.addMultipleChoiceItem()
    .setTitle('現在、有料プランの AI を契約していますか')
    .setHelpText('学習メンターは Claude Code / Codex CLI の上で動くため、無料枠だけでは実用にならない場合があります。契約していないこと自体は問題ありません。')
    .setChoiceValues([
      'Claude（Pro / Max など）を契約している',
      'ChatGPT（Go / Plus / Pro など）を契約している',
      'その他のAI(Geminiなど)、または複数のAIを契約している',
      '契約していない',
      '分からない'
    ])
    .setRequired(true);

  finish_(form, title);
}

// ══════════════════════════════════════════════════════════════
// 事後アンケート（9/26 の LT 会で取る。実施は issue #31）
// ══════════════════════════════════════════════════════════════

/**
 * 共通設問は導入前とまったく同じ順番・同じ尺度で出る（COMMON_ITEMS から生成）。
 * 固有の設問を足すのは構わないが、**COMMON_ITEMS より前に置かない**こと。
 * 利用度やアンインストールを先に聞くと、「自分はあまり使わなかった」という自覚が
 * そのあとの4項目の自己評価に影響する。
 */
function createPostSurveyForm() {
  var title = 'phase2 学習会 アンケート（事後・9/26）';
  var form = FormApp.create(title);

  form.setDescription([
    '9/12 にお答えいただいたものと同じ設問を、もう一度お聞きします。',
    '',
    '5分ほどです。導入前と比べるためのものなので、9/12 の回答に合わせにいかず、',
    'いま感じているままを答えてください。',
    '',
    '使わなかった・途中でやめた場合こそ、そのまま答えてください。',
    'それが分からないと、次に何を直すべきかが決まりません。',
    '',
    '回答は運営のみが見ます。個人ごとの点数化や、成績としての利用はしません。'
  ].join('\n'));

  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setAllowResponseEdits(true);
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage('ありがとうございます。phase2 お疲れさまでした。');

  addIdentifier_(form);
  addCommonItems_(form, PERIOD_POST);

  // ── 散布図の横軸／中止条件「2以下が半数以上」 ─────────────
  form.addScaleItem()
    .setTitle('9/12〜9/26 の間、学習メンターをどれくらい使いましたか')
    .setHelpText('使わなかった場合は 1 を選んでください。少ないこと自体は問題ではありません。')
    .setBounds(1, 5)
    .setLabels('1 ほとんど使わなかった', '5 ほぼ毎回使った')
    .setRequired(true);

  // ── 中止条件「アンインストールした人が複数」 ───────────────
  // 「外した」は自己申告しないと分からない。fork 先の履歴を追えば消したコミットは
  // 見えるが、追う側の手間が現実的でないうえ、「設定は残っているが呼ばなくなった」
  // との区別がつかない。
  form.addMultipleChoiceItem()
    .setTitle('学習メンターの設定を、途中で外しましたか')
    .setHelpText('「外した」＝設定ファイルを消した／無効にした、ということです。使わなくなっただけの場合は、その下の選択肢を選んでください。')
    .setChoiceValues([
      '外していない（入れたまま）',
      '外した（設定ファイルを消した・無効にした）',
      '外してはいないが、途中から使わなくなった',
      '分からない'
    ])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('外した／使わなくなった場合、そのきっかけは何でしたか')
    .setHelpText('そのとき何をしようとしていて、何が起きたか。「普通の AI を使いたかった」でも構いません。該当しなければ空欄で。')
    .setRequired(false);

  // ── 行動の記述。「便利でしたか」の代わりに置いている ───────
  form.addParagraphTextItem()
    .setTitle('メンターを使うのをやめた瞬間はありましたか。そのとき何が起きていましたか')
    .setHelpText('一度もなければ「ない」で構いません。感想ではなく、その場面で起きたことを書いてください。')
    .setRequired(true);

  finish_(form, title);
}
