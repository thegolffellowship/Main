// Apply Credit on a Golf Genius-only (RSVP, no order) row must reach the
// credit-info route (Kerry, 2026-09-27, 9:54 PM: "James Wilson", CREDIT
// badge, the modal said only "Failed to load credit info.").
// Root cause: the MOBILE roster built its synthetic gg-rsvp rows without
// rsvp_id, so the badge carried neither an rsvp id nor an item id and the
// modal fetched /api/rsvps/null/credit-info (an HTML 404).
//
// 1. CLASS guard: every builder that makes a DISPLAYED synthetic gg-rsvp
//    row (it carries `customer:`) also carries rsvp_id.
// 2. The modal: with no id it says so and never fetches; with an rsvp id
//    it calls the GG route; a non-JSON error shows the HTTP status.
//
// Run: node test_apply_credit_ids.js
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, 'templates/events.html'), 'utf8');

let failures = 0;
const check = (label, cond, detail) => {
  console.log((cond ? '  PASS  ' : '  FAIL  ') + label + (cond ? '' : '  ' + (detail || '')));
  if (!cond) failures++;
};

// ── 1. every displayed synthetic gg-rsvp row carries rsvp_id ──
const re = /id:\s*`gg-rsvp-\$\{i\}`[\s\S]*?\}\)\)/g;
let m, builders = 0, displayed = 0;
while ((m = re.exec(src)) !== null) {
  builders++;
  const obj = m[0];
  if (!/\bcustomer:/.test(obj)) continue; // stats-only rows never render a badge
  displayed++;
  const line = src.slice(0, m.index).split('\n').length;
  check(`gg-rsvp row builder at line ${line} carries rsvp_id`, /\brsvp_id:\s*r\.id\b/.test(obj), obj.slice(0, 160));
}
check('found the synthetic-row builders (desktop + mobile at least)', displayed >= 2, `displayed=${displayed} builders=${builders}`);

// ── 2. the modal itself ──
const start = src.indexOf('    async function openApplyCreditModal(');
check('openApplyCreditModal found', start >= 0);
// slice to the function's closing brace at 4-space indent
const rest = src.slice(start);
const end = rest.search(/\n    }\n/);
const fnSrc = rest.slice(0, end + 7);

function makeEnv(fetchImpl) {
  const els = {};
  const el = () => ({ innerHTML: '', style: {} });
  const document = { getElementById: id => (els[id] = els[id] || el()) };
  const calls = [];
  const fetch = async url => { calls.push(url); return fetchImpl(url); };
  const escapeHtml = s => String(s ?? '');
  // eslint-disable-next-line no-new-func
  const f = new Function('document', 'fetch', 'escapeHtml',
    'let applyCreditState = null;\n' + fnSrc + '\nreturn openApplyCreditModal;');
  return { open: f(document, fetch, escapeHtml), els, calls };
}

(async () => {
  // no id at all (the James Wilson case)
  let env = makeEnv(async () => { throw new Error('must not fetch'); });
  await env.open(null, '', 'Wilson, James', 's9.25 Canyon Springs');
  check('no id: never fetches', env.calls.length === 0, JSON.stringify(env.calls));
  check('no id: says the row carries no id',
    /no RSVP id and no order id/.test(env.els['apply-credit-body'].innerHTML), env.els['apply-credit-body'].innerHTML);

  env = makeEnv(async () => { throw new Error('must not fetch'); });
  await env.open('null', 'undefined', 'X', 'E');
  check('string "null"/"undefined" ids are treated as missing', env.calls.length === 0, JSON.stringify(env.calls));

  // an rsvp id goes to the GG route; a non-JSON 404 shows the status
  env = makeEnv(async () => ({ ok: false, status: 404, json: async () => { throw new Error('html'); } }));
  await env.open(null, '5521', 'Wilson, James', 'E');
  check('rsvp id calls the GG credit-info route', env.calls[0] === '/api/rsvps/gg/5521/credit-info', env.calls[0]);
  check('non-JSON error shows the HTTP status',
    /HTTP 404/.test(env.els['apply-credit-body'].innerHTML), env.els['apply-credit-body'].innerHTML);

  // a JSON reason is still shown verbatim, without the status suffix
  env = makeEnv(async () => ({ ok: false, status: 404, json: async () => ({ error: 'No credits on file for this player' }) }));
  await env.open('812', null, 'X', 'E');
  check('item id calls the item route', env.calls[0] === '/api/rsvps/812/credit-info', env.calls[0]);
  const html = env.els['apply-credit-body'].innerHTML;
  check('JSON reason shown verbatim', /No credits on file for this player/.test(html) && !/HTTP 404/.test(html), html);

  console.log(failures ? `\n${failures} FAILURE(S)` : '\nALL PASS');
  process.exit(failures ? 1 : 0);
})();
