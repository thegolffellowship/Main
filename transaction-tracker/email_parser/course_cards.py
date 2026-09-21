"""Course cards supplied by Kerry from the club's own Golf Genius setup.

Kerry 2026-09-15, after the s9.23 tee-nine work: "That 'The course
card…' note WILL NOT fly. We can never do that. We need to get the
calculations right." — then sent the Avery Ranch and Cedar Creek cards
screen by screen. This is that data, typed once, in the repo, so it can
be re-applied, reviewed and diffed rather than living in a chat.

SHAPE, per tee:
    name    the club's own tee name, tee ORDER prefix included
    r18/s18 the 18-hole course rating / slope
    front   (rating, slope) for holes 1-9
    back    (rating, slope) for holes 10-18
    par     18 pars, holes 1-18
    si      18 stroke indexes, holes 1-18
    yards   18 yardages, holes 1-18

A tee whose only difference from another is its ratings (a ladies'
rating of the same physical tee) still gets its own entry, because that
is how the club rates it and how Golf Genius files it.
"""

# ── Avery Ranch Golf Club (course_id 22363), Austin ───────────────────
_AR_PAR = [4, 4, 5, 4, 5, 3, 4, 3, 4,  5, 3, 4, 3, 5, 5, 4, 3, 4]
_AR_SI = [15, 13, 9, 5, 1, 11, 3, 17, 7,  12, 4, 6, 14, 8, 10, 18, 16, 2]

AVERY_RANCH = {
    "course_id": 22363,
    "course": "Avery Ranch Golf Club",
    "source": "Golf Genius course setup, supplied by Kerry 2026-09-15",
    "tees": [
        {"name": "0 - Black Tee", "r18": 74.7, "s18": 138,
         "front": (37.7, 145), "back": (37.0, 130),
         "par": _AR_PAR, "si": _AR_SI,
         "yards": [377, 404, 546, 475, 597, 212, 396, 204, 444,
                   561, 227, 428, 161, 517, 577, 332, 186, 477]},
        {"name": "1 - Blue Tee", "r18": 71.0, "s18": 131,
         "front": (36.0, 139), "back": (35.0, 123),
         "par": _AR_PAR, "si": _AR_SI,
         "yards": [326, 355, 500, 394, 553, 188, 359, 181, 384,
                   480, 204, 352, 140, 477, 488, 300, 147, 400]},
        {"name": "2 - White Tee", "r18": 68.9, "s18": 125,
         "front": (34.9, 133), "back": (34.0, 116),
         "par": _AR_PAR, "si": _AR_SI,
         "yards": [288, 330, 478, 385, 495, 150, 339, 146, 356,
                   469, 190, 324, 134, 440, 436, 267, 126, 371]},
        {"name": "3 - Green Tee", "r18": 65.4, "s18": 118,
         "front": (33.1, 126), "back": (32.3, 109),
         "par": _AR_PAR, "si": _AR_SI,
         "yards": [265, 320, 304, 351, 403, 133, 316, 123, 337,
                   419, 146, 302, 69, 399, 388, 243, 109, 297]},
        # Same physical tee as Green, rated for women — and hole 7 plays
        # from a forward box (210 vs 316), which is why the front totals
        # differ by exactly that.
        {"name": "3 - Green (L) Tee", "r18": 69.8, "s18": 125,
         "front": (35.3, 132), "back": (34.5, 117),
         "par": _AR_PAR, "si": _AR_SI,
         "yards": [265, 320, 304, 351, 403, 133, 210, 123, 337,
                   419, 146, 302, 69, 399, 388, 243, 109, 297]},
    ],
}

# ── Cedar Creek Golf Course (course_id 35670), San Antonio ────────────
_CC_PAR = [4, 4, 4, 5, 3, 4, 3, 4, 5,  4, 4, 4, 4, 5, 4, 4, 3, 4]
_CC_SI = [13, 3, 9, 17, 15, 1, 7, 5, 11,  12, 16, 2, 6, 18, 14, 10, 8, 4]
# The ladies' rating carries its OWN stroke index — the holes are ranked
# for a different game off the same boxes.
_CC_SI_L = [11, 7, 1, 13, 17, 5, 15, 9, 3,  8, 18, 4, 2, 14, 16, 6, 12, 10]
_CC_RED_YARDS = [301, 324, 279, 442, 119, 322, 133, 309, 480,
                 312, 272, 334, 313, 429, 300, 297, 172, 301]

CEDAR_CREEK = {
    "course_id": 35670,
    "course": "Cedar Creek Golf Course",
    "source": "Golf Genius course setup, supplied by Kerry 2026-09-15",
    "tees": [
        {"name": "0 - Blue Tee", "r18": 74.5, "s18": 136,
         "front": (37.2, 132), "back": (37.3, 139),
         "par": _CC_PAR, "si": _CC_SI,
         "yards": [396, 439, 350, 559, 187, 412, 202, 430, 565,
                   408, 362, 415, 400, 514, 358, 403, 217, 443]},
        {"name": "1 - White Tee", "r18": 71.4, "s18": 125,
         "front": (35.5, 126), "back": (35.9, 123),
         "par": _CC_PAR, "si": _CC_SI,
         "yards": [362, 406, 327, 494, 159, 372, 180, 390, 546,
                   387, 329, 388, 373, 487, 347, 371, 200, 389]},
        {"name": "2 - Gold Tee", "r18": 69.4, "s18": 118,
         "front": (34.8, 116), "back": (34.6, 119),
         "par": _CC_PAR, "si": _CC_SI,
         "yards": [344, 380, 304, 469, 137, 346, 156, 368, 531,
                   357, 304, 358, 347, 449, 321, 345, 185, 324]},
        {"name": "3 - Red Tee", "r18": 66.7, "s18": 112,
         "front": (33.4, 109), "back": (33.3, 115),
         "par": _CC_PAR, "si": _CC_SI, "yards": _CC_RED_YARDS},
        {"name": "3 - Red (L) Tee", "r18": 72.9, "s18": 120,
         "front": (36.4, 124), "back": (36.5, 116),
         "par": _CC_PAR, "si": _CC_SI_L, "yards": _CC_RED_YARDS},
    ],
}

COURSE_CARDS = {
    "avery": AVERY_RANCH,
    "avery ranch": AVERY_RANCH,
    "22363": AVERY_RANCH,
    "cedar": CEDAR_CREEK,
    "cedar creek": CEDAR_CREEK,
    "35670": CEDAR_CREEK,
}

# ── Forest Creek Golf Club (course_id 29522), Austin ──────────────────
_FC_PAR = [4, 4, 5, 4, 4, 3, 5, 3, 4,  4, 4, 5, 4, 3, 4, 5, 3, 4]
_FC_SI = [15, 1, 13, 3, 5, 17, 9, 7, 11,  6, 16, 14, 10, 8, 4, 12, 18, 2]
_FC_SI_L = [15, 1, 11, 3, 5, 17, 7, 9, 13,  6, 14, 16, 8, 10, 4, 12, 18, 2]

FOREST_CREEK = {
    "course_id": 29522,
    "course": "Forest Creek Golf Club",
    "source": "Golf Genius course setup, supplied by Kerry 2026-09-15",
    "tees": [
        {"name": "0 - Gold Tee", "r18": 74.8, "s18": 139,
         "front": (37.2, 140), "back": (37.6, 137),
         "par": _FC_PAR, "si": _FC_SI,
         "yards": [385, 410, 535, 430, 395, 180, 535, 190, 400,
                   422, 398, 550, 380, 196, 469, 541, 156, 438]},
        {"name": "1 - Blue Tee", "r18": 72.2, "s18": 132,
         "front": (35.9, 133), "back": (36.3, 131),
         "par": _FC_PAR, "si": _FC_SI,
         "yards": [347, 394, 503, 387, 352, 158, 471, 165, 380,
                   387, 362, 509, 336, 165, 437, 519, 140, 410]},
        {"name": "2 - White Tee", "r18": 70.4, "s18": 125,
         "front": (35.2, 125), "back": (35.2, 125),
         "par": _FC_PAR, "si": _FC_SI,
         "yards": [333, 384, 476, 347, 315, 148, 461, 138, 350,
                   343, 348, 470, 320, 145, 417, 484, 112, 390]},
        {"name": "3 - Green Tee", "r18": 68.5, "s18": 120,
         "front": (34.3, 119), "back": (34.2, 121),
         "par": _FC_PAR, "si": _FC_SI,
         "yards": [297, 312, 457, 342, 304, 138, 434, 128, 315,
                   329, 315, 431, 309, 135, 374, 439, 109, 374]},
        # Forest Creek numbers its ladies' tee 4, not 3 (L) — Kerry's
        # reminder covers both: "3 (L) - Forward (Ladies), OR 4 (L) -
        # Forward (Ladies)".
        {"name": "4 - Red (L) Tee", "r18": 68.5, "s18": 121,
         "front": (34.1, 121), "back": (34.4, 120),
         "par": _FC_PAR, "si": _FC_SI_L,
         "yards": [281, 305, 408, 295, 242, 108, 380, 101, 264,
                   268, 307, 363, 287, 119, 303, 356, 82, 311]},
    ],
}

COURSE_CARDS.update({
    "forest": FOREST_CREEK,
    "forest creek": FOREST_CREEK,
    "29522": FOREST_CREEK,
})
