// Shared course + played-nine label (Kerry 2026-07-18).
// A round shows the nine PLAYED on its course, consistently everywhere:
//   * A course with GENERIC nines (Kissing Tree, Vaaler, Silverhorn, Quarry)
//     reads "Course - Front" / "Course - Back" — holes 1-9 = Front, 10-18 = Back.
//   * A course that NAMES its nines (Comanche Creeks/Hills/Valley, Hyatt
//     Oaks/Lakes/Creeks) carries the name in course_name and is shown with the
//     NAME — never a generic "Front/Back".
// The server (get_handicap_rounds) sets round.nine to 'front'/'back' ONLY for
// generic 18-hole courses; named-nine courses arrive with no .nine and simply
// render their (already nine-named) course name. Exposes window.courseNineLabel.
(function (w) {
    // Trim course boilerplate on narrow screens; full name on desktop.
    function shortCourse(n) {
        if (!(w.matchMedia && w.matchMedia('(max-width: 768px)').matches)) return n;
        let out = String(n || '').trim()
            .replace(/^\s*(the\s+)?(club|course)\s+at\s+/i, '')
            .replace(/^\s*hyatt\s+(regency\s+)?/i, '');
        for (let i = 0; i < 2; i++) {
            out = out.replace(/\s+(golf\s+(club|course|resort|links)|country\s+club|golf\s*&\s*country\s+club|resort(\s*&\s*spa)?|ranch\s+resort|golf|club)\s*$/i, '');
        }
        out = out.replace(/^[\s\-|–—]+|[\s\-|–—]+$/g, '');
        return out || n;
    }
    // A course_name of the form "Base | NineA / NineB" (or "Base - A / B") carries
    // both nine names — use the played one; otherwise fall back to "- Front/Back".
    function hcpNineLabel(fullName, shortLabel, nine) {
        const m = (fullName || '').match(/^(.*?)[|–-]\s*([^\/|]+?)\s*\/\s*([^\/|]+?)\s*$/);
        if (m) {
            const nineName = (nine === 'front' ? m[2] : m[3]).trim();
            return `${m[1].replace(/[\s|–-]+$/, '').trim()} | ${nineName}`;
        }
        return `${shortLabel || fullName || '—'} - ${nine === 'front' ? 'Front' : 'Back'}`;
    }
    // Display label for a round-like object {course_name, course_short, nine}.
    w.courseNineLabel = function (round) {
        const base = (round && (round.course_short || shortCourse(round.course_name))) || '—';
        return (round && round.nine) ? hcpNineLabel(round.course_name, base, round.nine) : base;
    };
    // Tidy a tee label: drop the word "Tee" and any "— Front 9 / — Back 9" nine
    // suffix (the nine belongs on the course, not the tee).
    w.teeLabel = function (name) {
        const out = String(name || '')
            .replace(/\s*[—–-]\s*(Front|Back)\s*9?\b/gi, '')
            .replace(/\s*\bTee\b/gi, '')
            .replace(/\s{2,}/g, ' ')
            .trim();
        return out || '—';
    };
})(window);
