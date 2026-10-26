/* 12-hour display (Kerry 2026-10-26, CoS #2325: "Please don't use Military
 * Time"). Every time a member, manager or course READS is 12-hour with AM/PM.
 * Display only: stored values, cron strings, logs, ISO API stamps and sort
 * keys stay 24-hour. The Python twin is timezone_utils.clock12 / stamp12.
 *
 * window.tgfTime12("16:30")            -> "4:30 PM"
 * window.tgfTime12("2026-10-26 15:40") -> "2026-10-26 3:40 PM"
 * window.tgfTime12("2026-10-26T15:40:12Z") -> "2026-10-26 3:40 PM"
 * Text already in 12-hour form comes back unchanged. Loaded by _shell_nav.html.
 */
(function () {
  var HM = /(^|[^\d:])(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?![\d:])(?!\s*[AaPp]\.?[Mm])/g;
  function tgfTime12(s) {
    if (s === null || s === undefined) return "";
    var t = String(s).replace(/^(\d{4}-\d{2}-\d{2})T/, "$1 ").replace(/(\d)Z$/, "$1");
    return t.replace(HM, function (m, pre, h, mm) {
      var n = parseInt(h, 10);
      if (n > 23) return m;
      return pre + ((n % 12) || 12) + ":" + mm + " " + (n >= 12 ? "PM" : "AM");
    });
  }
  if (typeof window !== "undefined") window.tgfTime12 = tgfTime12;
  if (typeof module !== "undefined" && module.exports) module.exports = tgfTime12;
})();
