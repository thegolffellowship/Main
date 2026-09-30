#!/usr/bin/env node
/* recap_docx.js — render a recap draft (markdown-ish, the shape written
 * under docs/claude/recaps/) as a formatted Word file the chapter manager
 * can paste into his email tool. Robert Straiton, 2026-09-16: "I really
 * would love if it could almost duplicate the spacing, where I bold, etc.
 * I had to spend 10 minutes formatting it." Kerry: "It can and will."
 *
 *   node tools/recap_docx.js <recap.md> --section "SAN ANTONIO" -o out.docx
 *
 * --section picks the "## <NAME> —" block (first match, case-insensitive);
 * omit it to render the whole file. Markup understood: **bold**,
 * [text](url) → real hyperlink, lines "- " → bullets, a line of CAPS ending
 * in "." → section head (rule above, bold, all caps, empty line below),
 * a "***" line → a rule with no head, {green}…{/green} → green text,
 * "**Subject:** …" → subject line, "[__ …]" placeholders → yellow
 * highlight, blank line → new block. Blocks are separated by ONE empty
 * paragraph (no paragraph spacing), and the lines after "See you…" keep
 * their breaks — the shape of Kerry's s9.25 send, 2026-09-30: "Learn from
 * my edits. Including all formatting and spacing."
 * Needs the `docx` npm package (npm i docx).
 */
const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, ExternalHyperlink, AlignmentType, LevelFormat, BorderStyle } = require("docx");

const args = process.argv.slice(2);
const src = args.find(a => !a.startsWith("--") && a.endsWith(".md"));
const sec = args.includes("--section") ? args[args.indexOf("--section") + 1] : null;
const out = args.includes("-o") ? args[args.indexOf("-o") + 1] : src.replace(/\.md$/, ".docx");
if (!src) { console.error("usage: recap_docx.js <recap.md> [--section NAME] [-o out.docx]"); process.exit(2); }

let text = fs.readFileSync(src, "utf8");
if (sec) {
  const re = new RegExp(`^## ${sec.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^\\n]*\\n([\\s\\S]*?)(?=^## |^---\\s*$|(?![\\s\\S]))`, "im");
  const m = text.match(re);
  if (!m) { console.error(`section "${sec}" not found`); process.exit(3); }
  text = m[1];
}

const FONT = "Arial", SIZE = 22;
const run = (t, o = {}) => new TextRun({ text: t, font: FONT, size: SIZE, ...o });
// inline: **bold**, [text](url), [__ blank __]
function inline(s, base = {}) {
  const outRuns = [];
  const re = /(\*\*(.+?)\*\*)|(\[([^\]]+)\]\((https?:[^)\s]+)\))|(\[(_[^\]]*)\])|(\{green\}(.+?)\{\/green\})/g;
  let i = 0, m;
  while ((m = re.exec(s))) {
    if (m.index > i) outRuns.push(run(s.slice(i, m.index), base));
    if (m[9] !== undefined) outRuns.push(...inline(m[9], { ...base, color: "27AE60" }));
    else if (m[2] !== undefined) outRuns.push(run(m[2], { ...base, bold: true }));
    else if (m[4] !== undefined) outRuns.push(new ExternalHyperlink({ link: m[5], children: [run(m[4], { ...base, style: "Hyperlink", bold: true })] }));
    else outRuns.push(run(`[${m[7]}]`, { ...base, highlight: "yellow" }));
    i = m.index + m[0].length;
  }
  if (i < s.length) outRuns.push(run(s.slice(i), base));
  return outRuns;
}
const isHead = (l) => /^[A-Z0-9 .&'\-]+\.$/.test(l.trim()) && l.trim().length <= 40;

const children = [];
const lines = text.replace(/\r/g, "").split("\n");
const SP = { after: 0, line: 276 };
const rule = () => new Paragraph({ children: [], border: { top: { style: BorderStyle.SINGLE, size: 6, color: "A0A0A0", space: 1 } }, spacing: SP });
const spacer = () => new Paragraph({ children: [run("")], spacing: SP });
// Blocks, then spacers between them (none before a rule, one after a head).
const blocks = [];
let para = [], bullets = [], sig = false;
const flush = () => {
  if (para.length) { blocks.push({ k: "p", v: new Paragraph({ children: inline(para.join(" ")), spacing: SP }) }); para = []; }
  if (bullets.length) { blocks.push({ k: "ul", v: bullets.map(b => new Paragraph({ children: inline(b.t), numbering: { reference: "bul", level: b.lvl }, spacing: SP })) }); bullets = []; }
};
for (const raw of lines) {
  const l = raw.replace(/\s+$/, "");
  if (sig && l.trim()) { blocks.push({ k: "sig", v: new Paragraph({ children: inline(l.trim()), spacing: SP }) }); continue; }
  if (!l.trim()) { flush(); continue; }
  if (/^\*\*Subject:\*\*/.test(l)) { flush(); children.push(new Paragraph({ children: [run("Subject: ", { color: "666666" }), ...inline(l.replace(/^\*\*Subject:\*\*\s*/, ""), { bold: true })], spacing: { after: 200 } })); continue; }
  if (l.trim() === "***") { flush(); blocks.push({ k: "rule" }); continue; }
  if (isHead(l)) { flush(); blocks.push({ k: "rule" }); blocks.push({ k: "head", v: new Paragraph({ children: [run(l.trim(), { bold: true, allCaps: true })], spacing: SP }) }); continue; }
  if (/^\s*[-•]\s+/.test(l)) {
    if (para.length) flush();
    bullets.push({ t: l.replace(/^\s*[-•]\s+/, ""), lvl: /^\s{2,}/.test(l) ? 1 : 0 });
    continue;
  }
  if (bullets.length) flush();
  para.push(l.trim());
  if (/^see you/i.test(l.trim())) { flush(); sig = true; blocks.push({ k: "sigstart" }); }
}
flush();
let prev = null;
for (const b of blocks) {
  if (b.k === "rule") { children.push(rule()); prev = "rule"; continue; }
  if (b.k === "sigstart") { children.push(spacer()); prev = "rule"; continue; }
  if (b.k === "sig") { children.push(b.v); prev = "sig"; continue; }
  if (b.k === "head") { children.push(b.v, spacer()); prev = "rule"; continue; }
  if (prev && prev !== "rule") children.push(spacer());
  if (b.k === "ul") children.push(...b.v); else children.push(b.v);
  prev = b.k;
}

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } },
  ] }] },
  styles: { default: { document: { run: { font: FONT, size: SIZE } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(out, b); console.log(`wrote ${out} (${b.length} bytes, ${children.length} paragraphs)`); });
