#!/usr/bin/env bun
/**
 * 役割定義の本文が、コピー先とずれていないか確認する。
 *
 * `learning-mentor-prompt.md` が唯一のソース。本文はほかに3箇所へコピーされている。
 *
 *   1. learning-mentor-setup.md の「--- ここから下が本文 ---」以降（配置用プロンプトに埋め込む用）
 *   2. .claude/agents/learn.md の frontmatter 以降（`claude --agent learn` 用の参照実装）
 *   3. experiments/fixture/.claude/agents/learn.md（検証ハーネスが被験体として起動する実体）
 *
 * 本体を更新したあと、このスクリプトを実行してコピー先の貼り直し漏れを検出する。
 *
 * 使い方:
 *     bun check-sync.ts
 *
 * 終了コード: 一致していれば 0、ずれていれば 1
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

// 差分の見せ方は mentor-update.ts と揃える。配布物を増やさないため共通部品用の
// ファイルは作らず、必ず同梱される側から借りている（release.yml は両方を zip に入れる）。
import { unifiedDiff } from "./mentor-update.ts";

const ROOT = dirname(resolve(import.meta.path ?? process.argv[1]));
const SOURCE = "learning-mentor-prompt.md";

const SETUP = "learning-mentor-setup.md";
const SETUP_MARKER = "--- ここから下が本文 ---";

const AGENT = join(".claude", "agents", "learn.md");

// 検証ハーネスが fixture 内に置くコピー。fixture 自体は git 管理外だが、
// 本体を更新したときの貼り直し漏れはここでも起きる。しかもここでずれると
// 「途中でメンターのプロンプトが変わった run」という最悪の事故になるため、
// experiments/run.py は起動時にこの検査を通してから実行する。
const FIXTURE_AGENT = join("experiments", "fixture", ".claude", "agents", "learn.md");

// 配布物の中で本文を囲む更新用マーカー。詳しくは mentor-update.ts と hooks/README.md。
const MARKER_RE = /^\s*<!--\s*learning-mentor:(begin\s+v[0-9A-Za-z.\-]+|end)\s*-->\s*$/;

function read(relpath: string): string | null {
  const path = join(ROOT, relpath);
  if (!existsSync(path)) return null;
  return readFileSync(path, "utf8");
}

/**
 * 比較用に正規化する。
 *
 * 改行コードの差（CRLF/LF）と行末の空白は、内容のずれではないので吸収する。
 * 前後の空行も、切り出し方の都合で増減するため落とす。
 *
 * 更新用マーカー（<!-- learning-mentor:begin vX.Y.Z --> / :end）も落とす。
 * これは本文の「内容」ではなく「境界」で、mentor-update.ts が貼り直す範囲を
 * 示すために配布物側にだけ入る。行末空白と同じく、吸収すべき差。
 */
function normalize(text: string): string[] {
  const lines = text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.replace(/\s+$/, ""))
    .filter((line) => !MARKER_RE.test(line));
  while (lines.length && !lines[0]) lines.shift();
  while (lines.length && !lines[lines.length - 1]) lines.pop();
  return lines;
}

type Extracted = [string | null, string | null];

/** 配置用プロンプトのコードフェンス内に埋め込まれた本文を取り出す。 */
function extractFromSetup(text: string): Extracted {
  const at = text.indexOf(SETUP_MARKER);
  if (at === -1) return [null, `「${SETUP_MARKER}」の行が見つかりません`];
  const after = text.slice(at + SETUP_MARKER.length);
  // 本文は貼り付けプロンプトのコードフェンス内にあるので、次に現れる ``` が終端
  const end = /^```[ \t]*$/m.exec(after);
  if (!end) return [null, "本文を閉じるコードフェンス (```) が見つかりません"];
  return [after.slice(0, end.index), null];
}

/** エージェント定義の frontmatter を取り除いて本文を取り出す。 */
function extractFromAgent(text: string): Extracted {
  if (!text.startsWith("---")) return [null, "frontmatter (先頭の ---) がありません"];
  // Python の re.split(r"^---\s*$", text, maxsplit=2) と同じ切り方。
  // 3つ目以降の区切り線は本文の一部として残す。
  const separator = /^---[ \t]*$/gm;
  const cuts: Array<[number, number]> = [];
  for (const found of text.matchAll(separator)) {
    cuts.push([found.index!, found.index! + found[0].length]);
    if (cuts.length === 2) break;
  }
  if (cuts.length < 2) return [null, "frontmatter が閉じられていません"];
  return [text.slice(cuts[1][1]), null];
}

function reportDiff(label: string, expected: string[], actual: string[]): void {
  const diff = unifiedDiff(expected, actual, SOURCE, label, 1);
  console.log("  ずれている行:");
  for (const line of diff.slice(0, 40)) console.log("    " + line);
  if (diff.length > 40) console.log(`    ... 他 ${diff.length - 40} 行`);
}

function main(): number {
  const sourceText = read(SOURCE);
  if (sourceText === null) {
    console.log(`NG: ${SOURCE} が見つかりません`);
    return 1;
  }
  const expected = normalize(sourceText);

  const targets: Array<[string, (text: string) => Extracted]> = [
    [SETUP, extractFromSetup],
    [AGENT, extractFromAgent],
    [FIXTURE_AGENT, extractFromAgent],
  ];

  let failed = false;
  for (const [relpath, extract] of targets) {
    const text = read(relpath);
    if (text === null) {
      console.log(`SKIP ${relpath} （ファイルが存在しません）`);
      continue;
    }

    const [body, error] = extract(text);
    if (error || body === null) {
      console.log(`NG   ${relpath} — ${error}`);
      failed = true;
      continue;
    }

    const actual = normalize(body);
    if (actual.length === expected.length && actual.every((line, i) => line === expected[i])) {
      console.log(`OK   ${relpath} （${actual.length} 行）`);
    } else {
      console.log(`NG   ${relpath} — 本文が ${SOURCE} とずれています`);
      reportDiff(relpath, expected, actual);
      failed = true;
    }
  }

  console.log("");
  if (failed) {
    console.log(`ずれがあります。${SOURCE} を唯一のソースとして、コピー先を貼り直してください。`);
    return 1;
  }
  console.log("すべて一致しています。");
  return 0;
}

if (import.meta.main) {
  process.exitCode = main();
}
