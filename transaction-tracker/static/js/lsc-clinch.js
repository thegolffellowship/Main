/* THE CUP IS DECIDED: a congratulations pop-up on the scorer's site
   (Kerry 2026-10-09: "When the cup is clinched a pop up congratulations
   message needs to pop up on the scorers site to say which chapter has
   clinched/retained the cup."). One copy for both scorer pages: the
   SCORING card (score_entry.html, from card.cup_standings.cup) and the
   scorer's Cup LEADERBOARD (contests.html in SOLO_CUP mode, from the
   board's d.cup). The board's own cup_status decides: "won" (a side past
   half the points) or "retained" (the defending champion at half).
   Shown ONCE PER DEVICE: localStorage lsc_clinch_seen_<event>[_preview],
   shared by both pages (same origin).
   window.lscClinchPopup({status, winner, austin, sa, event_id, preview}) */
(function () {
  var TEAM = { austin: { name: "AUSTIN", color: "#BF5700" },
               sa: { name: "SAN ANTONIO", color: "#4B6274" } };
  var NAVY = "#002855";

  function half(x) {
    x = Math.round((Number(x) || 0) * 2) / 2;
    var w = Math.floor(x), f = x - w;
    return (w || !f ? String(w) : "") + (f ? "½" : "");
  }
  function key(c) { return "lsc_clinch_seen_" + (c.event_id || "cup") + (c.preview ? "_preview" : ""); }
  function seen(c) { try { return localStorage.getItem(key(c)) === "1"; } catch (e) { return false; } }
  function mark(c) { try { localStorage.setItem(key(c), "1"); } catch (e) { /* private mode */ } }

  // the words, pinned by test_lsc_match_won.py
  function headline(c) {
    var t = TEAM[c.winner];
    if (!t) return "";
    return t.name + (c.status === "retained" ? " RETAINS" : " WINS") + " THE LONE STAR CUP";
  }

  function css() {
    if (document.getElementById("lsc-cl-css")) return;
    var s = document.createElement("style");
    s.id = "lsc-cl-css";
    s.textContent =
      ".lsc-cl-scrim{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:500}" +
      ".lsc-cl{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:501;" +
      "width:min(380px,calc(100% - 32px));max-height:calc(100% - 32px);overflow:hidden auto;border-radius:18px;" +
      "background:" + NAVY + ";color:#fff;text-align:center;box-shadow:0 18px 56px rgba(0,0,0,.45)}" +
      ".lsc-cl::after{content:'';position:absolute;top:-30%;bottom:-30%;width:40%;left:-70%;pointer-events:none;" +
      "transform:skewX(-18deg);background:linear-gradient(75deg,transparent,rgba(255,255,255,.22),transparent);" +
      "animation:lscClShine 3.6s ease-in-out .4s infinite}" +
      "@keyframes lscClShine{0%{left:-70%}55%{left:140%}100%{left:140%}}" +
      ".lsc-cl-x{position:absolute;top:10px;right:10px;z-index:2;width:36px;height:36px;border-radius:50%;border:0;" +
      "background:rgba(255,255,255,.16);color:#fff;font-size:17px;line-height:1;cursor:pointer}" +
      ".lsc-cl-logo{padding:26px 28px 8px}.lsc-cl-logo img{display:block;width:100%;max-width:250px;margin:0 auto}" +
      ".lsc-cl-word{display:none;font:800 22px/1.1 Bitter,Georgia,serif;letter-spacing:2px;padding:10px 0}" +
      ".lsc-cl-logo.nologo img{display:none}.lsc-cl-logo.nologo .lsc-cl-word{display:block}" +
      ".lsc-cl-eb{font:700 11px/1.2 Bitter,Georgia,serif;letter-spacing:2.4px;text-transform:uppercase;color:#E5C46B;margin-top:6px}" +
      ".lsc-cl-band{margin:12px 0 0;padding:16px 18px;font:800 24px/1.15 Bitter,Georgia,serif;letter-spacing:.6px}" +
      ".lsc-cl-score{display:flex;align-items:stretch;justify-content:center;margin:0}" +
      ".lsc-cl-score .t{flex:1 1 0;padding:10px 12px;font:800 12px/1.1 Bitter,Georgia,serif;letter-spacing:1px;display:flex;" +
      "align-items:center;gap:8px}.lsc-cl-score .t b{font-size:28px;line-height:1}" +
      ".lsc-cl-score .t.au{background:#BF5700;justify-content:flex-start}.lsc-cl-score .t.sa{background:#4B6274;justify-content:flex-end}" +
      ".lsc-cl-copy{padding:14px 20px 0;font:500 14px/1.45 'Helvetica Neue',Helvetica,Arial,sans-serif;color:#D7DEE8}" +
      ".lsc-cl-f{padding:16px 18px 20px}.lsc-cl-ok{width:100%;height:50px;border-radius:9999px;border:0;cursor:pointer;" +
      "background:#fff;color:" + NAVY + ";font:800 15px/1 Bitter,Georgia,serif;letter-spacing:.8px;text-transform:uppercase}" +
      "@media (prefers-reduced-motion: reduce){.lsc-cl::after{animation:none;display:none}}";
    document.head.appendChild(s);
  }

  function close() {
    ["lsc-cl", "lsc-cl-scrim"].forEach(function (id) { var el = document.getElementById(id); if (el) el.remove(); });
    document.removeEventListener("keydown", onKey);
  }
  function onKey(e) { if (e.key === "Escape") close(); }

  window.lscClinchPopup = function (c) {
    c = c || {};
    if (!(c.status === "won" || c.status === "retained") || !TEAM[c.winner]) return false;
    if (seen(c) || document.getElementById("lsc-cl")) return false;
    // never over the Cup splash: the next poll brings it back
    if (document.getElementById("se-splash")) return false;
    mark(c);
    css();
    var t = TEAM[c.winner];
    var scrim = document.createElement("div");
    scrim.className = "lsc-cl-scrim"; scrim.id = "lsc-cl-scrim";
    var m = document.createElement("div");
    m.className = "lsc-cl"; m.id = "lsc-cl";
    m.setAttribute("role", "dialog"); m.setAttribute("aria-modal", "true");
    m.setAttribute("aria-label", headline(c));
    m.innerHTML =
      '<button type="button" class="lsc-cl-x" aria-label="Close">&#10005;</button>' +
      '<div class="lsc-cl-logo"><img src="/static/lsc-logo-dark.png" alt="Lone Star Cup"><div class="lsc-cl-word">LONE STAR CUP 2026</div></div>' +
      '<div class="lsc-cl-eb">Congratulations' + (c.preview ? " · preview" : "") + '</div>' +
      '<div class="lsc-cl-band" style="background:' + t.color + '">' + headline(c) + '</div>' +
      '<div class="lsc-cl-score"><span class="t au">AUSTIN <b>' + half(c.austin) + '</b></span>' +
      '<span class="t sa"><b>' + half(c.sa) + '</b> SAN ANTONIO</span></div>' +
      '<div class="lsc-cl-copy">' + (c.status === "retained"
        ? "The defending champions keep the Cup. Matches still on the course play on for the record and for skins."
        : "The Cup is clinched. Matches still on the course play on for the record and for skins.") + '</div>' +
      '<div class="lsc-cl-f"><button type="button" class="lsc-cl-ok">Close</button></div>';
    document.body.append(scrim, m);
    var img = m.querySelector(".lsc-cl-logo img");
    img.addEventListener("error", function () { img.parentNode.classList.add("nologo"); });
    scrim.addEventListener("click", close);
    m.querySelector(".lsc-cl-x").addEventListener("click", close);
    m.querySelector(".lsc-cl-ok").addEventListener("click", close);
    document.addEventListener("keydown", onKey);
    return true;
  };
  window.lscClinchHeadline = headline;
})();
