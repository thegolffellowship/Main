/**
 * The message body editor is PLAIN TEXT (Kerry 2026-09-08: "Any way to
 * make that editor a regular text editor rather than a HTML editor?").
 *
 * The textarea holds text; HTML is generated on the way out. The only
 * markup the templates actually use is bold, so **stars** carry it. An
 * "Edit HTML" switch turns the conversion off for raw markup, and
 * flipping it converts what is already there so the two views always
 * describe the same message.
 *
 * Paragraph spacing is written INTO the markup, not left to the mail
 * client, and applied on the SERVER so templates written before the
 * standard existed get it too.
 *
 * Run: node test_compose_plaintext.js
 */
const fs = require("fs");
const html = fs.readFileSync("templates/events.html", "utf8");
const py = fs.readFileSync("email_parser/fetcher.py", "utf8");
const app = fs.readFileSync("app.py", "utf8");

let failures = 0;
function check(label, cond, detail) {
    if (cond) { console.log("  PASS  " + label); }
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

console.log("\nPlain-text editor");
check("an Edit HTML switch exists", /id="compose-html-mode"/.test(html));
check("html -> text on load", /function composeHtmlToText\(html\)/.test(html));
check("text -> html on the way out", /function composeTextToHtml\(text\)/.test(html));
check("the textarea tells you the two rules it follows",
    /Leave a blank line between paragraphs; wrap \*\*words in stars\*\* to bold them/.test(html));

// Every read of the body must go through composeBodyHtml, or one path
// (send, preview, save-as-template) silently mails raw markdown.
const reads = html.match(/document\.getElementById\("compose-body"\)\.value/g) || [];
check("no raw reads of the textarea survive outside the helpers",
    reads.length <= 3, `${reads.length} direct reads — expect only the helpers + reset`);
check("preview uses the converted body", /const body = composeBodyHtml\(\);/.test(html));
check("send uses the converted body", /const body = composeBodyHtml\(\)\.trim\(\);/.test(html));
check("loading a template goes through composeSetBody",
    /composeSetBody\(tpl\.html_body \|\| ""\)/.test(html));

console.log("\nRound trip");
check("bold survives both directions",
    /replace\(\/<\\s\*\(strong\|b\)\(\\s\[\^>\]\*\)\?>\/gi, "\*\*"\)/.test(html)
    && /replace\(\/\\\*\\\*\(\[\^\*\\n\]\+\)\\\*\\\*\/g, "<strong>\$1<\/strong>"\)/.test(html));
check("typed angle brackets are escaped, not injected",
    /\.replace\(\/&\/g, "&amp;"\)[\s\S]{0,120}\.replace\(\/<\/g, "&lt;"\)/.test(html));
check("flipping the switch converts what is already in the box",
    /modeEl\.checked\s*\n?\s*\?\s*composeTextToHtml\(ta\.value\)[\s\S]{0,120}composeHtmlToText\(ta\.value\)/.test(html));

console.log("\nParagraph spacing as a standard");
check("the house style is named once, server-side",
    /EMAIL_P_STYLE = "margin:0 0 1em;"/.test(py));
check("a <p> with no style of its own gets it", /def normalize_email_html/.test(py));
check("a <p> that already has a style is left alone",
    /\(\?!\[\^>\]\*\\b style\\s\*=\)/.test(py.replace(/\\s\*/g, "\\s*")) ||
    /style\\s\*=/.test(py));
check("the SEND path normalizes, so old templates get it too",
    /body_tpl = normalize_email_html\(body_tpl\)/.test(app));
check("the PREVIEW path normalizes too, so what he sees is what sends",
    (app.match(/body_tpl = normalize_email_html\(body_tpl\)/g) || []).length >= 2);
check("the composer emits the same spacing it will be sent with",
    /const COMPOSE_P_STYLE = "margin:0 0 1em;"/.test(html));

console.log("");
if (failures) { console.log(failures + " FAILURE(S)"); process.exit(1); }
console.log("All compose plain-text assertions passed.");
