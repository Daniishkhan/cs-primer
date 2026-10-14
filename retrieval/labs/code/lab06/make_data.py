"""make_data.py: writes pages.json and truth.json, the synthetic OCR fixtures of Lab 6. GIVEN.

You do not need to run this; the two JSON files are already in the folder. It is here so you can
see exactly how the pages were made, and change them (python3 make_data.py rewrites both files).

The pages are a four-page "Annual Review" of an invented council: a two-column page with a
heading across both columns, a page with a table, a single-column page with sections and a
numbered list, and a form. Each page has a running header and a page-number footer. The script
is a tiny typesetter: it lays words out with a fixed character width, then plays the part of an
OCR engine: every word gets a box, a transcription that is sometimes wrong, and a confidence
that is only loosely related to whether it is wrong. Everything is seeded.

Coordinates are IMAGE coordinates in points on a 612 x 792 page: x grows to the right and y
grows DOWNWARDS (chapter 18's PDF listings used y upwards; OCR engines report pixels, top
left first). A box is [x0, y0, x1, y1] = [left, top, right, bottom].
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 612, 792
MARGIN_X = 54
SEED = 20261014

SIZE = {"title": 22, "h1": 14, "h2": 12, "p": 10, "li": 10, "cap": 10}
BEFORE = {"title": 0, "h1": 14, "h2": 10, "p": 6, "li": 6, "cap": 10}   # space above an item
LINE_GAP = {"title": 4, "h1": 3, "h2": 3, "p": 2.4, "li": 2.4, "cap": 2.4}

# characters an OCR engine confuses, and what it writes instead
CONFUSE = {"O": "0", "0": "O", "l": "1", "1": "l", "I": "l", "m": "rn", "e": "c", "a": "o",
           "5": "S", "S": "5", "u": "v", "h": "b", "B": "8", "g": "q"}

HEADER = "Harbourside Council | Annual Review 2026"

TEXT = {
    1: [
        ("title", "Annual Review 2026"),
        ("h1", "1. Service performance"),
        ("p", "Harbourside Council handled more requests in 2026 than in any previous year, and most of "
              "them were resolved without a second contact. This review sets out what the council delivered, "
              "where it fell short and what residents can expect next year. Figures come from the council's "
              "case management system and cover the twelve months to 31 March."),
        ("p", "Household waste collections ran to schedule on 97 days in every 100. The remaining delays were "
              "caused by two weeks of flooding in January, when the main depot on Quay Road was closed and "
              "crews worked from a temporary yard. Residents were told by text message on the morning of "
              "each affected route, and no collection was missed for more than three days."),
        ("h2", "1.1 Waste and recycling"),
        ("p", "The recycling rate rose from 41 per cent to 46 per cent after the introduction of weekly food "
              "waste collections. Contamination, the share of recycling loads rejected at the sorting plant, "
              "fell by a third. The council expects the new rate to hold, although it depends on residents "
              "continuing to separate glass and food waste correctly."),
        ("p", "Garden waste collections remain a paid service. Almost 18,000 households subscribed this year, "
              "and the subscription fee will stay at 52 pounds for 2027. Subscribers who move house can "
              "transfer the service by telephone or online."),
        ("h2", "1.2 Parking and transport"),
        ("p", "Residents' parking permits are now issued online in an average of two working days. The "
              "infra~structure behind the system was replaced in October, and the old paper process closes at "
              "the end of the year. Visitors can still buy daily vouchers from any library or from the "
              "council's website."),
    ],
    2: [
        ("h1", "2. Requests handled"),
        ("p", "The council recorded more than one million three hundred thousand requests across its four "
              "busiest services. Waste collection and parking both grew, while library loans fell for the "
              "second year running as more residents moved to the digital collection."),
        ("cap", "Table 1: Requests handled by service, in thousands"),
        # the table sits here (see TABLE_ROWS)
        ("p", "Planning applications are few but slow to handle, which is why they are counted separately "
              "from the other services. Every figure in the table is rounded to one decimal place, so the "
              "total may differ from the sum of the rows by a tenth."),
    ],
    3: [
        ("h1", "3. Contact and complaints"),
        ("p", "Most problems are put right by the team that caused them, so the quickest route is to contact "
              "that team directly by telephone or through the online form. If you are not satisfied with the "
              "reply you can make a formal complaint, and the council will acknowledge it within five working "
              "days."),
        ("h2", "3.1 Making a complaint"),
        ("p", "A complaint should say what went wrong, when it happened and what you would like the council "
              "to do about it. Include any reference number you were given, because it lets the case officer "
              "find the earlier correspondence at once. The steps are:"),
        ("li", "1. Write to the service manager, giving your name and a reference number."),
        ("li", "2. Wait ten working days for a full written reply from that manager."),
        ("li", "3. If you are still unhappy, ask for your complaint to be escalated."),
        ("h2", "3.2 Escalation"),
        ("p", "An escalated complaint is reviewed by a director who was not involved in the original decision. "
              "The director will write to you within twenty working days. If the outcome does not resolve "
              "the matter, you may take it to the independent ombudsman, whose service is free."),
    ],
    4: [
        ("h1", "4. Parking permit application"),
        ("p", "Complete every field in capital letters and attach proof of address. Fields with tick boxes "
              "accept one choice, and the council returns incomplete forms unprocessed."),
    ],
}

# Table 1: (row, col, colspan, text). Numbers are right-aligned at the column's right edge.
TABLE_CELLS = [
    (0, 1, 2, "Requests (thousands)"),
    (1, 0, 1, "Service"), (1, 1, 1, "2025"), (1, 2, 1, "2026"), (1, 3, 1, "Change %"),
    (2, 0, 1, "Waste collection"), (2, 1, 1, "412.6"), (2, 2, 1, "431.0"), (2, 3, 1, "+4.5"),
    (3, 0, 1, "Parking permits"), (3, 1, 1, "58.3"), (3, 2, 1, "61.9"), (3, 3, 1, "+6.2"),
    (4, 0, 1, "Library loans"), (4, 1, 1, "903.4"), (4, 2, 1, "871.2"), (4, 3, 1, "-3.6"),
    (5, 0, 1, "Planning applications"), (5, 1, 1, "7.8"), (5, 2, 1, "8.4"), (5, 3, 1, "+7.7"),
    (6, 0, 1, "Total"), (6, 1, 1, "1,382.1"), (6, 2, 1, "1,372.5"), (6, 3, 1, "-0.7"),
]
COL_LEFT0 = 54
COL_RIGHT = {1: 330, 2: 420, 3: 510}

# The form: (label, value, pattern). The pattern says how the value sits next to the label.
FORM = [
    ("Full name", "Maria Okafor", "inline"),            # "Full name: Maria Okafor" on one line
    ("Date of birth", "14 March 1987", "right"),        # label left, value on the same row, far right
    ("Address", "12 Quay Road, Harbourside HA1 4QR", "below"),   # value on the line under the label
    ("Vehicle registration", "KX19 ZTR", "right"),
    ("Permit zone", "C4", "right"),
    ("Email", "", "blank"),                             # left empty on purpose
    ("Permit type", "Resident", "choice"),              # tick boxes: Resident / Visitor / Business
]
CHOICES = ["Resident", "Visitor", "Business"]

# Deliberate OCR slips that the lab's checks rely on: (page, ground-truth word) -> (read as, confidence)
FORCED = {
    (4, "March"): ("Marcb", 0.55),        # low confidence, wrong: a review queue catches it
    (4, "KX19"): ("KXl9", 0.93),          # HIGH confidence, wrong: only a validator catches it
    (3, "Council"): ("Councii", 0.71),    # a noisy running header: boilerplate matching must be fuzzy
    (2, "871.2"): ("87l.2", 0.64),        # one wrong digit in the table
}
NOISE_P = {"body": 0.06, "table": 0.0, "clean": 0.0}


def ocr(rng, gt, p):
    """Play the OCR engine: return (text read, confidence)."""
    text = gt
    if len(gt) >= 3 and rng.random() < p:
        spots = [i for i, ch in enumerate(gt) if ch in CONFUSE]
        if spots:
            i = rng.choice(spots)
            text = gt[:i] + CONFUSE[gt[i]] + gt[i + 1:]
    if text != gt:
        conf = rng.gauss(0.93, 0.02) if rng.random() < 0.12 else rng.gauss(0.60, 0.12)
    else:
        conf = rng.gauss(0.72, 0.05) if rng.random() < 0.03 else rng.gauss(0.965, 0.022)
    return text, round(max(0.2, min(0.995, conf)), 3)


def wrap(text, width_chars):
    """Greedy wrap. A '~' marks a point where a word may be broken with a hyphen."""
    lines, cur, cur_len = [], [], 0
    queue = text.split()
    while queue:
        tok = queue.pop(0)
        full = tok.replace("~", "")
        need = len(full) + (1 if cur else 0)
        if cur_len + need <= width_chars:
            cur.append(full)
            cur_len += need
            continue
        if "~" in tok:
            parts = tok.split("~")
            for cut in range(len(parts) - 1, 0, -1):
                head = "".join(parts[:cut]) + "-"
                if cur_len + (1 if cur else 0) + len(head) <= width_chars:
                    cur.append(head)
                    lines.append(cur)
                    cur, cur_len = [], 0
                    queue.insert(0, "~".join(parts[cut:]))
                    break
            else:
                lines.append(cur)
                cur, cur_len = [], 0
                queue.insert(0, tok)
        else:
            lines.append(cur)
            cur, cur_len = [], 0
            queue.insert(0, tok)
    if cur:
        lines.append(cur)
    return lines


class Page:
    def __init__(self, number, rng):
        self.number, self.rng = number, rng
        self.words = []            # dicts: gt, box, p
        self.body_truth = []       # item texts in reading order (truth for the page CER)

    def put_line(self, tokens, x, y, size, p, align="left", span=None):
        cw, h = 0.6 * size, 1.2 * size
        total = (sum(len(t) for t in tokens) + len(tokens) - 1) * cw
        if align == "centre":
            x = (W - total) / 2
        elif align == "right":
            x = x - total
        cur = x
        for t in tokens:
            jx, jy = self.rng.uniform(-0.5, 0.5), self.rng.uniform(-0.4, 0.4)
            box = [round(cur + jx, 1), round(y + jy, 1), round(cur + len(t) * cw + jx, 1), round(y + h + jy, 1)]
            self.words.append({"gt": t, "box": box, "p": p})
            cur += (len(t) + 1) * cw
        return h

    def flow(self, items, columns, y_top, y_bottom):
        """Lay items into columns [(x, width), ...], filling each to y_bottom before the next."""
        col, y = 0, y_top
        first_in_col = True
        for kind, text in items:
            size = SIZE[kind]
            h = 1.2 * size
            lines = wrap(text, int(columns[col][1] / (0.6 * size))) if kind not in ("title", "h1", "h2", "cap") \
                else [text.split()]
            y += 0 if first_in_col else BEFORE[kind]
            for ln in lines:
                if y + h > y_bottom:
                    col += 1
                    y, first_in_col = y_top, True
                x, width = columns[col]
                p = NOISE_P["body"] if kind in ("p", "li", "cap") else NOISE_P["clean"]
                self.put_line(ln, x, y, size, p)
                y += h + LINE_GAP[kind]
                first_in_col = False
            self.body_truth.append(text.replace("~", ""))
        return y


def build():
    rng = random.Random(SEED)
    pages, truth_words = [], {}
    truth = {"pages": [], "tables": [], "forms": [], "outline": [], "sections": []}
    for n in (1, 2, 3, 4):
        pg = Page(n, random.Random(SEED + n))
        regions = []
        # running header and footer (clean, tiny)
        pg.put_line(HEADER.split(), MARGIN_X, 28, 9, 0.0)
        pg.put_line(f"Page {n} of 4".split(), 0, 754, 9, 0.0, align="centre")
        full = [(MARGIN_X, W - 2 * MARGIN_X)]
        if n == 1:
            pg.flow(TEXT[1][:2], full, 72, 140)
            # the title is wider than a heading: re-flow the first two items on separate rows
            pg.flow(TEXT[1][2:], [(MARGIN_X, 240), (318, 240)], 170, 590)
        elif n == 2:
            y = pg.flow(TEXT[2][:3], full, 80, 400)
            # the table
            ty = y + 8
            top = ty
            cw = 6.0
            row_y = {}
            for r, c, cs, text in TABLE_CELLS:
                row_y.setdefault(r, ty + r * 19)
            for r, c, cs, text in TABLE_CELLS:
                toks = text.split()
                width = (sum(len(t) for t in toks) + len(toks) - 1) * cw
                if c == 0:
                    x = COL_LEFT0
                elif cs == 1:
                    x = COL_RIGHT[c] - width
                else:
                    centre = (COL_RIGHT[c] - 42 + COL_RIGHT[c + cs - 1]) / 2
                    x = centre - width / 2
                pg.put_line(toks, x, row_y[r], 10, NOISE_P["table"])
            bottom = row_y[6] + 12
            regions.append({"type": "table", "bbox": [COL_LEFT0 - 4, round(top - 4, 1), 514, round(bottom + 4, 1)]})
            pg.flow(TEXT[2][3:], full, bottom + 24, 700)
            # the caption belongs before the table in reading order: already in TEXT[2][:3]
            pg.body_truth = [t for t in pg.body_truth]
        elif n == 3:
            pg.flow(TEXT[3], full, 80, 700)
        else:
            pg.flow(TEXT[4], full, 80, 400)
            y = 190
            top = y
            for label, value, pattern in FORM:
                lt = label.split()
                if pattern == "inline":
                    pg.put_line(lt[:-1] + [lt[-1] + ":", value.split()[0], value.split()[1]], MARGIN_X, y, 10, 0.0)
                    y += 40
                elif pattern == "right":
                    pg.put_line(lt[:-1] + [lt[-1] + ":"] if label == "Date of birth" else lt, MARGIN_X, y, 10, 0.0)
                    pg.put_line(value.split(), 250, y, 10, 0.0)
                    y += 40
                elif pattern == "below":
                    pg.put_line(lt, MARGIN_X, y, 10, 0.0)
                    pg.put_line(value.split(), MARGIN_X, y + 16, 10, 0.0)
                    y += 56
                elif pattern == "blank":
                    pg.put_line([label + ":"], MARGIN_X, y, 10, 0.0)
                    y += 40
                else:
                    toks = lt[:-1] + [lt[-1] + ":"]
                    for opt in CHOICES:
                        toks += ["☒" if opt == value else "☐", opt]
                    pg.put_line(toks, MARGIN_X, y, 10, 0.0)
                    y += 40
            regions.append({"type": "form", "bbox": [MARGIN_X - 4, top - 6, 400, round(y - 12, 1)]})
        pages.append((n, pg, regions))
        truth["pages"].append({"page": n, "body": " ".join(pg.body_truth), "boilerplate": [HEADER, f"Page {n} of 4"]})

    out_pages = []
    for n, pg, regions in pages:
        words = []
        seen = set()
        for i, w in enumerate(pg.words):
            wid = f"p{n}w{i:04d}"
            gt = w["gt"]
            text, conf = ocr(rng, gt, w["p"])
            key = (n, gt)
            if key in FORCED and key not in seen:
                text, conf = FORCED[key]
                seen.add(key)
            words.append({"id": wid, "text": text, "conf": conf, "box": w["box"]})
            truth_words[wid] = gt
        random.Random(SEED * 7 + n).shuffle(words)     # the engine's stream order is not reading order
        out_pages.append({"page": n, "words": words, "regions": regions})

    # ground truth for the table, the form and the outline
    bbox = out_pages[1]["regions"][0]["bbox"]
    truth["tables"].append({"page": 2, "cells": [list(c) for c in TABLE_CELLS]})
    truth["forms"].append({"page": 4, "fields": {
        "full_name": "Maria Okafor", "date_of_birth": "14 March 1987",
        "address": "12 Quay Road, Harbourside HA1 4QR", "vehicle_registration": "KX19 ZTR",
        "permit_zone": "C4", "email": None, "permit_type": ["Resident"]}})
    for n in (1, 2, 3, 4):
        for kind, text in TEXT[n]:
            if kind in ("title", "h1", "h2"):
                level = {"title": 0, "h1": 1, "h2": 2}[kind]
                truth["outline"].append({"level": level, "title": text, "page": n})
    # section bodies: the paragraphs between headings, joined by single spaces
    secs, cur = [], None
    for n in (1, 2, 3, 4):
        for kind, text in TEXT[n]:
            if kind in ("title", "h1", "h2"):
                cur = {"title": text, "body": []}
                secs.append(cur)
            elif cur is not None:
                cur["body"].append(text.replace("~", ""))
    truth["sections"] = [{"title": s["title"], "body": " ".join(s["body"])} for s in secs]
    # the table caption moves nothing; the table words are not part of any section body
    truth["words"] = truth_words
    with open(os.path.join(HERE, "pages.json"), "w", encoding="utf-8") as fh:
        json.dump({"page_width": W, "page_height": H, "pages": out_pages}, fh, ensure_ascii=False)
    with open(os.path.join(HERE, "truth.json"), "w", encoding="utf-8") as fh:
        json.dump(truth, fh, ensure_ascii=False, indent=1)
    n_words = sum(len(p["words"]) for p in out_pages)
    print(f"wrote pages.json ({n_words} words on 4 pages) and truth.json")


if __name__ == "__main__":
    build()
