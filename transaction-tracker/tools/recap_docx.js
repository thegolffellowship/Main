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
 * in "." → section head (bold, all caps), "**Subject:** …" → subject line,
 * "[__ …]" placeholders → yellow highlight, blank line → paragraph break.
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
  const re = /(\*\*(.+?)\*\*)|(\[([^\]]+)\]\((https?:[^)\s]+)\))|(\[(_[^\]]*)\])/g;
  let i = 0, m;
  while ((m = re.exec(s))) {
    if (m.index > i) outRuns.push(run(s.slice(i, m.index), base));
    if (m[2] !== undefined) outRuns.push(run(m[2], { ...base, bold: true }));
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
let para = [];
const flush = () => { if (para.length) { children.push(new Paragraph({ children: inline(para.join(" ")), spacing: { after: 160, line: 300 } })); para = []; } };
for (const raw of lines) {
  const l = raw.replace(/\s+$/, "");
  if (!l.trim()) { flush(); continue; }
  if (/^\*\*Subject:\*\*/.test(l)) { flush(); children.push(new Paragraph({ children: [run("Subject: ", { color: "666666" }), ...inline(l.replace(/^\*\*Subject:\*\*\s*/, ""), { bold: true })], spacing: { after: 200 } })); continue; }
  // A thin rule above every section head, as Kerry's sent email has it
  // (s9.24, 2026-09-23) — the sections read as blocks, not one long page.
  if (isHead(l)) { flush(); children.push(new Paragraph({ children: [run(l.trim(), { bold: true, allCaps: true })], border: { top: { style: BorderStyle.SINGLE, size: 6, color: "D9D9D9", space: 10 } }, spacing: { before: 240, after: 120 } })); continue; }
  if (/^\s*[-•]\s+/.test(l)) {
    flush();
    const lvl = /^\s{2,}/.test(l) ? 1 : 0;
    children.push(new Paragraph({ children: inline(l.replace(/^\s*[-•]\s+/, "")), numbering: { reference: "bul", level: lvl }, spacing: { after: 80, line: 300 } }));
    continue;
  }
  para.push(l.trim());
}
flush();

const doc = new Document({
  numbering: { config: [{ reference: "bul", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } },
  ] }] },
  styles: { default: { document: { run: { font: FONT, size: SIZE } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(out, b); console.log(`wrote ${out} (${b.length} bytes, ${children.length} paragraphs)`); });
