#!/usr/bin/env bun
/**
 * 配置済みの学習メンターを、GitHub Releases の最新版に追従させる。
 *
 * このスクリプトは4つのモードを持つ。すべて1ファイルに入れてあるのは、
 * 配布物を増やさないため（配るものが増えるほど、古いものが混ざる）。
 *
 *     --setup     配置直後に1回だけ実行する。受領書を書き、hook を設置し、
 *                 動作確認の手順を表示する（旧名 --register も受け付ける）
 *     --check     人が読む形で、新版の有無と hook の健康状態を表示する
 *     --apply     受領書を見て、配置済みのコピーを最新版に貼り直す
 *     --hook      SessionStart hook から呼ばれる。JSON を1行返して即座に終わる
 *
 * なぜ Bun か（v0.2.0 で Python から移行した）:
 *     学習会の環境には bun が入っている。Python は入っている保証がなく、
 *     入っていても `python` / `python3` / `py` のどれで起動するかが環境ごとに違った。
 *     hook のコマンド行を間違えると **何のエラーも出ずに更新のお知らせだけが止まる**。
 *     起動系の分岐を1つ減らせるなら、それだけで移行の価値がある。
 *
 * なぜ依存パッケージを持たないか:
 *     配置先は学習者の手元で、node_modules を置ける場所とは限らない。
 *     `bun mentor-update.ts` の1行で完結させるため、ZIP 展開も差分計算も
 *     このファイル内に持っている（それぞれ readZipEntry / unifiedDiff）。
 *
 * なぜ受領書が要るか:
 *     learning-mentor-setup.md は、配置先をAIに判断させる設計になっている。
 *     このため置き場所は人によって違う。更新側から見ると、探し当てる手段が無い。
 *     配置した時点で記録しておく以外に方法がない。
 *
 * なぜマーカーで囲むか:
 *     【A】常時適用型では本文が CLAUDE.md / AGENTS.md に埋め込まれる。そのファイルには
 *     学習者自身の記述も入りうるので、ファイルごと上書きしてはいけない。
 *     マーカー間だけを差し替える。マーカーの内側は本文と1バイトも変えないので、
 *     check-sync.ts の一致検査はそのまま通る。
 *
 * 終了コード:
 *     0 = 最新（または処理成功） / 1 = エラー / 2 = 新版あり（--check のみ）
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, join, relative, resolve } from "node:path";
import { inflateRawSync } from "node:zlib";

const REPO = "winc1980/learning-mentor";
// 参照先を差し替えられるようにしてあるのは、LEARNING_MENTOR_HOME と同じ理由。
// --apply は本文とスクリプト自身を書き換えるので、**本物のリリースを配る前に
// 隔離した環境で通しで試せないと、検証手段が「本番で一度やってみる」しかなくなる。**
const API_LATEST =
  process.env.LEARNING_MENTOR_API || `https://api.github.com/repos/${REPO}/releases/latest`;
const RELEASES_PAGE = `https://github.com/${REPO}/releases`;

// 配置済みファイルの中で本文を囲む番兵。begin 側だけがバージョンを名乗る。
// 内側は learning-mentor-prompt.md と完全一致させる（check-sync.ts と同じ規約）。
const markBegin = (v: string) => `<!-- learning-mentor:begin v${v} -->`;
const MARK_BEGIN_RE = /<!--\s*learning-mentor:begin\s+v([0-9A-Za-z.\-]+)\s*-->/;
const MARK_END = "<!-- learning-mentor:end -->";

// --target の種別。ここに無い語は種別と見なさない（Windows のドライブレター対策も兼ねる）
//   agent    = .claude/agents/learn.md のような、frontmatter 付きの定義ファイル
//   embedded = CLAUDE.md / AGENTS.md のように、他の記述と同居しているファイル
const TARGET_KIND_RE = /^(agent|embedded):([\s\S]+)$/;

const CHECK_INTERVAL_HOURS = 24; // 成功結果の寿命。GitHub API は未認証で 60回/時
const FAILURE_INTERVAL_HOURS = 1; // 失敗の寿命。短いのは、復旧に早く気づけるようにするため
const NETWORK_TIMEOUT = 5; // 秒。hook を待たせない。繋がらなければ黙って諦める

type Json = any;

// --------------------------------------------------------------------------
// 保存場所
// --------------------------------------------------------------------------

/**
 * 受領書・キャッシュ・スタンプの置き場所。
 *
 * 環境変数で差し替えられるようにしてあるのは、検証用に隔離した状態で
 * 動かせるようにするため（experiments/ が fixture を隔離しているのと同じ理由）。
 */
function home(): string {
  const override = process.env.LEARNING_MENTOR_HOME;
  if (override) return override;
  return join(homedir(), ".learning-mentor");
}

function pathInHome(name: string): string {
  return join(home(), name);
}

/** `~` 始まりのパスを展開する（Python の os.path.expanduser 相当）。 */
function expandUser(p: string): string {
  if (p === "~") return homedir();
  if (p.startsWith("~/") || p.startsWith("~\\")) return join(homedir(), p.slice(2));
  return p;
}

function readText(path: string): string | null {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

function readJson(path: string, fallback: Json = null): Json {
  const text = readText(path);
  if (text === null) return fallback;
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

function writeJson(path: string, data: Json): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(data, null, 2) + "\n", "utf8");
}

function nowIso(): string {
  return new Date().toISOString();
}

/**
 * ISO 8601 の文字列をミリ秒に直す。読めなければ null。
 *
 * v0.1.x（Python 版）が書いたタイムスタンプも読める必要がある。Python の
 * `datetime.isoformat()` は秒の小数部が6桁で、JS の Date.parse は桁数によって
 * 解釈が揺れるため3桁に丸める。タイムゾーンが無い場合に UTC と見なすのも
 * Python 版（hours_since が naive を UTC 扱いしていた）に合わせている。
 * ここを間違えると「hook が最後に動いた時刻」がずれ、--check の判定が狂う。
 */
function parseIso(text: unknown): number | null {
  if (typeof text !== "string" || !text) return null;
  let norm = text.replace(/(\.\d{3})\d+/, "$1");
  if (!/(Z|[+\-]\d{2}:?\d{2})$/.test(norm)) norm += "Z";
  const ms = Date.parse(norm);
  return Number.isNaN(ms) ? null : ms;
}

/** iso_text から何時間経ったか。読めなければ null。 */
function hoursSince(isoText: unknown): number | null {
  const stamp = parseIso(isoText);
  if (stamp === null) return null;
  return (Date.now() - stamp) / 3600000;
}

// --------------------------------------------------------------------------
// バージョン比較
// --------------------------------------------------------------------------

/**
 * "1.2.10" -> [1, 2, 10]。数字でない部分は 0 として扱う。
 *
 * 厳密な semver 実装ではない。プレリリース版を配る予定がないので、
 * 数値の組として比べれば足りる。
 */
function versionKey(text: unknown): number[] {
  const parts = String(text ?? "").trim().replace(/^[vV]/, "").split(/[.\-+]/);
  const key = parts.map((part) => {
    const digits = /^\d+/.exec(part);
    return digits ? parseInt(digits[0], 10) : 0;
  });
  return key.length ? key : [0];
}

/**
 * Python のタプル比較と同じ順序にそろえてある。
 * 短いほうが前方一致なら小さい（(1,2) < (1,2,0)）。0 で埋めて等値にはしない。
 * Python 版と1つでも判定が変わると「更新したつもりが来ない」が起きるため。
 */
function compareKey(a: number[], b: number[]): number {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  if (a.length === b.length) return 0;
  return a.length < b.length ? -1 : 1;
}

function isNewer(latest: unknown, local: unknown): boolean {
  return compareKey(versionKey(latest), versionKey(local)) > 0;
}

// --------------------------------------------------------------------------
// 差分（Python の difflib.unified_diff の代わり）
// --------------------------------------------------------------------------
//
// 標準ライブラリに無いので持っている。check-sync.ts からも使う（配布物を
// 増やさないため、共通部品用のファイルは作らずここから import させている）。
// 出力の形は Python の difflib.unified_diff に合わせてある ── 移行の前後で
// 目視の差分が変わると、「本文がずれた」のか「差分の出し方が変わった」のかを
// 人が切り分けられなくなるため。
//
// 既知の違い（v0.2.0 の移行時に、無作為な 160 件で difflib と突き合わせた実測）:
//   ・出力が difflib と1文字も違わない ........ 150 / 160
//   ・残り 10 件は「同じ変更量を別の位置に割り当てた」だけで、当てれば同じ結果になる
//     （difflib は純粋な LCS ではなく、最長一致ブロックを優先する探索をするため）
//   ・「+N 行 / -M 行」の合計は 160 件すべてで一致した
// つまり --apply の要約表示は Python 版と変わらない。差が出るとしても --diff の見え方だけ。

type Tag = "equal" | "delete" | "insert" | "replace";
type Opcode = [Tag, number, number, number, number]; // tag, i1, i2, j1, j2

/** LCS が現実的な大きさを超えたら諦める閾値。超えた分は「全置換」として扱う。 */
const LCS_CELL_LIMIT = 16_000_000;

/**
 * difflib.SequenceMatcher.get_opcodes 相当。
 *
 * 先に前後の一致行を削ってから LCS にかける。--apply が比べるのはマーカーの
 * 内側だけが変わったファイルなので、この前処理だけで対象行数が桁で落ちる。
 */
export function diffOpcodes(a: string[], b: string[]): Opcode[] {
  let lo = 0;
  while (lo < a.length && lo < b.length && a[lo] === b[lo]) lo++;
  let ha = a.length;
  let hb = b.length;
  while (ha > lo && hb > lo && a[ha - 1] === b[hb - 1]) {
    ha--;
    hb--;
  }

  const midA = a.slice(lo, ha);
  const midB = b.slice(lo, hb);
  const raw: Opcode[] = [];
  if (lo > 0) raw.push(["equal", 0, lo, 0, lo]);

  if (midA.length && midB.length && midA.length * midB.length <= LCS_CELL_LIMIT) {
    for (const op of lcsOpcodes(midA, midB)) {
      raw.push([op[0], op[1] + lo, op[2] + lo, op[3] + lo, op[4] + lo]);
    }
  } else if (midA.length || midB.length) {
    // 大きすぎる／片側が空。最小の差分ではないが、嘘ではない形にして返す。
    raw.push(["replace", lo, ha, lo, hb]);
  }

  if (ha < a.length) raw.push(["equal", ha, a.length, hb, b.length]);
  return mergeReplace(raw);
}

function lcsOpcodes(a: string[], b: string[]): Opcode[] {
  const n = a.length;
  const m = b.length;
  const width = m + 1;
  const table = new Int32Array((n + 1) * width);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[i * width + j] =
        a[i] === b[j]
          ? table[(i + 1) * width + (j + 1)] + 1
          : Math.max(table[(i + 1) * width + j], table[i * width + (j + 1)]);
    }
  }

  const ops: Opcode[] = [];
  const push = (tag: Tag, i1: number, i2: number, j1: number, j2: number) => {
    const last = ops[ops.length - 1];
    if (last && last[0] === tag) {
      last[2] = i2;
      last[4] = j2;
    } else ops.push([tag, i1, i2, j1, j2]);
  };

  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push("equal", i, i + 1, j, j + 1);
      i++;
      j++;
    } else if (table[(i + 1) * width + j] >= table[i * width + (j + 1)]) {
      push("delete", i, i + 1, j, j);
      i++;
    } else {
      push("insert", i, i, j, j + 1);
      j++;
    }
  }
  if (i < n) push("delete", i, n, j, j);
  if (j < m) push("insert", n, n, j, m);
  return ops;
}

/** 隣り合う delete + insert を replace にまとめる（difflib の出力に合わせる）。 */
function mergeReplace(ops: Opcode[]): Opcode[] {
  const out: Opcode[] = [];
  for (const op of ops) {
    const last = out[out.length - 1];
    if (last && last[0] === "delete" && op[0] === "insert") {
      out[out.length - 1] = ["replace", last[1], last[2], last[3], op[4]];
      continue;
    }
    out.push(op);
  }
  return out;
}

/** difflib._format_range_unified 相当。長さ1なら開始行だけ、0なら1つ手前を指す。 */
function formatRange(start: number, stop: number): string {
  let beginning = start + 1;
  const length = stop - start;
  if (length === 1) return String(beginning);
  if (!length) beginning -= 1;
  return `${beginning},${length}`;
}

/** difflib._group_opcodes 相当。前後 n 行だけ文脈として残し、離れた変更は別のハンクに割る。 */
function groupOpcodes(codes: Opcode[], n: number): Opcode[][] {
  if (!codes.length) return [];
  const work = codes.map((c) => [...c] as Opcode);

  const first = work[0];
  if (first[0] === "equal") {
    work[0] = ["equal", Math.max(first[1], first[2] - n), first[2], Math.max(first[3], first[4] - n), first[4]];
  }
  const last = work[work.length - 1];
  if (last[0] === "equal") {
    work[work.length - 1] = ["equal", last[1], Math.min(last[2], last[1] + n), last[3], Math.min(last[4], last[3] + n)];
  }

  const groups: Opcode[][] = [];
  const nn = n + n;
  let group: Opcode[] = [];
  for (const [tag, i1, i2, j1, j2] of work) {
    if (tag === "equal" && i2 - i1 > nn) {
      group.push(["equal", i1, Math.min(i2, i1 + n), j1, Math.min(j2, j1 + n)]);
      groups.push(group);
      group = [["equal", Math.max(i1, i2 - n), i2, Math.max(j1, j2 - n), j2]];
      continue;
    }
    group.push([tag, i1, i2, j1, j2]);
  }
  if (group.length && !(group.length === 1 && group[0][0] === "equal")) groups.push(group);
  return groups;
}

/** difflib.unified_diff(..., lineterm="") 相当。差分が無ければ空配列。 */
export function unifiedDiff(
  a: string[],
  b: string[],
  fromFile: string,
  toFile: string,
  n = 3,
): string[] {
  const groups = groupOpcodes(diffOpcodes(a, b), n);
  if (!groups.length) return [];

  const out = [`--- ${fromFile}`, `+++ ${toFile}`];
  for (const group of groups) {
    const first = group[0];
    const tail = group[group.length - 1];
    out.push(`@@ -${formatRange(first[1], tail[2])} +${formatRange(first[3], tail[4])} @@`);
    for (const [tag, i1, i2, j1, j2] of group) {
      if (tag === "equal") {
        for (const line of a.slice(i1, i2)) out.push(" " + line);
        continue;
      }
      if (tag === "replace" || tag === "delete") for (const line of a.slice(i1, i2)) out.push("-" + line);
      if (tag === "replace" || tag === "insert") for (const line of b.slice(j1, j2)) out.push("+" + line);
    }
  }
  return out;
}

// --------------------------------------------------------------------------
// ZIP の読み出し（Python の zipfile の代わり）
// --------------------------------------------------------------------------

/**
 * ZIP の中から、名前が suffix で終わる最初のエントリを取り出す。
 *
 * 中央ディレクトリだけを読む最小実装。展開ライブラリを足さないのは、
 * 配置先で `bun install` を走らせないと動かないものを配りたくないため。
 * 一時ファイルにも書かない（Python 版は tempfile 経由だった）。
 *
 * Zip64 には対応していない。対応が要るのは 4GB 超か 65535 エントリ超のときで、
 * 配布物の zip は数百KB。該当したら黙って外すのではなく null を返して報告する。
 */
export function readZipEntry(buf: Buffer, suffix: string): Buffer | null {
  const EOCD_SIG = 0x06054b50;
  const CENTRAL_SIG = 0x02014b50;

  let eocd = -1;
  const floor = Math.max(0, buf.length - 22 - 65535);
  for (let i = buf.length - 22; i >= floor; i--) {
    if (buf.readUInt32LE(i) === EOCD_SIG) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) return null;

  const count = buf.readUInt16LE(eocd + 10);
  let offset = buf.readUInt32LE(eocd + 16);

  for (let index = 0; index < count; index++) {
    if (offset + 46 > buf.length || buf.readUInt32LE(offset) !== CENTRAL_SIG) return null;
    const method = buf.readUInt16LE(offset + 10);
    const compressedSize = buf.readUInt32LE(offset + 20);
    const nameLen = buf.readUInt16LE(offset + 28);
    const extraLen = buf.readUInt16LE(offset + 30);
    const commentLen = buf.readUInt16LE(offset + 32);
    const localOffset = buf.readUInt32LE(offset + 42);
    const name = buf.toString("utf8", offset + 46, offset + 46 + nameLen);

    if (name.endsWith(suffix)) {
      // 可変長フィールドの長さは、中央ディレクトリとローカルヘッダで違いうる。
      // データの開始位置はローカルヘッダ側を読み直して出す。
      const localNameLen = buf.readUInt16LE(localOffset + 26);
      const localExtraLen = buf.readUInt16LE(localOffset + 28);
      const start = localOffset + 30 + localNameLen + localExtraLen;
      const raw = buf.subarray(start, start + compressedSize);
      if (method === 0) return Buffer.from(raw);
      if (method === 8) return inflateRawSync(raw);
      return null; // 未対応の圧縮方式。呼び出し側が理由を出す
    }
    offset += 46 + nameLen + extraLen + commentLen;
  }
  return null;
}

// --------------------------------------------------------------------------
// GitHub Releases
// --------------------------------------------------------------------------

interface Latest {
  version: string;
  url: string;
  asset: string | null;
  notes: string;
}

/**
 * 失敗を短時間だけ覚える。直前までの成功結果は消さない。
 *
 * キャッシュごと上書きすると、オフラインになった瞬間に「前回 v1.1.0 を見た」
 * という事実まで失われる。失敗は別のキーに積む。
 */
function rememberFailure(cachePath: string, cache: Json, message: string): [null, string] {
  const next = { ...(cache ?? {}) };
  next.failed_at = nowIso();
  next.error = message;
  try {
    writeJson(cachePath, next);
  } catch {
    // キャッシュが書けないこと自体は、処理を止める理由にならない
  }
  return [null, message];
}

function errorText(exc: unknown): string {
  if (exc instanceof Error) return exc.name === "TimeoutError" ? "時間内に応答がありませんでした" : exc.message;
  return String(exc);
}

/**
 * 最新リリースを取る。成功は24時間、失敗は1時間キャッシュする。
 *
 * 戻り値は [info, error] の組。info は {version, url, asset, notes}。
 * ネットワークが無い環境でも hook を壊さないため、例外は投げずに error を返す。
 *
 * 失敗もキャッシュするのは、オフラインのままセッションを開くたびに
 * タイムアウト（最大 NETWORK_TIMEOUT 秒）を待たされるのを避けるため。
 * 通知の頻度は変わらない ── latest は null のままなので、decideNotice は
 * キャッシュの有無にかかわらず同じ判断をする。
 */
async function fetchLatest(force = false): Promise<[Latest | null, string | null]> {
  const cachePath = pathInHome("cache.json");
  const cache = readJson(cachePath, {}) ?? {};

  if (!force) {
    const age = hoursSince(cache.checked_at);
    if (age !== null && age < CHECK_INTERVAL_HOURS && cache.latest) return [cache.latest, null];
    const failAge = hoursSince(cache.failed_at);
    if (failAge !== null && failAge < FAILURE_INTERVAL_HOURS && cache.error) return [null, cache.error];
  }

  let payload: Json;
  try {
    const response = await fetch(API_LATEST, {
      headers: {
        "User-Agent": "learning-mentor-update",
        Accept: "application/vnd.github+json",
      },
      signal: AbortSignal.timeout(NETWORK_TIMEOUT * 1000),
    });
    if (response.status === 404) {
      return rememberFailure(cachePath, cache, "リリースがまだ1つも公開されていません");
    }
    if (!response.ok) {
      return rememberFailure(cachePath, cache, `GitHub API がエラーを返しました (HTTP ${response.status})`);
    }
    payload = await response.json();
  } catch (exc) {
    // ネットワーク断・DNS・タイムアウトなど
    return rememberFailure(cachePath, cache, `取得できませんでした: ${errorText(exc)}`);
  }

  let assetUrl: string | null = null;
  for (const asset of payload?.assets ?? []) {
    if (String(asset?.name ?? "").endsWith(".zip")) {
      assetUrl = asset?.browser_download_url ?? null;
      break;
    }
  }

  const info: Latest = {
    version: String(payload?.tag_name ?? "").replace(/^[vV]/, ""),
    url: payload?.html_url || RELEASES_PAGE,
    asset: assetUrl,
    notes: String(payload?.body ?? "").trim(),
  };
  // 成功したら失敗の記録は残さない（次に落ちたときの経過時間が狂うため）
  writeJson(cachePath, { checked_at: nowIso(), latest: info });
  return [info, null];
}

// --------------------------------------------------------------------------
// 受領書
// --------------------------------------------------------------------------

function receiptPath(): string {
  return pathInHome("receipt.json");
}

function loadReceipt(): Json {
  return readJson(receiptPath());
}

/**
 * 人にそのまま渡せるコマンド行を組む。
 *
 * 受領書にスクリプトの絶対パスがあるならそれを使う。相対パスで案内すると、
 * 受け取った側は「どのディレクトリで打つのか」を自分で解く必要がある。
 *
 * v0.1.x の受領書には .py の絶対パスが入っている。そのまま出すと
 * 「もう存在しないファイルを実行してください」と案内することになるので、
 * .py を指していたら同じディレクトリの .ts に読み替える。
 */
function commandLine(script: string | null | undefined, mode: string): string {
  const path = migrateScriptPath(script);
  if (path) return `"${bunPath()}" "${path}" ${mode}`;
  return `bun mentor-update.ts ${mode}`;
}

function migrateScriptPath(script: string | null | undefined): string | null {
  if (!script) return null;
  if (!script.endsWith(".py")) return script;
  const swapped = script.slice(0, -3) + ".ts";
  return existsSync(swapped) ? swapped : scriptPath();
}

/**
 * 配置済みファイルが名乗っているバージョンを読む。
 *
 * 受領書を失っても、置かれたファイル自体がバージョンを持っているので復旧できる。
 * マーカーが無い（= このスクリプトを通さずに手で貼った）場合は null。
 */
function placedVersion(targetPath: string): string | null {
  const text = readText(targetPath);
  if (text === null) return null;
  const found = MARK_BEGIN_RE.exec(text);
  return found ? found[1] : null;
}

// --------------------------------------------------------------------------
// 通知するかどうかの方針
// --------------------------------------------------------------------------

interface NoticeState {
  local: string | null;
  latest: string | null;
  error: string | null;
  last_notified: string | null;
  hook_last_run_hours: number | null;
  script: string | null;
}

/**
 * 新版の状況を見て、セッション冒頭に何を出すかを決める。
 *
 * ここがこの仕組みの性格を決める。「うるさくない」と「見逃さない」は両立しない。
 *
 * state に入るもの:
 *     local                 いま配置されているバージョン（例 "1.0.0"）。不明なら null
 *     latest                最新バージョン。取得できなかったなら null
 *     error                 取得に失敗した理由の文字列。成功していれば null
 *     last_notified         この端末に前回通知したバージョン。未通知なら null
 *     hook_last_run_hours   hook が最後に動いてから何時間か。初回なら null
 *     script                受領書に記録したスクリプトの絶対パス。無ければ null
 *
 * 戻り値:
 *     セッション冒頭に差し込む文字列。何も出さないなら null を返す。
 *
 * 採用した方針:
 *     新版の告知は、その版について一度だけ。ただし3日以上あいだが空いた起動では、
 *     前回を見逃している可能性があるので出し直す。
 *     取得の失敗は毎回、理由つきで出す（切り分けができないと直せないため）。
 */
export function decideNotice(state: NoticeState): string | null {
  // --- ここから下を書き換える ---
  // 失敗は毎回出す。理由まで出さないと、DNS断・レート制限・リリース未公開の
  // どれなのかが切り分けられず、デバッグの役に立たない。
  if (state.latest === null) {
    return `学習メンターの更新確認に失敗しました（${state.error || "理由不明"}）`;
  }

  // 受領書が読めない = 更新できない状態。黙っていると誰も気づかない。
  if (!state.local) {
    return `学習メンターの受領書が読めません。${commandLine(state.script, "--check")} で確認してください。`;
  }

  if (!isNewer(state.latest, state.local)) return null;

  // 一度伝えた版は繰り返さない。ただし3日以上あいだが空いたら、
  // 前回の通知を見逃している可能性があるので出し直す。
  const alreadyTold = state.last_notified === state.latest;
  const usedRecently = state.hook_last_run_hours !== null && state.hook_last_run_hours < 72;
  if (alreadyTold && usedRecently) return null;

  // 更新コマンドは絶対パスで出す。ここに URL しか書かないと、受け取った人は
  // まず「スクリプトをどこに置いたか」を思い出すところから始めることになる。
  return `学習メンターの新版 v${state.latest} が出ています（いま v${state.local}）。更新するには ${commandLine(state.script, "--apply")} を実行してください（変更点: ${RELEASES_PAGE}）。`;
  // --- ここまで ---
}

// --------------------------------------------------------------------------
// モード: --hook
// --------------------------------------------------------------------------

/**
 * SessionStart hook から呼ばれる。
 *
 * 絶対に守ること: 何があってもセッションを壊さない。例外を投げない。終了コードは常に 0。
 * ただし「黙って死ぬ」のはこの製品が最も嫌う失敗なので、失敗の記録は必ず残し、
 * --check で人が読めるようにする。その場では静かに、後から見えるように。
 */
async function cmdHook(): Promise<number> {
  const previous = readJson(pathInHome("stamp.json"), {}) ?? {};
  const stamp: Json = {
    ran_at: nowIso(),
    ok: true,
    error: null,
    notified_version: previous.notified_version ?? null,
    runtime: "bun", // v0.1.x（python）から移ったかを --check が見分けるための印
  };
  let notice: string | null = null;

  try {
    const receipt = loadReceipt();
    const [latestInfo, error] = await fetchLatest();
    notice = decideNotice({
      local: receipt?.version ?? null,
      latest: latestInfo ? latestInfo.version : null,
      error,
      last_notified: previous.notified_version ?? null,
      hook_last_run_hours: hoursSince(previous.ran_at),
      script: receipt?.script_path ?? null,
    });
    if (notice && latestInfo) stamp.notified_version = latestInfo.version;
    stamp.error = error;
  } catch (exc) {
    stamp.ok = false;
    stamp.error = exc instanceof Error ? `${exc.name}: ${exc.message}` : String(exc);
  }

  try {
    writeJson(pathInHome("stamp.json"), stamp);
  } catch {
    // スタンプが書けないこと自体は、セッションを止める理由にならない
  }

  if (notice) {
    console.log(
      JSON.stringify({
        hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: notice },
      }),
    );
  }
  return 0;
}

// --------------------------------------------------------------------------
// モード: --check
// --------------------------------------------------------------------------

async function cmdCheck(): Promise<number> {
  const receipt = loadReceipt();
  if (!receipt) {
    console.log(`受領書がありません（${receiptPath()}）`);
    console.log("配置直後に、置いた場所を指定してこれを実行してください:");
    console.log(`  ${commandLine(scriptPath(), "--setup --tool claude-code --target agent:/絶対パス/learn.md")}`);
    return 1;
  }

  const local = receipt.version ?? "不明";
  console.log(`配置済み : v${local}（${receipt.installed_at ?? "日付不明"} に配置）`);
  console.log(`運用     : ${receipt.tool ?? "不明"} / 運用型 ${receipt.pattern ?? "不明"}`);
  console.log("配置先   :");
  for (const target of receipt.targets ?? []) {
    const path = target?.path ?? "";
    const stamped = existsSync(path) ? placedVersion(path) : null;
    let note: string;
    if (!existsSync(path)) note = "★ ファイルが見つかりません";
    else if (stamped === null) note = "★ マーカーがありません（--apply で更新できません）";
    else if (stamped !== local) note = `★ 受領書は v${local} だがファイルは v${stamped}`;
    else note = "OK";
    // 複数リポジトリに配置すると、配置先ごとに別のツールを使っていることがある
    const kind = target?.kind ?? "?";
    const label = target?.tool && target.tool !== "unknown" ? `${target.tool}/${kind}` : kind;
    console.log(`  [${label}] ${path}  ${note}`);
  }

  // hook が本当に動いているか。Codex の対話TUIでは発火しないという報告があり
  // （openai/codex#17532、2026-05-21 時点で open）、しかも失敗してもエラーが出ない。
  // 動いていないことを検出できないと、「更新確認しているつもり」で古いまま使い続ける。
  console.log("");
  const stamp = readJson(pathInHome("stamp.json"));
  if (!stamp) {
    console.log("hook     : ★ 一度も動いていません。hook の設定が効いていない可能性があります");
  } else {
    const age = hoursSince(stamp.ran_at);
    const when = age !== null ? `${age.toFixed(1)} 時間前` : "不明";
    if (!(stamp.ok ?? true)) console.log(`hook     : ★ 最後の実行で失敗 — ${stamp.error}（${when}）`);
    else if (age !== null && age > 24 * 7) console.log(`hook     : ★ ${when} から動いていません。設定が外れた可能性があります`);
    else console.log(`hook     : OK（最後の実行 ${when}）`);
  }

  console.log("");
  const [latestInfo, error] = await fetchLatest(true);
  if (error || !latestInfo) {
    console.log(`最新版   : ★ 確認できませんでした — ${error}`);
    return 1;
  }
  const latest = latestInfo.version;
  if (isNewer(latest, local)) {
    console.log(`最新版   : v${latest} ← 新版が出ています`);
    if (latestInfo.notes) {
      console.log("");
      for (const line of latestInfo.notes.split("\n").slice(0, 10)) console.log("    " + line);
    }
    console.log("");
    console.log(`更新するには: ${commandLine(receipt.script_path ?? scriptPath(), "--apply")}`);
    return 2;
  }
  console.log(`最新版   : v${latest}（最新です）`);
  return 0;
}

// --------------------------------------------------------------------------
// モード: --apply
// --------------------------------------------------------------------------

/** マーカー間の本文を差し替える。マーカーが無ければ [null, 理由] を返す。 */
function replaceBetweenMarkers(text: string, body: string, version: string): [string | null, string | null] {
  const found = MARK_BEGIN_RE.exec(text);
  if (!found) return [null, "開始マーカーがありません"];
  const endAt = text.indexOf(MARK_END, found.index + found[0].length);
  if (endAt === -1) return [null, "終了マーカーがありません"];
  const head = text.slice(0, found.index);
  const tail = text.slice(endAt + MARK_END.length);
  return [head + markBegin(version) + "\n" + body.trim() + "\n" + MARK_END + tail, null];
}

/** リリース zip を丸ごと落とす。中身の取り出しは readZipEntry に任せる。 */
async function downloadZip(assetUrl: string): Promise<[Buffer | null, string | null]> {
  try {
    const response = await fetch(assetUrl, {
      headers: { "User-Agent": "learning-mentor-update" },
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) return [null, `zip を取得できませんでした (HTTP ${response.status})`];
    return [Buffer.from(await response.arrayBuffer()), null];
  } catch (exc) {
    return [null, `zip を取得できませんでした: ${errorText(exc)}`];
  }
}

/** zip から1件をテキストで取り出す。無ければ null。 */
function zipText(zip: Buffer, name: string): string | null {
  try {
    const entry = readZipEntry(zip, name);
    return entry ? entry.toString("utf8") : null;
  } catch {
    return null;
  }
}

// 自分自身の更新対象。配布物のうち、置き場所に実体として置かれるものだけ。
// 文書（README など）は配置先に置かれないので触らない。
const SELF_FILES = ["mentor-update.ts", "check-sync.ts", "VERSION"];

/**
 * スクリプト自身を新版に入れ替える計画を立てる。
 *
 * **なぜ要るか。** v0.1.x → v0.2.0 の移行でこれが無くて困った。--apply が
 * 入れ替えるのは本文だけで、スクリプトは古いまま残る。実行系が変わる更新
 * （Python → Bun）や、hook のコマンド行が変わる更新では、**本文だけ新しくなって
 * 仕組みが古いまま**という状態になり、しかも本人は更新済みだと思っている。
 *
 * 今回の移行そのものは、これでは救えない（救うには v0.1.x 側に要る）。
 * **次に同じことが起きたときのために入れてある。**
 *
 * 戻り値: [path, 旧内容, 新内容] の配列
 */
function planSelfUpdate(zip: Buffer): Array<[string, string, string]> {
  const here = dirname(scriptPath());
  const plans: Array<[string, string, string]> = [];
  for (const name of SELF_FILES) {
    const incoming = zipText(zip, name);
    if (incoming === null) continue; // zip に無いものは触らない
    const path = join(here, name);
    const current = readText(path);
    if (current === null || current === incoming) continue;
    plans.push([path, current, incoming]);
  }
  return plans;
}

async function cmdApply(args: Args): Promise<number> {
  const receipt = loadReceipt();
  if (!receipt) {
    console.log("受領書がありません。先に --setup を実行してください。");
    return 1;
  }

  const [latestInfo, error] = await fetchLatest(true);
  if (error || !latestInfo) {
    console.log(`最新版を確認できませんでした — ${error}`);
    return 1;
  }
  const latest = latestInfo.version;
  const local = receipt.version ?? "0";
  if (!isNewer(latest, local) && !args.force) {
    console.log(`すでに最新です（v${local}）。貼り直すなら --force。`);
    return 0;
  }
  if (!latestInfo.asset) {
    console.log(`リリース v${latest} に zip アセットが付いていません: ${latestInfo.url}`);
    return 1;
  }

  const [zip, downloadError] = await downloadZip(latestInfo.asset);
  if (downloadError || zip === null) {
    console.log(downloadError);
    return 1;
  }
  const body = zipText(zip, "learning-mentor-prompt.md");
  if (body === null) {
    console.log("zip の中に learning-mentor-prompt.md がありません");
    return 1;
  }

  // まず全部の差分を見せる。書き換えるのは了解を得てから。
  const plans: Array<[string, string, string]> = [];
  for (const target of receipt.targets ?? []) {
    const path = target?.path ?? "";
    const original = readText(path);
    if (original === null) {
      console.log(`SKIP ${path} （見つかりません）`);
      continue;
    }
    const [updated, markerError] = replaceBetweenMarkers(original, body, latest);
    if (markerError || updated === null) {
      console.log(`SKIP ${path} （${markerError}）`);
      continue;
    }
    if (updated === original) {
      console.log(`変更なし ${path}`);
      continue;
    }
    plans.push([path, original, updated]);
  }

  const selfPlans = planSelfUpdate(zip);

  if (!plans.length && !selfPlans.length) {
    console.log("書き換える対象がありませんでした。");
    return 1;
  }

  // 本文が全面的に書き換わると差分は数百行になり、流れるだけで判断の役に立たない。
  // 既定は「どこが何行変わるか」の要約。中身を見たいときだけ --diff。
  console.log("");
  console.log(`v${local} → v${latest}`);
  if (latestInfo.notes) {
    console.log("");
    for (const line of latestInfo.notes.split("\n").slice(0, 15)) console.log("  " + line);
  }
  console.log("");
  for (const [path, original, updated] of plans) {
    const diff = unifiedDiff(original.split("\n"), updated.split("\n"), `v${local}`, `v${latest}`, 1);
    const added = diff.filter((l) => l.startsWith("+") && !l.startsWith("+++")).length;
    const removed = diff.filter((l) => l.startsWith("-") && !l.startsWith("---")).length;
    console.log(`  ${path}`);
    console.log(`      +${added} 行 / -${removed} 行（マーカーの外は変えません）`);
    if (args.diff) for (const line of diff) console.log("      " + line);
  }

  // スクリプト自身の入れ替えは、本文の貼り直しとは意味が違う。同じ確認に混ぜるが、
  // 別枠で見せる ── 「何が置き換わるのか」を取り違えたまま y と答えさせないため。
  if (selfPlans.length) {
    console.log("");
    console.log("  このスクリプト自身も新版に入れ替えます:");
    for (const [path, original, updated] of selfPlans) {
      const diff = unifiedDiff(original.split("\n"), updated.split("\n"), `v${local}`, `v${latest}`, 1);
      const added = diff.filter((l) => l.startsWith("+") && !l.startsWith("+++")).length;
      const removed = diff.filter((l) => l.startsWith("-") && !l.startsWith("---")).length;
      console.log(`      ${path}  +${added} 行 / -${removed} 行`);
    }
  }

  if (!args.diff) {
    console.log("");
    console.log("  中身を確認するなら --diff を付けて実行してください。");
  }
  console.log("");
  if (!args.yes && !confirm(`上記を v${latest} に更新します。よろしいですか [y/N]: `)) {
    console.log("中止しました。");
    return 1;
  }

  for (const [path, original, updated] of plans) {
    writeFileSync(path + ".bak", original, "utf8");
    writeFileSync(path, updated, "utf8");
    console.log(`更新 ${path} （元は ${basename(path)}.bak）`);
  }

  // 実行中のファイルを上書きすることになるが、Bun は起動時に読み切っているので
  // この実行は最後まで古いコードのまま走る。次回の起動から新版になる。
  let selfUpdated = false;
  for (const [path, original, updated] of selfPlans) {
    try {
      writeFileSync(path + ".bak", original, "utf8");
      writeFileSync(path, updated, "utf8");
      console.log(`更新 ${path} （元は ${basename(path)}.bak）`);
      selfUpdated = true;
    } catch (exc) {
      // ここで落ちても本文の貼り直しは済んでいる。黙らずに、次の一手を出す。
      console.log(`★ ${path} を入れ替えられませんでした — ${errorText(exc)}`);
      console.log(`   zip を落とし直して手で置き換えてください: ${latestInfo.url}`);
    }
  }

  receipt.version = latest;
  receipt.updated_at = nowIso();
  receipt.script_path = scriptPath();
  writeJson(receiptPath(), receipt);
  console.log("");
  console.log(`v${latest} に更新しました。`);

  // スクリプトを入れ替えたら hook の登録も見直す。起動コマンドが変わる更新
  // （実行系の変更・ファイル名の変更）で、hook だけが古いまま残ると、
  // 更新のお知らせがエラーも出さずに止まる。冪等なので、変化が無ければ何も書かない。
  // --no-hook で入れなかった人には生やさない。
  if (selfUpdated && receipt.hook_installed !== false) {
    for (const line of installHook(receipt.tool).lines) console.log(line);
  }

  // 更新は本文を丸ごと入れ替える。配置が効いているかの確認は、配置直後と
  // まったく同じ理由で毎回要る。案内を別ファイルに送らず、その場に出す。
  printVerification();
  return 0;
}

// --------------------------------------------------------------------------
// hook の設置
// --------------------------------------------------------------------------

// ツールごとの差はこの表だけに閉じる。設定ファイルの場所・matcher・
// hook エントリに載る追加フィールドの3点しか違わない。
const HOOK_TARGETS: Record<string, { settings: string[]; matcher: string; fields: Json }> = {
  "claude-code": {
    settings: ["~", ".claude", "settings.json"],
    matcher: "startup",
    fields: { timeout: 10 },
  },
  codex: {
    settings: ["~", ".codex", "hooks.json"],
    matcher: "startup|resume",
    fields: {
      statusMessage: "学習メンターの更新を確認しています",
      additionalContextLimit: 2000,
    },
  },
};

function scriptPath(): string {
  return resolve(import.meta.path ?? process.argv[1]);
}

/**
 * hook から呼ばせる bun の絶対パス。
 *
 * `bun` ではなく process.execPath を書く。--setup を実行できた実行系は確実に
 * 存在するが、`bun` が PATH にある保証はない（Windows では特に多い）。
 * ここを間違えても hook は黙って何もしないので、推測できる箇所は推測しない。
 */
function bunPath(): string {
  return process.execPath;
}

function hookCommand(): string {
  return `"${bunPath()}" "${scriptPath()}" --hook`;
}

function hookEntry(tool: string): Json {
  const spec = HOOK_TARGETS[tool];
  return {
    matcher: spec.matcher,
    hooks: [{ type: "command", command: hookCommand(), ...spec.fields }],
  };
}

function normPath(text: string): string {
  return text.replace(/\\/g, "/").toLowerCase();
}

/**
 * この仕組みが置いた hook エントリか。どのリポジトリのコピーでも真になる。
 *
 * スクリプトのパスは見ない。学習メンターは複数のリポジトリに配置されうるが、
 * **更新通知は端末に1本あれば足りる。**「新版が出た」という事実はリポジトリごとに
 * 変わらないし、通知の重複はどのみち stamp.json の既通知判定で潰れる（2本目は
 * 何も出さない）。だからどのコピーが登録されていても「うちのもの」と見なし、
 * 最新の1本に集約する。
 *
 * **拡張子も見ない。** v0.1.x は Python 版（`mentor-update.py`）を登録している。
 * ここで .ts しか拾わないと、**古い python 起動の1本が外れずに残り、bun の1本と
 * 二重になる。** しかも .py を消した時点で古いほうは黙って死ぬので、
 * 「hook が2本あるのに1本も動いていない」状態を誰も検出できない。
 * 両方を「うちのもの」と見なすことで、v0.1.x からの移行は --setup を通すだけで済む。
 */
function isMentorEntry(entry: Json): boolean {
  const command = String(entry?.command ?? "");
  return /mentor-update\.(ts|py)/.test(command) && command.includes("--hook");
}

/**
 * SessionStart の配列を、メンターの hook がちょうど1本ある状態にする。
 *
 * **メンター以外のエントリには触らない。** メンターのエントリは、どのリポジトリの
 * コピーを指していても取り除き、最後に desired を1つだけ足す。
 *
 * グループ単位ではなくエントリ単位で外すのが要点。1つのグループにメンターの
 * hook と他人の hook が同居している場合、グループごと消すと無関係な設定まで
 * 巻き添えになる。
 *
 * 戻り値: [新しい配列, 取り除いたメンターエントリの数]
 */
function consolidateSessionStart(groups: Json[], desired: Json): [Json[], number] {
  const keptGroups: Json[] = [];
  let removed = 0;
  for (const group of groups ?? []) {
    const entries = group?.hooks;
    if (!Array.isArray(entries)) {
      keptGroups.push(group); // 想定外の形は解釈せず、そのまま残す
      continue;
    }
    const kept = entries.filter((entry: Json) => !isMentorEntry(entry));
    removed += entries.length - kept.length;
    if (kept.length) keptGroups.push({ ...group, hooks: kept });
  }
  return [[...keptGroups, desired], removed];
}

function settingsPathFor(tool: string): string {
  return expandUser(join(...HOOK_TARGETS[tool].settings));
}

function backupAndWrite(path: string, text: string): void {
  const original = readText(path);
  if (original !== null) writeFileSync(path + ".bak", original, "utf8");
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text, "utf8");
}

/**
 * SessionStart hook を設定ファイルに書く。メンターの hook は常に1本に保つ。
 *
 * v0.1.1 までは「既存の SessionStart 設定があれば触らず報告」だった。実地で
 * 破綻した。**2つ目のリポジトリに配置すると、1つ目で自分が置いた hook を
 * 「他人の設定」と見なして拒否する。** リポジトリを増やすたびに手作業が要る。
 *
 * 方針を次のように変えた。
 *
 *     メンターの hook（どのリポジトリのコピーでも）→ 取り除いて、最新の1本に置き換える
 *     メンター以外の SessionStart 設定          → 一切触らず、自分のエントリを足す
 *
 * 「触らず報告」を守るのはメンター以外の設定に対してだけにした。**自分が置いた
 * ものを他人のものとして扱うのは、慎重さではなく取り違えでしかない。**
 *
 * 集約する（追加しない）のは、通知が端末単位の情報だから。2本目の hook は
 * stamp.json の既通知判定で黙るので、増やしても仕事がない。
 *
 * 戻り値の status は "installed" / "updated" / "already" / "skipped" / "failed"
 */
function installHook(tool: string | undefined): { status: string; lines: string[] } {
  if (!tool || !(tool in HOOK_TARGETS)) {
    return {
      status: "skipped",
      lines: [
        `hook     : ★ 設置していません（--tool ${tool || "未指定"} は自動設置に未対応）`,
        `           対応しているのは ${Object.keys(HOOK_TARGETS).sort().join(" / ")} です。`,
        "           手で入れる場合は hooks/README.md を見てください。",
        `           コマンドはこれです: ${hookCommand()}`,
      ],
    };
  }

  const path = settingsPathFor(tool);
  const raw = readText(path);
  let settings = readJson(path, null);
  if (settings === null && raw !== null) {
    return {
      status: "failed",
      lines: [
        `hook     : ★ ${path} を読めませんでした（JSON として壊れている可能性）`,
        "           直してから --setup をもう一度実行してください。",
      ],
    };
  }
  settings = settings && typeof settings === "object" ? settings : {};

  const hooks = settings.hooks && typeof settings.hooks === "object" ? settings.hooks : {};
  const existing = Array.isArray(hooks.SessionStart) ? hooks.SessionStart : [];

  const [updated, removed] = consolidateSessionStart(existing, hookEntry(tool));
  hooks.SessionStart = updated;
  settings.hooks = hooks;

  const text = JSON.stringify(settings, null, 2) + "\n";
  if (raw === text) {
    return { status: "already", lines: [`hook     : 設置済み（${path}）`, ...ensureCodexFeature(tool)] };
  }

  try {
    backupAndWrite(path, text);
  } catch (exc) {
    return { status: "failed", lines: [`hook     : ★ ${path} に書けませんでした — ${errorText(exc)}`] };
  }

  const others = updated
    .slice(0, -1)
    .reduce((n: number, g: Json) => n + (Array.isArray(g?.hooks) ? g.hooks.length : 0), 0);
  const lines = removed
    ? [
        `hook     : 更新しました（${path}）`,
        `           既にあった学習メンターの登録 ${removed} 件を、このコピーの1本にまとめました`,
      ]
    : [`hook     : 設置しました（${path}）`];
  if (others) lines.push(`           ほかの SessionStart 設定 ${others} 件はそのまま残しています`);
  lines.push(...ensureCodexFeature(tool));
  return { status: removed ? "updated" : "installed", lines };
}


function ensureCodexFeature(tool: string): string[] {
  if (tool !== "codex") return [];
  const path = expandUser(join("~", ".codex", "config.toml"));
  const text = readText(path);

  if (text === null) {
    try {
      backupAndWrite(path, "[features]\ncodex_hooks = true\n");
    } catch (exc) {
      return [`           ★ ${path} を作れませんでした — ${errorText(exc)}`];
    }
    return [`           ${path} に [features] codex_hooks = true を書きました`];
  }

  if (/^\s*codex_hooks\s*=\s*true/m.test(text)) return ["           config.toml の codex_hooks は有効です"];

  if (/^\s*\[features\]/m.test(text)) {
    return [
      `           ★ ${path} に既に [features] があります。触っていません。`,
      "           そのテーブルに codex_hooks = true を手で足してください。",
    ];
  }

  try {
    backupAndWrite(path, text.replace(/\n+$/, "") + "\n\n[features]\ncodex_hooks = true\n");
  } catch (exc) {
    return [`           ★ ${path} に書けませんでした — ${errorText(exc)}`];
  }
  return [`           ${path} に [features] codex_hooks = true を足しました（元は .bak）`];
}


// --------------------------------------------------------------------------
// 個人の配置物をチームリポジトリに巻き込まない
// --------------------------------------------------------------------------
//
// なぜ要るか:
//   配置先はAIが環境ごとに判断する（learning-mentor-setup.md）。学習会の参加者が
//   普段の開発リポジトリに【B】呼び出し型で配置すると、置き場所はツール・OS・
//   本人の判断で人によって変わる。.gitignore に入れておかないと、次の
//   `git add` や `git status` に個人の配置物が混ざり、「AIメンター導入」だけの
//   PR が参加者の数だけ飛んでくる。チーム開発では無意味な差分でしかない。

const GITIGNORE_MARK_BEGIN = "# learning-mentor:gitignore begin";
const GITIGNORE_MARK_END = "# learning-mentor:gitignore end";

/** path から上へ辿って .git のあるディレクトリを探す。無ければ null。 */
function findRepoRoot(path: string): string | null {
  let current = dirname(resolve(path));
  for (;;) {
    if (existsSync(join(current, ".git"))) return current;
    const parent = dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

/**
 * .gitignore に書く1行。リポジトリ直下からの相対パスで、先頭に / を付けて
 * 同名ファイルが別の場所にあっても巻き込まないようにする。
 */
function gitignoreEntry(repoRoot: string, targetPath: string): string {
  return "/" + relative(repoRoot, resolve(targetPath)).replace(/\\/g, "/");
}

/** entry そのもの、または entry を含む親ディレクトリの除外が既にあるか。 */
function alreadyIgnored(existingLines: string[], entry: string): boolean {
  const stripped = new Set(existingLines.map((line) => line.trim().replace(/^\/+/, "")));
  const bare = entry.replace(/^\/+/, "");
  if (stripped.has(bare)) return true;
  const parts = bare.split("/");
  for (let i = 1; i < parts.length; i++) {
    if (stripped.has(parts.slice(0, i).join("/") + "/")) return true;
  }
  return false;
}

/**
 * learning-mentor 専用ブロックを .gitignore に足す（無ければ作る）。
 *
 * 既存のブロックがあれば中身を読み取って合流させる（再実行しても重複しない）。
 * 変更が無かった場合は書き込まない。
 * 戻り値: [path, 書き込んだかどうか]
 */
function updateGitignore(repoRoot: string, entries: string[]): [string, boolean] {
  const path = join(repoRoot, ".gitignore");
  const text = readText(path) ?? "";

  const lines = text.split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop(); // splitlines 相当
  const beginAt = lines.findIndex((l) => l.trim() === GITIGNORE_MARK_BEGIN);
  const endAt = lines.findIndex((l) => l.trim() === GITIGNORE_MARK_END);

  let before: string[];
  let blockBody: string[];
  let after: string[];
  if (beginAt !== -1 && endAt !== -1 && endAt > beginAt) {
    before = lines.slice(0, beginAt);
    blockBody = lines.slice(beginAt + 1, endAt);
    after = lines.slice(endAt + 1);
  } else {
    before = lines;
    blockBody = [];
    after = [];
  }

  const existingEntries = blockBody.filter((l) => l.trim() && !l.trim().startsWith("#"));
  const merged = [...existingEntries];
  for (const entry of entries) {
    if (!merged.includes(entry) && !alreadyIgnored([...before, ...merged, ...after], entry)) {
      merged.push(entry);
    }
  }

  if (!merged.length) return [path, false];
  if (beginAt !== -1 && merged.length === existingEntries.length
      && merged.every((e, i) => e === existingEntries[i])) {
    return [path, false];
  }

  const block = [
    GITIGNORE_MARK_BEGIN,
    "# 学習メンターの個人導入物。配置先は人によって違うので追跡しない",
    ...merged,
    GITIGNORE_MARK_END,
  ];

  let newLines = [...before, ...(before.length && before[before.length - 1].trim() !== "" ? [""] : []), ...block];
  if (after.length) newLines = [...newLines, "", ...after];

  const newText = newLines.join("\n").replace(/\n+$/, "") + "\n";
  if (newText === text) return [path, false];

  writeFileSync(path, newText, "utf8");
  return [path, true];
}

/** マーカーで囲まれた本文を取り除いた残り。embedded 判定に使う。 */
function contentOutsideMarkers(text: string): string {
  const found = MARK_BEGIN_RE.exec(text);
  if (!found) return text;
  const endAt = text.indexOf(MARK_END, found.index + found[0].length);
  if (endAt === -1) return text;
  return text.slice(0, found.index) + text.slice(endAt + MARK_END.length);
}

/**
 * path が既に git 管理下にあるか。無ければ false（git が無い環境でも false）。
 *
 * Python 版の subprocess.run に相当。Bun.spawnSync は git が PATH に無いと
 * 例外を投げるので、握って false にする ── ここで落ちると --setup 全体が
 * 止まってしまい、git の有無という本題と無関係な理由で導入が失敗する。
 */
function isTrackedByGit(repoRoot: string, path: string): boolean {
  const rel = relative(repoRoot, resolve(path)).replace(/\\/g, "/");
  try {
    const result = Bun.spawnSync({
      cmd: ["git", "ls-files", "--error-unmatch", "--", rel],
      cwd: repoRoot,
      stdout: "ignore",
      stderr: "ignore",
    });
    return result.exitCode === 0;
  } catch {
    return false;
  }
}

/**
 * 配置先を調べ、リポジトリ内のものは .gitignore に足す。表示行のリストを返す。
 *
 * - agent（frontmatter 付きの単独ファイル）は無条件で対象にする
 * - embedded（CLAUDE.md / AGENTS.md など）は、マーカーの外に本文が無い
 *   （＝このファイルが実質メンター専用ファイルとして新規に作られた）場合だけ
 *   対象にする。既存の記述と同居している場合は自動で除外できないので警告に回す
 */
function protectTargetsFromGit(targets: Json[]): string[] {
  const lines: string[] = [];
  const byRepo = new Map<string, string[]>();
  const noRepo: string[] = [];
  const warnEmbedded: string[] = [];
  const trackedAlready: Array<[string, string]> = [];

  for (const target of targets) {
    const path = target.path;
    if (target.kind === "embedded") {
      const text = readText(path);
      const remainder = text === null ? null : contentOutsideMarkers(text);
      if (remainder === null || remainder.trim()) {
        warnEmbedded.push(path);
        continue;
      }
    }

    const root = findRepoRoot(path);
    if (root === null) {
      noRepo.push(path);
      continue;
    }
    if (!byRepo.has(root)) byRepo.set(root, []);
    byRepo.get(root)!.push(path);
    if (isTrackedByGit(root, path)) trackedAlready.push([root, path]);
  }

  for (const [root, paths] of byRepo) {
    const [gpath, changed] = updateGitignore(root, paths.map((p) => gitignoreEntry(root, p)));
    lines.push(changed ? `gitignore: ${gpath} に追記しました` : `gitignore: ${gpath} は既に対応済みです`);
  }

  for (const [root, path] of trackedAlready) {
    const rel = relative(root, path).replace(/\\/g, "/");
    lines.push(
      `gitignore: ★ ${path} は既に git 管理下です。` +
        `\`git rm --cached -- "${rel}"\` で追跡を外してください`,
    );
  }

  for (const path of warnEmbedded) {
    lines.push(`gitignore: ★ ${path} は既存ファイルへの同居配置（embedded）のため、自動では除外できません`);
    lines.push(
      "           他の記述と同じファイルにあるので、ファイルごと無視するとチームの記述も消えます。" +
        "共有リポジトリなら【A】の分離運用か、個人用ファイルへの分離を検討してください。",
    );
  }

  for (const path of noRepo) {
    lines.push(`gitignore: ${path} は git リポジトリの外なので対象外です`);
  }

  return lines;
}

// --------------------------------------------------------------------------
// モード: --setup
// --------------------------------------------------------------------------

function readVersionFile(): string | null {
  const text = readText(join(dirname(scriptPath()), "VERSION"));
  return text === null ? null : text.trim();
}

const VERIFY_QUESTION = "使えるツールの名前を、箇条書きで全部挙げてください。";

/**
 * 配置が効いているかを人が確かめる手順を、その場に出す。
 *
 * ここだけは自動化できない。配置が効いているかは、そのセッションが実際に
 * 何を持っているかにしか現れず、外から観測する手段がないため。
 * README と hooks/README.md を往復させないよう、必要なものは全部ここに出す。
 */
function printVerification(): void {
  console.log("");
  console.log("─".repeat(60));
  console.log("★ 最後に、動作確認をしてください（ここを飛ばさないでください）");
  console.log("");
  console.log("  置き場所を間違えても、エラーは出ません。黙って無視されるだけです。");
  console.log("  メンターを起動して、次の質問をそのまま貼ってください。");
  console.log("");
  console.log(`      ${VERIFY_QUESTION}`);
  console.log("");
  console.log("  読み取り系だけ（Read / Grep / Glob など）  → 成功");
  console.log("  Edit / Write やシェル実行が入っている       → 失敗。置き場所か起動方法が違います");
  console.log("");
  console.log("  「書き換えて」と頼んで断られたかどうかでは判定できません。ツールが無くても");
  console.log("  AIは「〜という設定なので、できません」と説明するだけで、区別がつかないためです。");
  console.log("");
  console.log("  hook が本当に動いたかは、セッションを1回起動したあとに分かります:");
  console.log(`      ${commandLine(scriptPath(), "--check")}`);
  console.log("─".repeat(60));
}

/**
 * 配置先をパスで合流する。同じ配置先なら上書き、違う配置先なら追加。
 *
 * 受領書は端末に1つしかない。v0.1.1 まではここを丸ごと置き換えていたため、
 * **2つ目のリポジトリに配置すると1つ目の配置先が受領書から消えていた。**
 * 消えた配置先は --apply の対象から外れ、二度と更新されない。しかも
 * エラーは出ない ── この製品が最も嫌う壊れ方だった。
 *
 * 戻り値: [合流後のリスト, 追加された数, 更新された数]
 */
function mergeTargets(existing: Json[] | undefined, incoming: Json[]): [Json[], number, number] {
  const merged: Json[] = (existing ?? [])
    .filter((t) => t && typeof t === "object")
    .map((t) => ({ ...t }));
  // Windows のパスは大文字小文字を区別しないので、そろえてから突き合わせる
  const key = (p: string) => (process.platform === "win32" ? String(p ?? "").toLowerCase() : String(p ?? ""));
  const index = new Map<string, number>(merged.map((t, i) => [key(t.path), i]));

  let added = 0;
  let updated = 0;
  for (const target of incoming) {
    const k = key(target.path);
    const at = index.get(k);
    if (at !== undefined) {
      merged[at] = target;
      updated++;
    } else {
      index.set(k, merged.length);
      merged.push(target);
      added++;
    }
  }
  return [merged, added, updated];
}

/**
 * 配置直後に1回実行する。受領書・hook・.gitignore・動作確認をまとめて片づける。
 *
 * setup.md の配置手順の最後で、AI にこれを実行させる想定。
 */
function cmdSetup(args: Args): number {
  const version = args.version || readVersionFile() || "0.0.0";
  const targets: Json[] = [];
  for (const spec of args.target) {
    // 種別は既知の語だけに限る。素朴に ":" で割ると、Windows の
    // ドライブレター（C:/Users/...）を区切りと誤認する。
    const found = TARGET_KIND_RE.exec(spec);
    const kind = found ? found[1] : "agent";
    const path = found ? found[2] : spec;
    targets.push({
      kind,
      path: resolve(expandUser(path)),
      // 配置先ごとにツールを持たせる。複数リポジトリに配置すると、
      // リポジトリごとに別のツールを使っていることがある
      tool: args.tool || "unknown",
      registered_at: nowIso(),
    });
  }

  const previous = loadReceipt() ?? {};
  const [merged, added, refreshed] = mergeTargets(previous.targets, targets);

  writeJson(receiptPath(), {
    version,
    installed_at: previous.installed_at || nowIso(),
    updated_at: nowIso(),
    tool: args.tool || previous.tool || "unknown",
    pattern: args.pattern || previous.pattern || "unknown",
    source: `https://github.com/${REPO}`,
    // 更新のたびにスクリプトを探させないため、自分の居場所を残す。
    // hook の通知文も --check の案内も、ここを読んで絶対パスで出す。
    script_path: scriptPath(),
    runtime: "bun",
    // --no-hook で入れなかったことを覚えておく。--apply が更新のついでに
    // hook を生やすと、要らないと言った人の設定を黙って変えることになる。
    hook_installed: !args.noHook,
    targets: merged,
  });

  console.log(`受領書   : ${receiptPath()}`);
  if (added && merged.length > added) {
    console.log(`  配置先 ${merged.length} 件（今回 ${added} 件を追加。既存の登録は残しています）`);
  } else if (refreshed && merged.length > refreshed) {
    console.log(`  配置先 ${merged.length} 件（今回 ${refreshed} 件を更新）`);
  }
  for (const target of merged) {
    const stamped = placedVersion(target.path);
    if (!existsSync(target.path)) {
      console.log(`  ★ ${target.path} が見つかりません（--apply の対象から外れています）`);
    } else if (stamped === null) {
      console.log(`  ★ ${target.path} にマーカーがありません。本文を次の形で囲んでください:`);
      console.log(`      ${markBegin(version)}`);
      console.log("      （本文）");
      console.log(`      ${MARK_END}`);
    } else {
      console.log(`  OK ${target.path} （v${stamped}）`);
    }
  }

  // .gitignore の面倒を見るのは今回指定された配置先だけ。既に登録済みの
  // 配置先は前回の --setup で処理済みだし、別リポジトリを勝手に触らない
  for (const line of protectTargetsFromGit(targets)) console.log(line);

  if (args.noHook) {
    console.log("hook     : 設置していません（--no-hook）");
  } else {
    for (const line of installHook(args.tool).lines) console.log(line);
  }

  printVerification();
  return 0;
}

// --------------------------------------------------------------------------
// 引数
// --------------------------------------------------------------------------

interface Args {
  hook: boolean;
  check: boolean;
  apply: boolean;
  setup: boolean;
  target: string[];
  tool: string | undefined;
  pattern: string | undefined;
  noHook: boolean;
  version: string | undefined;
  diff: boolean;
  force: boolean;
  yes: boolean;
}

const USAGE = `学習メンターの配置を最新版に追従させる

使い方: bun mentor-update.ts [モード] [オプション]

モード（省略時は --check）
  --hook                SessionStart hook から呼ぶ
  --check               新版の有無と hook の状態を表示（既定）
  --apply               配置済みのコピーを最新版に貼り直す
  --setup, --register   配置直後に1回。受領書・hook・動作確認をまとめて行う

--setup 用
  --target KIND:PATH    agent:/path/to/learn.md の形で複数指定できる
  --tool NAME           claude-code / codex。hook の置き場所を決める
  --pattern A|B         A（常時適用型）/ B（呼び出し型）
  --no-hook             更新のお知らせ（SessionStart hook）を設置しない
  --version VER         省略時は VERSION ファイルを読む

--apply 用
  --diff                差分を全文表示する
  --force               同一版でも貼り直す
  --yes, -y             確認を省く`;

/**
 * 引数を読む。argparse の代わりなので、受け付ける形も終了コードも Python 版と同じにしてある。
 * 知らないオプションは黙って捨てず、使い方を出して 1 で落とす（打ち間違いに気づけるように）。
 * --help は「使い方を聞かれた」だけなので 0 で終わる ── ここを 1 にすると、
 * 導入手順をスクリプトで包んだときに、成功しているのに失敗として扱われる。
 */
function parseArgs(argv: string[]): Args | "help" | null {
  const args: Args = {
    hook: false,
    check: false,
    apply: false,
    setup: false,
    target: [],
    tool: undefined,
    pattern: undefined,
    noHook: false,
    version: undefined,
    diff: false,
    force: false,
    yes: false,
  };

  const valueOf = (index: number, name: string): string | null => {
    const next = argv[index + 1];
    if (next === undefined || next.startsWith("--")) {
      console.log(`${name} には値が要ります。`);
      return null;
    }
    return next;
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    switch (arg) {
      case "--hook": args.hook = true; break;
      case "--check": args.check = true; break;
      case "--apply": args.apply = true; break;
      case "--setup":
      case "--register": args.setup = true; break;
      case "--no-hook": args.noHook = true; break;
      case "--diff": args.diff = true; break;
      case "--force": args.force = true; break;
      case "--yes":
      case "-y": args.yes = true; break;
      case "--help":
      case "-h": console.log(USAGE); return "help";
      case "--target": {
        const value = valueOf(i, "--target");
        if (value === null) return null;
        args.target.push(value);
        i++;
        break;
      }
      case "--tool": {
        const value = valueOf(i, "--tool");
        if (value === null) return null;
        args.tool = value;
        i++;
        break;
      }
      case "--pattern": {
        const value = valueOf(i, "--pattern");
        if (value === null) return null;
        args.pattern = value;
        i++;
        break;
      }
      case "--version": {
        const value = valueOf(i, "--version");
        if (value === null) return null;
        args.version = value;
        i++;
        break;
      }
      default:
        console.log(`知らないオプションです: ${arg}`);
        console.log("");
        console.log(USAGE);
        return null;
    }
  }
  return args;
}

async function main(argv: string[]): Promise<number> {
  const args = parseArgs(argv);
  if (args === "help") return 0;
  if (args === null) return 1;
  if (args.hook) return cmdHook();
  if (args.setup) return cmdSetup(args);
  if (args.apply) return cmdApply(args);
  return cmdCheck();
}

// import.meta.main は「直接実行されたか」。check-sync.ts が差分の部品だけを
// import したときに、こちらの main が動き出さないようにするための番。
if (import.meta.main) {
  process.exitCode = await main(process.argv.slice(2));
}
