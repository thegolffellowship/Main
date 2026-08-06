"""R6 Championship Chase email — mailbox #294–#299 build.

Design handoff: #295 (template) · #296 (slots/copy) · #297 (logic)
· #298 (assets/tokens/links/QA) · #299 (acceptance + additions).
Kerry-signed R6; test-send gate to Kerry's inbox only (#294/#298/#299).

The template below is design-claude's #295 production HTML verbatim,
with the four sanctioned module tokens the package itself calls for:
{{cta_block}} (CTA states A/B/C, #297b), {{pc_card}} (the suppressible
Players Cup module, #295/#297c), {{seat_row_label}} (inside-the-line
payoff swap, #297d), and the #299 preheader div + compliance footer.
Kerry-ratified copy is frozen — DO NOT EDIT wording (#296).
"""

import json
import logging
import os

from .database import (DB_PATH, _connect, get_app_setting,
                       get_player_spotlight, snapshot_target_list,
                       get_points_race_live, _handicap_recap_recipient)

logger = logging.getLogger(__name__)

BASE = "https://tgf-tracker.up.railway.app"

# ── deep links (#292/#298, confirmed #300) ──────────────────────────
_NET_RACE_HASH = {"San Antonio": "net", "Austin": "austin"}

# Store URLs (GoDaddy) — dials until Kerry/CA post canonical product
# URLs (#300 ask). Tests may go out with the placeholder flagged.
_SIGNUP_DIAL = "chase_link_signup"
_BUYIN_DIAL = "chase_link_buyin"
_PLACEHOLDER_STORE = "https://thegolffellowship.com/shop"

TEMPLATE = """<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>Your TGF Snapshot</title>
<style>
  @media only screen and (max-width:479px){
    .chain td.chain-cell{display:block !important; width:100% !important; box-sizing:border-box !important;}
    .chain td.chain-arrow{display:block !important; width:100% !important; padding:5px 0 !important;}
    .arrow-h{display:none !important;}
    .arrow-v{display:inline !important;}
  }
</style>
</head>
<body style="margin:0; padding:0; background:#F3F1EE;" bgcolor="#F3F1EE">
<div style="display:none; font-size:1px; line-height:1px; max-height:0; max-width:0; opacity:0; overflow:hidden; mso-hide:all;">{{preheader}}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; background:#F3F1EE;" bgcolor="#F3F1EE">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="620" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; width:620px; max-width:620px; font-family:Georgia,'Times New Roman',serif; color:#1B1B1B;">

<!-- HEADER (ratified as-is) -->
<tr><td style="background:#1B1B1B; padding:26px 30px 24px;" bgcolor="#1B1B1B">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;"><tr>
    <td style="vertical-align:middle; padding-right:20px;"><img src="{{ASSET_ROUNDEL_WHITE}}" alt="The Golf Fellowship" width="72" height="72" style="display:block; border:0;"></td>
    <td style="vertical-align:middle;">
      <div style="color:#E87C3E; font-size:12px; letter-spacing:0.22em; text-transform:uppercase; margin-bottom:5px;">Your TGF Snapshot</div>
      <div style="color:#FFFFFF; font-size:30px; font-weight:700; line-height:1.05;">{{full_name}}</div>
      <div style="color:#9C9A95; font-family:Helvetica,Arial,sans-serif; font-size:13px; margin-top:6px;">{{chapter}} &middot; {{send_date}}</div>
    </td>
  </tr></table>
</td></tr>

<tr><td style="background:#FFFFFF; border:1px solid #E2DFDA; border-top:0; padding:26px 30px 30px;" bgcolor="#FFFFFF">

  <!-- CAUSAL CHAIN STRIP: widths 22.5/7/22.5/7/41 -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" class="chain" style="border-collapse:collapse; width:100%; table-layout:fixed;">
    <tr>
      <td class="chain-cell" style="width:22.5%; background:#F6F4F1; border-top:3px solid #1B1B1B; vertical-align:bottom; padding:0;" bgcolor="#F6F4F1">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
          <tr><td style="text-align:center; padding:15px 8px 13px;">
            <div style="font-size:30px; font-weight:700; line-height:1;">{{city_finish_ordinal}}</div>
            <div style="font-family:Helvetica,Arial,sans-serif; font-size:9.5px; letter-spacing:0.08em; text-transform:uppercase; color:#8A867F; margin-top:7px; line-height:1.4;">{{city_net_label}}<br>&mdash; Final &mdash;</div>
          </td></tr>
          <tr><td style="background:#E8E5E0; text-align:center; padding:5px 2px;" bgcolor="#E8E5E0"><a href="{{link_city_net}}" style="font-family:Helvetica,Arial,sans-serif; font-size:8px; letter-spacing:0.1em; color:#6B675F; text-decoration:none; font-weight:700;">CLICK FOR STANDINGS</a></td></tr>
        </table>
      </td>
      <td class="chain-arrow" style="width:7%; text-align:center; color:#C05B21; font-size:17px; font-weight:700;"><span class="arrow-h">&#9654;</span><span class="arrow-v" style="display:none;">&#9660;</span></td>
      <td class="chain-cell" style="width:22.5%; background:#FBEFE4; border-top:3px solid #E87C3E; vertical-align:bottom; padding:0;" bgcolor="#FBEFE4">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
          <tr><td style="text-align:center; padding:15px 8px 13px;">
            <div style="font-size:30px; font-weight:700; line-height:1; color:#C05B21;">{{reset_seed}}</div>
            <div style="font-family:Helvetica,Arial,sans-serif; font-size:9.5px; letter-spacing:0.08em; text-transform:uppercase; color:#9A5B2E; margin-top:7px; line-height:1.4;">Fellowship Cup<br>Points Reset</div>
          </td></tr>
          <tr><td style="background:#F3D9C0; text-align:center; padding:5px 2px;" bgcolor="#F3D9C0"><a href="{{link_fellowship_cup}}" style="font-family:Helvetica,Arial,sans-serif; font-size:8px; letter-spacing:0.1em; color:#9A5B2E; text-decoration:none; font-weight:700;">CLICK FOR STANDINGS</a></td></tr>
        </table>
      </td>
      <td class="chain-arrow" style="width:7%; text-align:center; color:#C05B21; font-size:17px; font-weight:700;"><span class="arrow-h">&#9654;</span><span class="arrow-v" style="display:none;">&#9660;</span></td>
      <td class="chain-cell" style="width:41%; background:#002868; border-top:3px solid #E87C3E; vertical-align:bottom; padding:0;" bgcolor="#002868">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
          <tr><td style="padding:14px 10px 13px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
              <tr>
                <td style="width:36px; vertical-align:middle; text-align:center;"><img src="{{ASSET_STAR_WHITE}}" alt="" width="22" height="22" style="display:inline-block; border:0;"></td>
                <td style="vertical-align:middle; text-align:center;">
                  <div style="color:#FFFFFF; font-size:22px; font-weight:700; line-height:1;">{{seat_gap_display}}</div>
                  <div style="font-family:Helvetica,Arial,sans-serif; font-size:9px; letter-spacing:0.06em; text-transform:uppercase; color:#9DB4D6; margin-top:4px; line-height:1.45;">{{seat_row_label}}</div>
                </td>
              </tr>
              <tr>
                <td style="font-size:0; line-height:0;">&nbsp;</td>
                <td style="padding:8px 0;"><table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; width:74%; margin:0 auto;"><tr><td style="height:1px; background:#33517F; font-size:0; line-height:0;" bgcolor="#33517F">&nbsp;</td></tr></table></td>
              </tr>
              <tr>
                <td style="width:36px; vertical-align:middle; text-align:center;"><img src="{{ASSET_TROPHY_ORANGE}}" alt="" width="22" height="22" style="display:inline-block; border:0;"></td>
                <td style="vertical-align:middle; text-align:center;">
                  <div style="color:#FFFFFF; font-size:22px; font-weight:700; line-height:1;">{{cup_gap}}</div>
                  <div style="font-family:Helvetica,Arial,sans-serif; font-size:9px; letter-spacing:0.06em; text-transform:uppercase; color:#9DB4D6; margin-top:4px; line-height:1.45;">from winning<br>The Fellowship Cup</div>
                </td>
              </tr>
            </table>
          </td></tr>
          <tr><td style="background:#0B3574; text-align:center; padding:5px 2px;" bgcolor="#0B3574"><a href="{{link_lone_star_cup}}" style="font-family:Helvetica,Arial,sans-serif; font-size:8px; letter-spacing:0.1em; color:#9DB4D6; text-decoration:none; font-weight:700;">CLICK FOR STANDINGS</a></td></tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- EXPLAINER PASSAGE (P1/P2/P3 frozen per #296) -->
  <div style="font-family:Helvetica,Arial,sans-serif; font-size:15px; color:#44403B; line-height:1.65; margin-top:20px;"><b>{{first_name}}</b>, your city finish is banked. The rest is decided at the TGF Championship, Aug 15&ndash;16 &mdash; if it ended today, {{seat_phrase}}.</div>
  <div style="font-family:Helvetica,Arial,sans-serif; font-size:15px; color:#44403B; line-height:1.65; margin-top:14px; background:#FBEFE4; padding:12px 16px;"><b style="font-family:Georgia,serif; color:#BF5700; letter-spacing:0.08em;">TRUE STORY</b> &mdash; Mark Freund, from San Antonio, overcame a 14.5 point deficit in 2024 to win The Fellowship Cup by 2.5 points!</div>
  <div style="font-family:Helvetica,Arial,sans-serif; font-size:15px; color:#44403B; line-height:1.65; margin-top:12px;"><b>One thing's for sure</b> &mdash; if you don't play, there's no chance to qualify. And your chances are better than you probably realize: seats only go to players who show up.</div>

{{pc_card}}

{{cta_block}}

  <!-- SPOTLIGHT CLOSE -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; width:100%; margin-top:20px;"><tr><td style="border-top:2px solid #1B1B1B; padding-top:18px; text-align:center;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; margin:0 auto;"><tr>
      <td style="border:2px solid #1B1B1B; border-radius:9999px;"><a href="{{link_spotlight}}" style="display:inline-block; color:#1B1B1B; font-family:Georgia,serif; font-weight:700; padding:10px 24px; font-size:13px; letter-spacing:0.08em; text-decoration:none;">SEE YOUR FULL SPOTLIGHT</a></td>
    </tr></table>
    <p style="font-family:Helvetica,Arial,sans-serif; color:#8A867F; font-size:11px; margin:12px 0 0;">Every number above is live from the TGF Tracker as of {{send_date}}.</p>
  </td></tr></table>

</td></tr>
{{footer_compliance}}
</table>
</td></tr>
</table>
</body>
</html>"""

# ── #297b CTA state blocks (copy frozen per #296) ────────────────────
_CTA_STATE_A = """  <!-- TWO STEPS — STATE A -->
  <div style="font-family:Georgia,serif; font-size:15px; color:#1B1B1B; font-weight:700; letter-spacing:0.04em; line-height:1.65; margin-top:20px;">TWO STEPS TO GET IN:</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; width:100%; margin-top:8px;">
    <tr><td style="border-top:2px solid #1B1B1B; padding-top:16px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;"><tr>
        <td style="width:26px; vertical-align:top; font-family:Georgia,serif; font-size:16px; font-weight:700; color:#BF5700;">1</td>
        <td style="vertical-align:top; font-family:Helvetica,Arial,sans-serif; font-size:13px; line-height:1.55; color:#44403B; padding-bottom:14px;">
          <div style="font-family:Georgia,serif; font-size:15px; font-weight:700; color:#1B1B1B; margin-bottom:6px;">Sign up for the TGF Championship.</div>
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;"><tr>
            <td style="background:#E87C3E; border-radius:9999px;" bgcolor="#E87C3E"><a href="{{link_signup}}" style="display:inline-block; color:#FFFFFF; font-family:Georgia,serif; font-weight:700; padding:11px 26px; font-size:13px; letter-spacing:0.08em; text-decoration:none;">SIGN UP FOR THE TGF CHAMPIONSHIP</a></td>
          </tr></table>
          <div style="font-size:11px; color:#8A867F; margin-top:8px;">Registration closes end of day <b style="color:#44403B;">{{deadline_date}}</b>.</div>
        </td>
      </tr>
      <tr>
        <td style="width:26px; vertical-align:top; font-family:Georgia,serif; font-size:16px; font-weight:700; color:#BF5700;">2</td>
        <td style="vertical-align:top; font-family:Helvetica,Arial,sans-serif; font-size:13px; line-height:1.55; color:#44403B;">
          <div style="font-family:Georgia,serif; font-size:15px; font-weight:700; color:#1B1B1B; margin-bottom:6px;">Then buy into your Cup(s).</div>
{{buyin_cards}}
        </td>
      </tr></table>
    </td></tr>
  </table>"""

_CTA_STATE_B = """  <!-- ONE STEP — STATE B (head copy NOT Kerry-ratified; #299 item 3) -->
  <div style="font-family:Georgia,serif; font-size:15px; color:#1B1B1B; font-weight:700; letter-spacing:0.04em; line-height:1.65; margin-top:20px;">You're signed up. One step left:</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; width:100%; margin-top:8px;">
    <tr><td style="border-top:2px solid #1B1B1B; padding-top:16px;">
{{buyin_cards}}
    </td></tr>
  </table>"""

_BUYIN_CARDS = """          <table role="presentation" cellpadding="0" cellspacing="8" border="0" style="border-collapse:separate; border-spacing:8px 0; width:100%; table-layout:fixed; margin-left:-8px;">
            <tr>
              <td style="border:1px solid #E2DFDA; border-top:3px solid #E87C3E; background:#FFFFFF; text-align:center; padding:12px 8px 10px; vertical-align:top;" bgcolor="#FFFFFF">
                <a href="{{link_fellowship_buyin}}" style="text-decoration:none; color:#1B1B1B;">
                  <div style="font-family:Georgia,serif; font-size:20px; font-weight:700;">$50</div>
                  <div style="font-family:Georgia,serif; font-size:12px; font-weight:700; margin-top:3px;">The Fellowship Cup</div>
                  <div style="font-family:Helvetica,Arial,sans-serif; font-size:10.5px; color:#8A867F; line-height:1.45; margin-top:4px;">Your {{reset_seed}} reset seed is waiting on it</div>
                </a>{{fellowship_buyin_pill}}
              </td>
              <td style="border:1px solid #E2DFDA; border-top:3px solid #1B1B1B; background:#FFFFFF; text-align:center; padding:12px 8px 10px; vertical-align:top;" bgcolor="#FFFFFF">
                <a href="{{link_players_buyin}}" style="text-decoration:none; color:#1B1B1B;">
                  <div style="font-family:Georgia,serif; font-size:20px; font-weight:700;">$50</div>
                  <div style="font-family:Georgia,serif; font-size:12px; font-weight:700; margin-top:3px;">The Players Cup</div>
                  <div style="font-family:Helvetica,Arial,sans-serif; font-size:10.5px; color:#8A867F; line-height:1.45; margin-top:4px;">{{pc_buyin_caption}}</div>
                </a>{{players_buyin_pill}}
              </td>
            </tr>
          </table>"""

_BUYIN_PILL = """<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; margin:8px auto 0;"><tr>
                  <td style="background:{color}; border-radius:9999px;" bgcolor="{color}"><a href="{href}" style="display:inline-block; color:#FFFFFF; font-family:Georgia,serif; font-weight:700; padding:9px 18px; font-size:11px; letter-spacing:0.08em; text-decoration:none;">BUY IN &middot; $50</a></td>
                </tr></table>"""

_PC_CARD = """  <!-- PLAYERS CUP CARD — SUPPRESSIBLE MODULE (drop this whole table when suppressed) -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse; width:100%; margin-top:16px;">
    <tr><td style="border:1px solid #E2DFDA; border-top:3px solid #1B1B1B; background:#F6F4F1; padding:0;" bgcolor="#F6F4F1">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;"><tr>
        <td style="width:58px; vertical-align:middle; text-align:center;"><img src="{{ASSET_TROPHY_BLACK}}" alt="" width="26" height="26" style="display:inline-block; border:0;"></td>
        <td style="padding:12px 20px 12px 0; font-family:Helvetica,Arial,sans-serif; font-size:12.5px; line-height:1.55; color:#44403B;">
          <div style="font-family:Georgia,serif; font-size:12px; letter-spacing:0.16em; text-transform:uppercase; color:#1B1B1B; font-weight:700; margin-bottom:4px;">The Players Cup &middot; your gross path</div>
          A second road to the Lone Star Cup weekend: you sit <b>{{pc_place_ordinal}}</b> with a points reset of <b>{{pc_reset}}</b> &mdash; only <b>{{pc_seat_gap}} from one of the {{pc_seats_available}} gross seats</b> available.
        </td>
      </tr></table>
      <div style="background:#E8E5E0; text-align:center; padding:5px 2px;" bgcolor="#E8E5E0"><a href="{{link_players_cup}}" style="font-family:Helvetica,Arial,sans-serif; font-size:8px; letter-spacing:0.1em; color:#9A5B2E; text-decoration:none; font-weight:700;">CLICK FOR STANDINGS</a></div>
    </td></tr>
  </table>"""

_FOOTER = """<tr><td style="padding:16px 30px 0; text-align:center; font-family:Helvetica,Arial,sans-serif; font-size:11px; color:#8A867F; line-height:1.6;">
The Golf Fellowship &middot; {address}<br>
Don't want these updates? <a href="mailto:{reply_to}?subject=UNSUBSCRIBE" style="color:#8A867F;">Unsubscribe</a> and we'll stop.
</td></tr>"""


def _ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return str(n) + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _rank_ordinal(v):
    """Board ranks arrive as ints OR tie notation ('T7'). 'T7' -> 'T7th'
    (first live find: Bryce's city finish)."""
    if v in (None, ""):
        return "—"
    s = str(v).strip().upper()
    tied = s.startswith("T")
    if tied:
        s = s[1:]
    try:
        o = _ordinal(int(float(s)))
    except (ValueError, TypeError):
        return str(v)
    return ("T" + o) if tied else o


def _n1(v):
    """One-decimal board style: 93.5 -> '93.5', 100.0 -> '100'."""
    return f"{v:g}" if v is not None else "—"


def _dot(v):
    """Leading-dot ratified style: 0.5 -> '.5' (#296)."""
    s = _n1(v)
    return s[1:] if s.startswith("0.") else s


def seat_ladder(gap, inside):
    """#297a — (seat_phrase, seat_gap_display). gap = points BELOW the
    chapter's last LSC seat (positive distance); inside = at/above it.
    Exact arithmetic; never round a gap to make a rung fit."""
    if inside:
        return ("you'd have a seat — nothing's final until Sunday",
                "IN")
    # #297: gap of exactly 1 renders "1 point"; all other gaps render
    # the bare number (2.5, 6.5).
    display = "1 point" if gap == 1 else _n1(gap)
    if gap <= 1:
        return ("you're only one net bogey from that Lone Star Cup seat",
                display)
    if gap <= 2:
        return "you're only one net par from that Lone Star Cup seat", display
    if gap <= 3:
        return ("you're only one net birdie from that Lone Star Cup seat",
                display)
    if gap <= 4:
        return "you're only two net pars from that Lone Star Cup seat", display
    if gap < 6:
        return f"you're just {_n1(gap)} points from that seat", display
    return f"you're {_n1(gap)} points from that seat", display


def _subject(gap, inside):
    """#299 candidate (AWAITING KERRY): ladder-driven for rungs 1-4,
    fallback for 5-7."""
    if not inside:
        if gap <= 1:
            unit = "one net bogey"
        elif gap <= 2:
            unit = "one net par"
        elif gap <= 3:
            unit = "one net birdie"
        elif gap <= 4:
            unit = "two net pars"
        else:
            unit = None
        if unit:
            return f"Your TGF Snapshot — {unit} from a Lone Star Cup seat"
    return "Your TGF Snapshot — the TGF Championship decides it"

PREHEADER = "Your city finish is banked. The rest is decided Aug 15–16."


def build_chase_email(customer_id: int, to_address: str | None = None,
                      send: bool = False, overrides: dict | None = None,
                      db_path=None) -> dict:
    """Render (and optionally send) the R6 chase email for one player.

    overrides (test matrix, #299): {"gap": float, "inside": bool,
    "cta_state": "A"|"B"|"C", "suppress_pc": bool, "pc_no_flight": bool}
    force render states without touching live data — every real number
    still comes from the player's spotlight payload.
    """
    ov = overrides or {}
    cid = int(customer_id)

    # Seat/gap/signup data: the Command Center target list computes
    # gap_to_seat for every push/defend player regardless of whether the
    # spotlight's LSC block resolved them to a seat/alternate (which
    # carries no gap numbers — first live find: Bryce, projected
    # alternate). The chase email IS the push/defend variant, so the
    # target list is its natural source of truth.
    tl = snapshot_target_list(db_path=db_path)
    entry = None
    for seg in ("push_entry", "defend"):
        entry = next((e for e in tl.get(seg, [])
                      if e.get("customer_id") == cid), None)
        if entry:
            break
    if not entry:
        return {"ok": False,
                "error": "player is not in the push/defend window — the "
                         "chase variant targets window players (normal "
                         "players get the standard snapshot)"}

    name = entry.get("name") or ""
    first = (name.split() or [""])[0]
    chapter = (entry.get("chapter") or "").strip()
    fcp = (entry.get("paths") or {}).get("Fellowship") or {}
    pcp = (entry.get("paths") or {}).get("Players") or {}

    # City-net final rank still comes off the spotlight (single-chapter
    # board, rank is already city-scoped).
    spot = get_player_spotlight(cid, db_path=db_path or DB_PATH)
    races = {r.get("key"): r for r in (spot.get("races") or [])}
    net_key = "austin_net" if chapter == "Austin" else "san_antonio_net"
    net = races.get(net_key) or {}

    # gap_to_seat is points - cut: >= 0 means INSIDE the line.
    raw_gap = fcp.get("gap_to_seat")
    inside = ov.get("inside", raw_gap is not None and raw_gap >= 0)
    gap = ov.get("gap", round(-raw_gap, 2) if raw_gap is not None
                 and raw_gap < 0 else 0)
    if raw_gap is None and "gap" not in ov and "inside" not in ov:
        return {"ok": False,
                "error": "no Fellowship seat line for this player "
                         "(chapter fields no LSC team?)"}

    phrase, gap_display = seat_ladder(gap, inside)
    seat_label = (f"A SEAT ON {chapter.upper()}'S<br>LONE STAR CUP TEAM "
                  f"&mdash; IF IT ENDED TODAY" if inside else
                  f"from a seat on {chapter}'s<br>Lone Star Cup team")

    # CTA state (#291/#297b)
    signed_up = bool(entry.get("tgf_champ_signed_up"))
    enrolled_any = bool(entry.get("enrolled_any"))
    state = ov.get("cta_state") or ("A" if not signed_up
                                    else ("C" if enrolled_any else "B"))

    # Players Cup chapter place — same convention as the spotlight's
    # _path_stats: place among ENROLLED chapter players plus self, on the
    # descending gross board (#296: Bryce = 5th).
    pc_place = None
    try:
        gross = get_points_race_live("players_cup_gross", db_path=db_path)
        ahead, seen = 0, False
        for r in gross.get("standings", []):
            if (r.get("player_chapter") or "").strip() != chapter:
                continue
            if r.get("customer_id") == cid:
                seen = True
                continue
            if r.get("enrolled") and not seen:
                ahead += 1
        pc_place = ahead + 1 if seen else None
    except Exception:
        logger.warning("chase: players-cup place lookup failed",
                       exc_info=True)

    # Players Cup module suppression (#297c): flag wired, threshold is a
    # dial AWAITING KERRY. Unset dial = always show (test-matrix forces
    # the suppressed render). Auto-suppress when the player has no gross
    # standing at all.
    pc_gap_raw = pcp.get("gap_to_seat")
    pc_inside = pc_gap_raw is not None and pc_gap_raw >= 0
    pc_gap = (round(-pc_gap_raw, 2) if pc_gap_raw is not None
              and pc_gap_raw < 0 else 0)
    no_flight = ov.get("pc_no_flight", pc_gap_raw is None
                       or pc_place is None)
    thr = get_app_setting("chase_pc_suppress_gap", db_path=db_path)
    suppress = ov.get("suppress_pc")
    if suppress is None:
        suppress = no_flight or (thr not in (None, "")
                                 and not pc_inside
                                 and pc_gap > float(thr))

    from .timezone_utils import today_central
    send_date = today_central().strftime("%B %-d, %Y")
    deadline = (get_app_setting("chase_deadline_display", db_path=db_path)
                or "Sunday, August 9")

    signup_url = (get_app_setting(_SIGNUP_DIAL, db_path=db_path)
                  or _PLACEHOLDER_STORE)
    buyin_url = (get_app_setting(_BUYIN_DIAL, db_path=db_path)
                 or _PLACEHOLDER_STORE)

    slots = {
        "preheader": PREHEADER,
        "full_name": name,
        "first_name": first,
        "chapter": chapter,
        "chapter_possessive": f"{chapter}'s",
        "send_date": send_date,
        "city_finish_ordinal": _rank_ordinal(net.get("rank")),
        "city_net_label": f"{chapter.upper()} CITY NET",
        "reset_seed": _n1(fcp.get("points")),
        "seat_gap_display": gap_display,
        "seat_row_label": seat_label,
        "seat_phrase": phrase,
        "cup_gap": _n1(max(fcp.get("points_back") or 0, 0)),
        "pc_place_ordinal": (_ordinal(pc_place)
                             if pc_place else "—"),
        "pc_reset": _n1(pcp.get("points")),
        "pc_seat_gap": ("inside the line" if pc_inside else _dot(pc_gap)),
        "pc_seats_available": str(pcp.get("seats") or 4),
        "pc_buyin_caption": ("The gross-points path to the same weekend"
                             if no_flight else
                             "The gross path — you're "
                             f"{'inside' if pc_inside else _dot(pc_gap)}"
                             " off its seat line" if not pc_inside else
                             "The gross path — you're inside its "
                             "seat line today"),
        "deadline_date": deadline,
        "link_city_net": (f"{BASE}/member/contests#race="
                          f"{_NET_RACE_HASH.get(chapter, 'net')}"
                          f"&player={cid}"),
        "link_fellowship_cup": f"{BASE}/member/contests#race=tfc&player={cid}",
        "link_lone_star_cup": f"{BASE}/member/contests#tab=lsc",
        "link_players_cup": f"{BASE}/member/contests#race=gross&player={cid}",
        "link_spotlight": f"{BASE}/member/spotlight?player={cid}",
        "link_signup": signup_url,
        "link_fellowship_buyin": buyin_url,
        "link_players_buyin": buyin_url,
        "ASSET_ROUNDEL_WHITE": f"{BASE}/static/email/tgf-roundel-white-144.png",
        "ASSET_STAR_WHITE": f"{BASE}/static/email/star-white-44.png",
        "ASSET_TROPHY_ORANGE": f"{BASE}/static/email/trophy-orange-44.png",
        "ASSET_TROPHY_BLACK": f"{BASE}/static/email/trophy-black-52.png",
    }

    # assemble modules
    if state == "A":
        cards = _BUYIN_CARDS.replace("{{fellowship_buyin_pill}}", "") \
                            .replace("{{players_buyin_pill}}", "")
        cta = _CTA_STATE_A.replace("{{buyin_cards}}", cards)
    elif state == "B":
        cards = _BUYIN_CARDS \
            .replace("{{fellowship_buyin_pill}}",
                     _BUYIN_PILL.format(color="#E87C3E",
                                        href=slots["link_fellowship_buyin"])) \
            .replace("{{players_buyin_pill}}",
                     _BUYIN_PILL.format(color="#1B1B1B",
                                        href=slots["link_players_buyin"]))
        cta = _CTA_STATE_B.replace("{{buyin_cards}}", cards)
    else:  # C — no commerce CTA
        cta = ""

    html = TEMPLATE.replace("{{pc_card}}", "" if suppress else _PC_CARD) \
                   .replace("{{cta_block}}", cta)

    # Compliance footer (#299 item 2): rides MEMBER sends; test sends to
    # Kerry keep it too so he approves the real render.
    address = (get_app_setting("email_business_address", db_path=db_path)
               or "San Antonio, TX")
    reply_to = os.getenv("EMAIL_ADDRESS") or "admin@thegolffellowship.com"
    html = html.replace("{{footer_compliance}}",
                        _FOOTER.format(address=address, reply_to=reply_to))

    for k, v in slots.items():
        html = html.replace("{{" + k + "}}", str(v))

    subject = _subject(gap, inside)
    result = {"ok": True, "customer_id": cid, "name": name,
              "state": state, "gap": gap, "inside": inside,
              "suppress_pc": bool(suppress), "no_flight": bool(no_flight),
              "subject": subject, "preheader": PREHEADER,
              "store_links_placeholder": signup_url == _PLACEHOLDER_STORE}
    if "{{" in html:
        import re as _re
        result["unfilled_slots"] = sorted(set(
            _re.findall(r"\{\{([a-zA-Z_]+)\}\}", html)))

    if not send:
        result["preview"] = html
        return result

    with _connect(db_path) as conn:
        to = (to_address or "").strip() or _handicap_recap_recipient(conn, "")
    if not to:
        return {**result, "ok": False, "error": "no recipient configured"}
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")
    if not all([tenant_id, client_id, client_secret, from_address]):
        return {**result, "ok": False,
                "error": "email not configured on server"}
    from email_parser.fetcher import send_mail_graph
    ok = send_mail_graph(tenant_id=tenant_id, client_id=client_id,
                         client_secret=client_secret,
                         from_address=from_address, to_address=to,
                         subject=subject, html_body=html)
    logger.info("Chase email cid=%s state=%s gap=%s -> %s: %s",
                cid, state, gap, to, "sent" if ok else "FAILED")
    return {**result, "sent": bool(ok), "sent_to": to}


def chase_test_matrix(baseline_customer_id: int, send: bool = False,
                      db_path=None) -> list:
    """#299 consolidated test matrix — every render built from the
    baseline player's LIVE data with forced states: State A baseline +
    ladder states 1-7 + State B + gross-suppressed + no-flight caption
    swap. send=True mails each to Kerry's recap inbox ONLY."""
    cases = [
        ("baseline-stateA", {}),
        ("ladder-1-bogey", {"gap": 1, "inside": False}),
        ("ladder-2-par", {"gap": 2, "inside": False}),
        ("ladder-3-birdie", {"gap": 3, "inside": False}),
        ("ladder-4-two-pars", {"gap": 4, "inside": False}),
        ("ladder-5-just", {"gap": 5, "inside": False}),
        ("ladder-6-plain", {"gap": 8.5, "inside": False}),
        ("ladder-7-inside", {"inside": True}),
        ("stateB", {"cta_state": "B"}),
        ("gross-suppressed", {"suppress_pc": True}),
        ("no-flight-caption", {"pc_no_flight": True, "suppress_pc": False}),
    ]
    out = []
    for label, ov in cases:
        r = build_chase_email(baseline_customer_id, send=send,
                              overrides=ov, db_path=db_path)
        out.append({"case": label, "ok": r.get("ok"),
                    "sent": r.get("sent"), "subject": r.get("subject"),
                    "state": r.get("state"), "gap": r.get("gap"),
                    "suppress_pc": r.get("suppress_pc"),
                    "unfilled_slots": r.get("unfilled_slots"),
                    "error": r.get("error")})
    return out
