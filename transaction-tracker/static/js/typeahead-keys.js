/**
 * Keyboard for EVERY typeahead on the Tracker (Kerry 2026-09-23: "On any
 * autofill type search on the tracker please add highlights to the arrow
 * down so I can arrow down or up, see visually which is selected, and
 * click enter to select.").
 *
 * The Tracker's typeaheads are hand-built per page (a list of buttons or
 * divs dropped under an input), so instead of rewiring each one this
 * listens once, in the CAPTURE phase, for ↓ ↑ Enter in any text box:
 *
 *   ↓ / ↑   find the suggestion list that is open under that box and move
 *           a highlight through its items (orange bar + tint, scrolled
 *           into view). ↓ from the last item stays put; ↑ from the first
 *           clears the highlight.
 *   Enter   with an item highlighted, picks it exactly as a tap would
 *           (mousedown, then click if the list is still open) and stops
 *           the page's own Enter handler, so "Enter picks the first
 *           match" shortcuts never override the one you chose. With
 *           nothing highlighted, Enter does what the page always did.
 *
 * Finding the list: the input's aria-controls / data-suggest target if it
 * names one; otherwise the nearest open, absolutely/fixed-positioned
 * element after the input inside its first few ancestors whose children
 * are clickable rows. Native <datalist> dropdowns are the browser's and
 * already have arrow keys. Loaded from the shell include on every page.
 */
(function () {
    if (window.tgfTypeaheadKeys) return;
    window.tgfTypeaheadKeys = true;
    var ACTIVE = "tgf-kb-active";

    var css = document.createElement("style");
    css.textContent =
        "." + ACTIVE + "{background:#FDF0E6 !important;box-shadow:inset 3px 0 0 var(--primary,#E87C3E) !important;" +
        "outline:none !important}";
    (document.head || document.documentElement).appendChild(css);

    function visible(el) {
        if (!el || !el.isConnected) return false;
        var cs = getComputedStyle(el);
        if (cs.display === "none" || cs.visibility === "hidden") return false;
        var r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    }
    function isTextInput(el) {
        if (!el) return false;
        if (el.tagName === "TEXTAREA") return false;          // multi-line: arrows move the caret
        if (el.tagName !== "INPUT") return false;
        var t = (el.getAttribute("type") || "text").toLowerCase();
        return t === "text" || t === "search" || t === "email" || t === "tel" || t === "";
    }
    function clickable(el) {
        if (!visible(el)) return false;
        var tag = el.tagName;
        if (tag === "BUTTON" || tag === "A" || tag === "LI") return true;
        if (el.getAttribute("role") === "option") return true;
        if (el.onclick || el.onmousedown) return true;
        return getComputedStyle(el).cursor === "pointer";
    }
    function itemsOf(box) {
        var direct = Array.prototype.filter.call(box.children, clickable);
        if (direct.length) return direct;
        // one wrapper level (a list inside a scroll div)
        for (var i = 0; i < box.children.length; i++) {
            var inner = Array.prototype.filter.call(box.children[i].children, clickable);
            if (inner.length) return inner;
        }
        return [];
    }
    function positioned(el) {
        var p = getComputedStyle(el).position;
        return p === "absolute" || p === "fixed";
    }
    function findList(input) {
        var id = input.getAttribute("aria-controls") || input.getAttribute("data-suggest");
        if (id) {
            var named = document.getElementById(id);
            if (named && visible(named) && itemsOf(named).length) return named;
        }
        if (input.list) return null;                          // native <datalist>
        var node = input.parentElement;
        for (var depth = 0; node && depth < 4; depth++, node = node.parentElement) {
            var cands = node.querySelectorAll("*");
            for (var i = 0; i < cands.length; i++) {
                var c = cands[i];
                if (c === input || c.contains(input)) continue;
                if (!(input.compareDocumentPosition(c) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
                if (!positioned(c) || !visible(c)) continue;
                if (itemsOf(c).length) return c;
            }
        }
        return null;
    }
    function setActive(items, idx) {
        items.forEach(function (it, i) { it.classList.toggle(ACTIVE, i === idx); });
        if (idx >= 0 && items[idx]) {
            try { items[idx].scrollIntoView({ block: "nearest" }); } catch (_) {}
        }
    }
    function pick(item, list) {
        var o = { bubbles: true, cancelable: true, view: window };
        item.dispatchEvent(new MouseEvent("mousedown", o));
        item.dispatchEvent(new MouseEvent("mouseup", o));
        // a mousedown-driven list closes itself; only click one still open
        if (item.isConnected && visible(list) && visible(item)) item.dispatchEvent(new MouseEvent("click", o));
    }

    document.addEventListener("keydown", function (e) {
        if (e.isComposing || e.altKey || e.ctrlKey || e.metaKey) return;
        var k = e.key;
        if (k !== "ArrowDown" && k !== "ArrowUp" && k !== "Enter") return;
        var input = e.target;
        if (!isTextInput(input)) return;
        var list = findList(input);
        if (!list) return;
        var items = itemsOf(list);
        if (!items.length) return;
        var cur = -1;
        for (var i = 0; i < items.length; i++) if (items[i].classList.contains(ACTIVE)) { cur = i; break; }
        if (k === "Enter") {
            if (cur < 0) return;                              // nothing chosen: the page's own Enter
            e.preventDefault(); e.stopPropagation();
            pick(items[cur], list);
            return;
        }
        e.preventDefault(); e.stopPropagation();              // the page's own arrow code stands down
        var next = k === "ArrowDown" ? Math.min(cur + 1, items.length - 1) : cur - 1;
        setActive(items, next);
    }, true);

    // the mouse and the keyboard share one highlight
    document.addEventListener("mouseover", function (e) {
        var el = e.target && e.target.closest ? e.target.closest("." + ACTIVE) : null;
        if (el) return;
        var any = document.querySelectorAll("." + ACTIVE);
        for (var i = 0; i < any.length; i++) {
            if (any[i].parentElement && any[i].parentElement.contains(e.target)) any[i].classList.remove(ACTIVE);
        }
    }, true);
})();
