/* LONE STAR CUP EVENT INFO — the Schedule | Teams | Formats toggle, the
   row highlight (#fourball, #skins ...) and Share link, for both homes of
   templates/_lsc_info_body.html: the standalone /member/lonestarcup/info
   page and the EVENT INFO view on LEADERBOARD > Lone Star Cup (Kerry 10/8).
   window.lscInfoWire(root, {key, onPick, shareUrl}) -> show(key) */
(function () {
  var SEC = { schedule: "schedule", teams: "teams", formats: "formats",
              fourball: "formats", foursomes: "formats", singles: "formats", skins: "formats",
              scoring: "scoring" };
  window.lscInfoSection = function (key) { return SEC[key] || "schedule"; };
  window.lscInfoWire = function (root, opts) {
    opts = opts || {};
    var info = root.querySelector(".lsc-info") || root;
    function show(key, scroll) {
      key = String(key || "").replace("#", "");
      var sec = SEC[key] || "schedule";
      info.querySelectorAll("section[data-sec]").forEach(function (s) { s.classList.toggle("on", s.dataset.sec === sec); });
      info.querySelectorAll("[data-lsc-info-seg] a").forEach(function (a) { a.classList.toggle("on", a.dataset.s === sec); });
      info.querySelectorAll(".d.hl").forEach(function (d) { d.classList.remove("hl"); });
      var el = key && key !== sec ? info.querySelector('[data-a="' + key + '"]') : null;
      if (el) {
        if (el.classList.contains("d")) el.classList.add("hl");
        if (scroll) setTimeout(function () { el.scrollIntoView({ block: "center" }); }, 30);
      }
      return sec;
    }
    var seg = info.querySelector("[data-lsc-info-seg]");
    if (seg) seg.addEventListener("click", function (e) {
      var a = e.target.closest("a"); if (!a) return;
      e.preventDefault();
      show(a.dataset.s, false);
      if (opts.onPick) opts.onPick(a.dataset.s);
    });
    var share = info.querySelector("[data-lsc-info-share]");
    if (share) share.addEventListener("click", function () {
      var url = opts.shareUrl ? opts.shareUrl() : location.origin + location.pathname;
      try {
        if (navigator.share) { navigator.share({ title: "Lone Star Cup 2026", url: url }).catch(function () {}); }
        else if (navigator.clipboard) { navigator.clipboard.writeText(url).then(function () { share.textContent = "Link copied"; }); }
      } catch (e) { /* cancelled */ }
    });
    show(opts.key || "schedule", !!opts.scroll);
    return show;
  };
})();
