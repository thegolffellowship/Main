# Lone Star Cup Cart Signs: the template of record

Kerry approved design **3e** (design-claude, mailbox #1463, 2026-10-08). Kerry asked on 10/8: "Review tracker for full direction on Cart Signs, just for the LONE STAR CUP. Save them as a template".

This sign is for the **Lone Star Cup only**. Regular TGF events keep the #893 cart sign (`templates/cart_signs.html`).

## Where it lives

| What | Path |
|---|---|
| Template (Jinja, production) | `templates/cup_cart_signs.html` |
| Data | `app.py` `cup_cart_signs_data(event_id, preview, session)` |
| Group rows | `email_parser/score_entry.py` `cup_sign_sheets` |
| Route (manager) | `/events/<id>/cup-cart-signs`. Add `?preview=1&session=sat-am\|sat-pm\|sun` to print from the demo rounds. |
| Logo | `static/lsc-logo-dark.png`: the white-border logo with THE HIDEOUT, 2000×1651, transparent background, sha256 423d3750… |
| Sample renders | `docs/claude/screenshots/lsc-preview/30-cart-sign-*.png`, `cup-cart-signs-*.pdf` |
| Design source | Claude Design `TGF LSC Cart Signs.dc.html` option 3e; `handoffs/lsc-cart-signs/lsc-cart-sign-production.html` |
| Guard | `test_lsc_preview.py` (cart-sign checks) |

## 1. Page

- US Letter portrait, 2 signs per sheet, `@page { size: letter; margin: 0 }`.
- Each sign is exactly half the sheet: 8.5in × 5.5in (816×528px).
- A 1px dashed #D1D5DB cut line sits at 5.5in.
- Order: by group, cart A (riders 1–2) and then cart B (riders 3–4). An odd final cart leaves the bottom half blank.
- `print-color-adjust: exact` so the bands print.
- No third or spill-over page. The print rule `.sheet { margin: 0 }` must come after the screen `.sheet` rule; otherwise the screen 24px gap adds a blank last page.
- No GGID and no course line. The logo carries "The Hideout".

## 2. Navy band (top, full bleed)

- 250px tall, background `--lsc-navy` #002855. Padding: 20px top and bottom, 40px left, 44px right.
- **Logo:** 240px tall with −15px/−14px margins, which cancel the PNG's transparent edge. That leaves 40px of navy on each side of the artwork.
- **Divider:** a 4px dotted #9DB4D6 line, inset 6px top and bottom.
- **Tee time and hole column:**
  - "TEE TIME" label: Bitter 700 14px, letter-spacing 3px, #9DB4D6.
  - Time: Bitter 800 54px, white.
  - Rule: 3px #E87C3E, 60% wide, 12px margin.
  - "HOLE" label: same as the TEE TIME label.
  - Hole: Bitter 800 54px, #E87C3E.
- **QR:**
  - A white 116px tile with an 8px radius and 8px quiet zone, set 8px from the time column.
  - A 100px QR inside it, navy #002855 on white, error correction M.
  - Caption "SCAN TO KEEP SCORE", 9px 700, letter-spacing 1px, #9DB4D6.

## 3. Team band

- 58px tall in the team color.
- Content: a 48×3px white rule, "TEAM {NAME}" in Bitter 800 26px with letter-spacing 4px, white, then a second 48×3px white rule. The gap between them is 14px.
- Team colors (`LSC_TEAM_COLORS` in app.py):
  - Austin #BF5700.
  - San Antonio #44596B. This is CD's starting value; other SA surfaces use #4B6274, and Kerry may restyle.
- Every new chapter needs a color before it can print. A team without one is listed under problems and is never silently greyed.

## 4. Names

- The white area is 220px, centred, with 32px side padding.
- Bitter 64px, line-height 1.04, one rider per line.
- First name weight 600; LAST NAME weight 800, uppercase.
- Fit rule (`fitNames()` runs on fonts ready and on beforeprint):
  - A line wider than 752px steps that sign's names down 2px at a time, to a 48px minimum.
  - Below 48px the first name ellipses.
  - Names never wrap.
- A 1-rider cart prints one line, still centred.

## 5. Data bindings

Nothing is typed in the print layer.

- **Tee time and hole:** from the score-entry group (`se_groups` tee time and `start_hole`).
- **Riders:** from `customers` by customer_id. Never join on name.
- **Team:** the cart's LSC side from the match.
- **QR:** the group's scorer link. It shows only when the event is in `score_entry_events` AND the `score_entry_qr` dial is on. With the QR off, the time column takes the space and a screen-only toolbar warns. Preview always shows the QR.

## 6. Acceptance (checked 2026-10-08, v2.525.41)

1. Two signs per sheet and no spill-over page: sat-am prints 14 signs on 7 pages; sun prints 28 signs on 14 pages.
2. The navy and team bands print edge to edge in print-to-PDF.
3. The logo has equal navy on its left and right.
4. A QR scan from a printed sheet is still to be confirmed by hand.
5. The longest roster name fits at or above 48px without wrapping (fit rule).
6. A test render goes to Kerry.
