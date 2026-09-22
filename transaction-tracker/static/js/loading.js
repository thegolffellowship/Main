/**
 * LOADING… — the page-wide in-flight indicator (Kerry 2026-09-22, 3:27 PM:
 * "We need some type of 'LOADING...' visual for our pages.").
 *
 * A ten-second wait with nothing moving reads as dead. This wraps
 * window.fetch so that while ANY request is in flight a slim TGF-orange
 * bar runs along the top of the page, and once a wait passes ~0.8 s a
 * small "Loading…" pill appears under it (the bar alone is easy to miss
 * on a phone). Nothing shows for a request that answers inside 150 ms,
 * so fast pages never flicker.
 *
 * Loaded from the shell include (templates/_shell_nav.html) BEFORE any
 * page script runs, so every fetch on every page is counted. Pages that
 * do their own long work without fetch can call
 * window.tgfLoading.start() / .end() (balanced), and any element with
 * the class `tgf-loading` renders the same pulsing "Loading…" text as a
 * panel placeholder.
 */
(function () {
    if (window.tgfLoading) return;                       // once per page
    var inflight = 0, showTimer = null, labelTimer = null, bar = null, label = null;
    var SHOW_AFTER_MS = 150, LABEL_AFTER_MS = 800, HIDE_AFTER_MS = 120;

    function ensureDom() {
        if (bar) return;
        var css = document.createElement("style");
        css.textContent =
            "#tgf-loading-bar{position:fixed;top:0;left:0;height:3px;width:100%;z-index:2000;pointer-events:none;" +
            "display:none;background:linear-gradient(90deg,transparent 0%,var(--primary,#E87C3E) 30%,var(--primary,#E87C3E) 70%,transparent 100%);" +
            "background-size:50% 100%;animation:tgf-loading-slide 1.1s linear infinite}" +
            "#tgf-loading-bar.on{display:block}" +
            "@keyframes tgf-loading-slide{0%{background-position:-50% 0}100%{background-position:150% 0}}" +
            "#tgf-loading-label{position:fixed;top:8px;right:12px;z-index:2000;pointer-events:none;display:none;" +
            "font:600 11px/1 'Bitter',serif;letter-spacing:1px;text-transform:uppercase;color:#fff;" +
            "background:var(--primary,#E87C3E);padding:6px 10px;border-radius:999px;box-shadow:0 2px 8px rgba(0,0,0,.18)}" +
            "#tgf-loading-label.on{display:block}" +
            ".tgf-loading{color:var(--text-muted,#6B7280);font-style:italic;animation:tgf-loading-pulse 1.2s ease-in-out infinite}" +
            ".tgf-loading:empty::before{content:'Loading\\2026'}" +
            "@keyframes tgf-loading-pulse{0%,100%{opacity:.45}50%{opacity:1}}" +
            "@media (prefers-reduced-motion: reduce){#tgf-loading-bar,.tgf-loading{animation:none}}";
        document.head.appendChild(css);
        bar = document.createElement("div"); bar.id = "tgf-loading-bar"; bar.setAttribute("aria-hidden", "true");
        label = document.createElement("div"); label.id = "tgf-loading-label"; label.setAttribute("role", "status");
        label.textContent = "Loading…";
        (document.body || document.documentElement).appendChild(bar);
        (document.body || document.documentElement).appendChild(label);
    }
    function show() { ensureDom(); bar.classList.add("on"); }
    function hide() {
        if (bar) bar.classList.remove("on");
        if (label) label.classList.remove("on");
    }
    function start() {
        inflight += 1;
        if (inflight === 1) {
            clearTimeout(showTimer); clearTimeout(labelTimer);
            showTimer = setTimeout(function () { if (inflight > 0) show(); }, SHOW_AFTER_MS);
            labelTimer = setTimeout(function () { if (inflight > 0) { ensureDom(); label.classList.add("on"); } }, LABEL_AFTER_MS);
        }
    }
    function end() {
        inflight = Math.max(0, inflight - 1);
        if (inflight === 0) {
            clearTimeout(showTimer); clearTimeout(labelTimer);
            setTimeout(function () { if (inflight === 0) hide(); }, HIDE_AFTER_MS);
        }
    }
    var origFetch = window.fetch;
    if (typeof origFetch === "function") {
        window.fetch = function () {
            start();
            var p;
            try { p = origFetch.apply(this, arguments); }
            catch (e) { end(); throw e; }
            return p.then(function (r) { end(); return r; }, function (e) { end(); throw e; });
        };
    }
    window.tgfLoading = { start: start, end: end, inflight: function () { return inflight; } };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ensureDom);
    else ensureDom();
})();
