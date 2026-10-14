"""Lab 6: a document understanding pipeline, from OCR boxes to text, sections, a table and a form.

Input is what an OCR engine hands you (chapters 18 to 20): words, each with a box and a
confidence, in no useful order. Output is what retrieval wants (chapter 14): reading-ordered
text with the running header and footer removed, paragraphs, a section outline, a table as a
grid of cells and a form as typed fields. Everything is measured against the truth the fixtures
were made from, using the character error rate of chapter 19.

Notation, as in chapters 18 and 20:

    word    {"id", "text", "conf", "box": [x0, y0, x1, y1]}   image coordinates, y grows DOWNWARDS
    line    {"text", "bbox", "conf", "height", "words"}       made by make_line()
    item    anything with a "bbox" key (a line, a paragraph); xy_cut orders items
    cell    (row, col, colspan, text)                         table cells, as in chapter 20

What is GIVEN: loading, make_line, the naive baseline, region splitting, the table scorer, the form
schema and validators, and the printing at the bottom. What YOU write is marked TODO:

    1  edit_distance, cer
    2  group_lines, xy_cut
    3  find_boilerplate, strip_boilerplate
    4  lines_to_paragraphs, detect_sections
    5  build_table
    6  extract_form, review_flags

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import json
import math
import os
import re
import statistics
import unicodedata
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# GIVEN: fixtures, geometry helpers, baselines
# =============================================================================
def load_fixtures():
    """(pages, truth): pages = list of {"page", "words", "regions"}, truth = the ground truth."""
    with open(os.path.join(HERE, "pages.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    with open(os.path.join(HERE, "truth.json"), encoding="utf-8") as fh:
        truth = json.load(fh)
    return data["pages"], truth, data["page_height"]


def make_line(words):
    """GIVEN: build a line dict from a list of word dicts (any order)."""
    ws = sorted(words, key=lambda w: w["box"][0])
    x0, y0 = min(w["box"][0] for w in ws), min(w["box"][1] for w in ws)
    x1, y1 = max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)
    return {"text": " ".join(w["text"] for w in ws), "bbox": [x0, y0, x1, y1],
            "conf": min(w["conf"] for w in ws), "height": y1 - y0, "words": ws}


def naive_order(items):
    """GIVEN: the baseline of chapter 18, sort by top edge then left edge."""
    return sorted(items, key=lambda it: (it["bbox"][1], it["bbox"][0]))


def split_regions(words, regions):
    """GIVEN: words whose centre lies in a detected region (table, form) versus the rest."""
    inside = {r["type"]: [] for r in regions}
    rest = []
    for w in words:
        cx, cy = (w["box"][0] + w["box"][2]) / 2, (w["box"][1] + w["box"][3]) / 2
        for r in regions:
            x0, y0, x1, y1 = r["bbox"]
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                inside[r["type"]].append(w)
                break
        else:
            rest.append(w)
    return rest, inside


def zone_of(line, page_height, margin=0.08):
    """GIVEN: 'top' or 'bottom' if the whole line sits in that margin band of the page, else None."""
    if line["bbox"][3] <= margin * page_height:
        return "top"
    if line["bbox"][1] >= (1 - margin) * page_height:
        return "bottom"
    return None


def shape(text):
    """GIVEN: a line's shape for repeat detection: lower case, digit runs become '#', one space."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", text.lower())).strip()


NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+\S")      # GIVEN: "1. Intro", "2.3 Scope"


def cell_scores(pred, gold):
    """GIVEN: structure F1 (row, col, colspan) and exact F1 (also the text) of two cell sets."""
    def f1(a, b):
        tp = len(a & b)
        p, r = tp / len(a) if a else 0.0, tp / len(b) if b else 0.0
        return 2 * p * r / (p + r) if p + r else 0.0
    pred, gold = {tuple(c) for c in pred}, {tuple(c) for c in gold}
    return {"structure_f1": f1({c[:3] for c in pred}, {c[:3] for c in gold}), "exact_f1": f1(pred, gold)}


FORM_SCHEMA = {                                          # GIVEN: the contract with downstream code
    "full_name":            {"label": "Full name",            "kind": "text",   "required": True},
    "date_of_birth":        {"label": "Date of birth",        "kind": "text",   "required": True},
    "address":              {"label": "Address",              "kind": "text",   "required": True},
    "vehicle_registration": {"label": "Vehicle registration", "kind": "text",   "required": True},
    "permit_zone":          {"label": "Permit zone",          "kind": "text",   "required": True},
    "email":                {"label": "Email",                "kind": "text",   "required": False},
    "permit_type":          {"label": "Permit type",          "kind": "choice", "required": True},
}
TICKED, UNTICKED = "☒", "☐"                    # the glyphs this OCR engine writes for boxes


def _date_ok(v):
    try:
        datetime.strptime(v, "%d %B %Y")
        return True
    except ValueError:
        return False


VALIDATORS = {                                           # GIVEN: typed checks that ignore confidence
    "date_of_birth": _date_ok,
    "vehicle_registration": lambda v: re.fullmatch(r"[A-Z]{2}\d{2} [A-Z]{3}", v) is not None,
    "permit_zone": lambda v: re.fullmatch(r"[A-Z]\d{1,2}", v) is not None,
    "full_name": lambda v: re.fullmatch(r"[A-Za-z' -]+", v) is not None,
}


# =============================================================================
# Milestone 1: the character error rate
# =============================================================================
def normalise(text):
    """GIVEN: the normalisation policy, stated so a CER can be compared: NFKC, one space, trimmed."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def edit_distance(a, b):
    """Levenshtein distance between two strings: the fewest single-character insertions,
    deletions and substitutions that turn `a` into `b`.

        edit_distance("kitten", "sitting") -> 3        edit_distance("", "abc") -> 3
    """
    # Two rows of the dynamic-programming table are enough: row i only needs row i - 1.
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1,                  # delete ca
                           cur[j - 1] + 1,               # insert cb
                           prev[j - 1] + (ca != cb)))    # substitute (free if equal)
        prev = cur
    return prev[-1]


def cer(ref, hyp, normalise_text=True):
    """Character error rate: edit_distance(ref, hyp) / len(ref), after `normalise` if asked.

    Not a probability: it can exceed 1.0 when `hyp` has many insertions. An empty reference gives
    0.0 for an empty hypothesis and 1.0 otherwise (so the function never divides by zero).

        cer("abcd", "abxd") -> 0.25        cer("ab", "abcd") -> 1.0
    """
    if normalise_text:
        ref, hyp = normalise(ref), normalise(hyp)
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


# =============================================================================
# Milestone 2: lines and reading order
# =============================================================================
def group_lines(words, gap_factor=1.5):
    """Group words into lines. Two words are on one line if they overlap vertically by at least
    half the smaller height AND the horizontal gap between them is at most gap_factor times the
    taller height. The second condition is what keeps two columns apart: a gutter is wider than a
    word space.

    Returns lines (make_line dicts) sorted by top edge then left edge. The input order must not
    matter. Words closer than the gap limit chain: A joins B, B joins C.
    """
    lines = []                                           # each: {"words": [...], "x1", "y0", "y1"}
    for w in sorted(words, key=lambda w: (w["box"][0], w["box"][1])):
        x0, y0, x1, y1 = w["box"]
        h = y1 - y0
        best = None
        for ln in lines:
            overlap = min(y1, ln["y1"]) - max(y0, ln["y0"])
            if overlap < 0.5 * min(h, ln["y1"] - ln["y0"]):
                continue
            gap = x0 - ln["x1"]
            if gap <= gap_factor * max(h, ln["y1"] - ln["y0"]):
                best = ln
                break
        if best is None:
            lines.append({"words": [w], "x1": x1, "y0": y0, "y1": y1})
        else:
            best["words"].append(w)
            best["x1"] = max(best["x1"], x1)
            best["y0"], best["y1"] = min(best["y0"], y0), max(best["y1"], y1)
    return naive_order([make_line(ln["words"]) for ln in lines])


def _widest_gap(items, axis, min_gap):
    """The widest empty band along one axis. axis 0 = x (a vertical cut), 1 = y (a horizontal cut).
    Returns (gap, first_group, second_group); gap is 0 and the groups are None if no band is
    wider than min_gap."""
    s = sorted(items, key=lambda it: it["bbox"][axis])
    reach = s[0]["bbox"][axis + 2]
    best, at = 0.0, None
    for n, it in enumerate(s[1:], 1):
        gap = it["bbox"][axis] - reach
        if gap > best:
            best, at = gap, n
        reach = max(reach, it["bbox"][axis + 2])
    if at is None or best <= min_gap:
        return 0.0, None, None
    return best, s[:at], s[at:]


def xy_cut(items, min_gap=4.0):
    """Recursive XY-cut (Nagy and Seth, 1984; chapter 18). Find the widest empty band, horizontal
    or vertical; split there; recurse on each part. A horizontal cut puts the top part first, a
    vertical cut the left part first. If no band is wider than `min_gap`, fall back to
    naive_order. Every item appears exactly once, and the input order must not matter.
    """
    items = list(items)
    if len(items) <= 1:
        return items
    gx, lx, rx = _widest_gap(items, 0, min_gap)
    gy, ty, by = _widest_gap(items, 1, min_gap)
    if gx == 0.0 and gy == 0.0:
        return naive_order(items)
    first, second = (lx, rx) if gx > gy else (ty, by)    # cut along the widest whitespace first
    return xy_cut(first, min_gap) + xy_cut(second, min_gap)


# =============================================================================
# Milestone 3: running headers and footers
# =============================================================================
def find_boilerplate(pages_lines, page_height, margin=0.08, tol=0.15, min_share=0.5):
    """Find lines that repeat in the top or bottom margin across pages: running headers, footers,
    page numbers.

    pages_lines: one list of lines per page. A line is a candidate only if zone_of(...) is 'top'
    or 'bottom'. Candidates are compared by shape(text) (so 'Page 3 of 9' equals 'Page 4 of 9') and
    treated as the same line if cer(representative, candidate) <= tol, which tolerates a
    misread character. A cluster counts once per page and is boilerplate if it occurs on at least
    max(2, ceil(min_share * number of pages)) pages. One page has no evidence, so nothing is removed.

    Returns a list of (zone, shape) pairs, one per boilerplate cluster.
    """
    need = max(2, math.ceil(min_share * len(pages_lines)))
    clusters = []                                        # [zone, representative shape, set of pages]
    for p, lines in enumerate(pages_lines):
        for ln in lines:
            zone = zone_of(ln, page_height, margin)
            if zone is None:
                continue
            s = shape(ln["text"])
            for c in clusters:
                if c[0] == zone and cer(c[1], s) <= tol:
                    c[2].add(p)
                    break
            else:
                clusters.append([zone, s, {p}])
    return [(z, s) for z, s, pages in clusters if len(pages) >= need]


def strip_boilerplate(lines, boilerplate, page_height, margin=0.08, tol=0.15):
    """Return `lines` without those in a margin zone that match a boilerplate (zone, shape)
    within tol. A line in the middle of the page is never removed, whatever it says."""
    kept = []
    for ln in lines:
        zone = zone_of(ln, page_height, margin)
        s = shape(ln["text"])
        if zone is not None and any(z == zone and cer(b, s) <= tol for z, b in boilerplate):
            continue
        kept.append(ln)
    return kept


# =============================================================================
# Milestone 4: paragraphs and sections
# =============================================================================
TERMINAL = ".!?:"


def _join(prev, nxt):
    """Join two lines of one paragraph, undoing a line-end hyphenation: 'infra-' + 'structure'."""
    if prev.endswith("-") and len(prev) > 1 and prev[-2].isalpha() and nxt[:1].islower():
        return prev[:-1] + nxt
    return prev + " " + nxt


def lines_to_paragraphs(lines, gap_ratio=0.5):
    """Merge lines, already in reading order, into paragraphs: {"text", "bbox", "height", "n_lines"}.

    A new paragraph starts when
      * the gap above the line (its top minus the previous line's bottom) exceeds gap_ratio times
        the previous line's height, or
      * the line height differs from the previous one's by more than 15 per cent (a heading), or
      * the line is higher on the page than the previous one (a column break) AND the previous
        line ended a sentence (its text ends in . ! ? or :). A column break in the middle of a
        sentence continues the paragraph.
    Inside a paragraph, lines are joined with a space, except that a line-end hyphen after a
    letter, followed by a lower-case start, is removed and the two pieces fused.
    """
    paras = []
    prev = None
    for ln in lines:
        x0, y0, x1, y1 = ln["bbox"]
        new = prev is None
        if prev is not None:
            px0, py0, px1, py1 = prev["bbox"]
            ph = py1 - py0
            if y0 - py1 > gap_ratio * ph:
                new = True
            elif abs(ln["height"] - prev["height"]) > 0.15 * prev["height"]:
                new = True
            elif y0 < py0 and prev["text"].rstrip()[-1:] in TERMINAL:
                new = True
        if new:
            paras.append({"text": ln["text"], "bbox": list(ln["bbox"]), "height": ln["height"], "n_lines": 1})
        else:
            p = paras[-1]
            p["text"] = _join(p["text"], ln["text"])
            p["bbox"] = [min(p["bbox"][0], x0), min(p["bbox"][1], y0), max(p["bbox"][2], x1), max(p["bbox"][3], y1)]
            p["n_lines"] += 1
        prev = ln
    return paras


def body_height(paragraphs):
    """The typical text height: the median line height, counting each paragraph once per line."""
    heights = []
    for p in paragraphs:
        heights.extend([p["height"]] * p["n_lines"])
    return statistics.median(heights) if heights else 0.0


def detect_sections(paragraphs):
    """Turn the document's paragraphs (all pages, in order, each with a "page") into sections:
    [{"level", "title", "page", "text"}].

    A paragraph is a HEADING if it is one line, at most 12 words, does not end in . , or ;, and
      * its height is at least 1.8 times body_height -> level 0 (a title); or
      * it starts with a section number (NUMBERED): level = number of dot-separated parts
        ('1.' -> 1, '1.2' -> 2); or
      * its height is at least 1.25 times body_height -> level 1.
    Every other paragraph is body text of the current section; body paragraphs are joined by one
    space. Body text before the first heading goes in a section with level 0 and title ''.
    """
    bh = body_height(paragraphs)
    sections = []
    for p in paragraphs:
        text = p["text"]
        level = None
        if p["n_lines"] == 1 and len(text.split()) <= 12 and text.rstrip()[-1:] not in ".,;":
            m = NUMBERED.match(text)
            if p["height"] >= 1.8 * bh:
                level = 0
            elif m:
                level = len(m.group(1).split("."))
            elif p["height"] >= 1.25 * bh:
                level = 1
        if level is not None:
            sections.append({"level": level, "title": text, "page": p.get("page"), "text": ""})
        else:
            if not sections:
                sections.append({"level": 0, "title": "", "page": p.get("page"), "text": ""})
            cur = sections[-1]
            cur["text"] = (cur["text"] + " " + text).strip()
    return sections


# =============================================================================
# Milestone 5: a table from boxes
# =============================================================================
def build_table(words, min_gap=12.0, vote=0.7):
    """Rebuild a table's cell grid from word boxes (chapter 20's whitespace method).

    1. ROWS: cluster words into rows by vertical position (a word joins the row whose mean centre
       is within 0.6 of its height). Number the rows 0, 1, ... from the top.
    2. CELLS: in each row, sort by x and join consecutive words whose gap is below min_gap.
    3. COLUMNS: an x position is 'empty' in a row if no word of that row covers it. Mark x as
       empty overall if it is empty in at least `vote` of the rows. Every run of empty x at least
       min_gap wide (not touching the table's left or right edge) is a separator; use its centre.
       Separators cut the table into column strips numbered 0, 1, ...
    4. A cell's first column is the strip containing its left edge + 1; its last column is the
       strip containing its right edge - 1; colspan = last - first + 1.

    Returns [(row, col, colspan, text), ...] sorted.
    """
    if not words:
        return []
    # 1. rows
    rows = []                                            # each: {"cy": mean centre, "words": [...]}
    for w in sorted(words, key=lambda w: (w["box"][1] + w["box"][3]) / 2):
        cy, h = (w["box"][1] + w["box"][3]) / 2, w["box"][3] - w["box"][1]
        if rows and abs(cy - rows[-1]["cy"]) <= 0.6 * h:
            rows[-1]["words"].append(w)
            rows[-1]["cy"] = sum((v["box"][1] + v["box"][3]) / 2 for v in rows[-1]["words"]) / len(rows[-1]["words"])
        else:
            rows.append({"cy": cy, "words": [w]})
    # 2. cells in each row
    row_cells = []
    for r in rows:
        cells = []
        for w in sorted(r["words"], key=lambda w: w["box"][0]):
            x0, x1 = w["box"][0], w["box"][2]
            if cells and x0 - cells[-1]["x1"] < min_gap:
                cells[-1]["x1"] = max(cells[-1]["x1"], x1)
                cells[-1]["text"] += " " + w["text"]
            else:
                cells.append({"x0": x0, "x1": x1, "text": w["text"]})
        row_cells.append(cells)
    # 3. column separators from whitespace that most rows leave empty
    lo = int(math.floor(min(w["box"][0] for w in words)))
    hi = int(math.ceil(max(w["box"][2] for w in words)))
    empty = []
    for x in range(lo, hi + 1):
        blanks = sum(1 for cells in row_cells if not any(c["x0"] <= x <= c["x1"] for c in cells))
        empty.append(blanks >= vote * len(row_cells))
    seps, i = [], 0
    while i < len(empty):
        if empty[i]:
            j = i
            while j < len(empty) and empty[j]:
                j += 1
            if j - i >= min_gap and i > 0 and j < len(empty):
                seps.append(lo + (i + j - 1) / 2)
            i = j
        else:
            i += 1

    def strip(x):
        return sum(1 for s in seps if s < x)             # how many separators lie to the left of x
    # 4. place the cells
    out = []
    for r, cells in enumerate(row_cells):
        for c in cells:
            first, last = strip(c["x0"] + 1), strip(c["x1"] - 1)
            out.append((r, first, last - first + 1, c["text"]))
    return sorted(out)


# =============================================================================
# Milestone 6: a form into typed fields, and what to send to a person
# =============================================================================
def extract_form(lines, schema=FORM_SCHEMA):
    """Find each schema field's value among the form's lines (group_lines output).

    A field's LABEL is a line that starts with the schema label: compare the first len(label)
    characters of the line, lower-cased, with the lower-cased label using cer(...) <= 0.15, so a
    misread letter in a label still matches. Then the VALUE is, in this order:
      1. inline: the words of the same line after the label's words, if there are any
         ('Full name: Maria Okafor');
      2. to the right: the nearest other line that overlaps the label vertically by at least half
         the label's height and starts at or after the label's right edge ('Date of birth:' and
         its value on the same row, separated by a gap that group_lines split);
      3. below: the nearest line whose top is at or below the label's bottom, within 1.2 times the
         label's height, and that starts within 20 points of the label's left edge ('Address' with
         its value underneath).
    A value is the line's text; conf is the minimum confidence of its words. If none of the three
    finds anything, value and conf are None (the field is blank or missing); a blank line never
    steals the NEXT label as its value because of the distance limit in rule 3.

    kind 'choice': after the label come glyph + option pairs (TICKED or UNTICKED, then the option's
    words). The value is the list of ticked option names, in order; conf is the minimum over all
    words after the label.

    Returns {field: {"value": ..., "conf": ...}} for every field of the schema.
    """
    out = {}
    for name, spec in schema.items():
        label = spec["label"]
        found = None
        for ln in lines:
            if cer(label.lower(), ln["text"][:len(label)].lower()) <= 0.15:
                found = ln
                break
        if found is None:
            out[name] = {"value": None, "conf": None}
            continue
        n_label_words = len(label.split())
        after = found["words"][n_label_words:]
        if spec["kind"] == "choice":
            ticked, current = [], None
            for w in after:
                if w["text"] in (TICKED, UNTICKED):
                    current = [w["text"] == TICKED, []]
                    if current[0]:
                        ticked.append(current)
                    else:
                        ticked.append(None)
                elif current is not None:
                    current[1].append(w["text"])
            values = [" ".join(c[1]) for c in ticked if c]
            out[name] = {"value": values, "conf": min([w["conf"] for w in after], default=None)}
            continue
        value_words = after
        if not value_words:
            fx0, fy0, fx1, fy1 = found["bbox"]
            fh = fy1 - fy0
            right = [o for o in lines if o is not found
                     and min(fy1, o["bbox"][3]) - max(fy0, o["bbox"][1]) >= 0.5 * fh and o["bbox"][0] >= fx1]
            below = [o for o in lines if o is not found
                     and o["bbox"][1] >= fy1 - 1 and o["bbox"][1] - fy1 <= 1.2 * fh and abs(o["bbox"][0] - fx0) <= 20]
            if right:
                value_words = min(right, key=lambda o: o["bbox"][0])["words"]
            elif below:
                value_words = min(below, key=lambda o: o["bbox"][1])["words"]
        if value_words:
            out[name] = {"value": " ".join(w["text"] for w in value_words), "conf": min(w["conf"] for w in value_words)}
        else:
            out[name] = {"value": None, "conf": None}
    return out


def review_flags(fields, threshold=0.8, schema=FORM_SCHEMA, validators=VALIDATORS):
    """The names of the fields a person should look at, sorted. A field is flagged if

      * it is required and its value is None or an empty list (missing),
      * its value is present and conf < threshold (the engine was unsure), or
      * it has a validator in `validators` and the value fails it (a confident misread).

    An optional field that is blank (value None) is NOT flagged.
    """
    flagged = []
    for name, spec in schema.items():
        f = fields.get(name, {"value": None, "conf": None})
        v = f["value"]
        if v is None or v == []:
            if spec["required"]:
                flagged.append(name)
            continue
        if f["conf"] is not None and f["conf"] < threshold:
            flagged.append(name)
        elif name in validators and not validators[name](v):
            flagged.append(name)
    return sorted(flagged)


# =============================================================================
# GIVEN: the whole pipeline and the scorecard
# =============================================================================
def run_pipeline(pages=None, page_height=None, order=xy_cut, extract=True):
    """Run every stage with your functions. `order` is the reading-order function to use;
    extract=False skips the table and form stages (the milestone 2 to 4 checks use that)."""
    if pages is None:
        pages, _, page_height = load_fixtures()
    per_page = []
    for pg in pages:
        body, inside = split_regions(pg["words"], pg["regions"])
        per_page.append({"page": pg["page"], "lines": group_lines(body), "inside": inside})
    boiler = find_boilerplate([p["lines"] for p in per_page], page_height)
    paragraphs, result = [], {"boilerplate": boiler, "pages": [], "tables": [], "forms": []}
    for p in per_page:
        kept = strip_boilerplate(p["lines"], boiler, page_height)
        ordered = order(kept)
        paras = lines_to_paragraphs(ordered)
        for para in paras:
            para["page"] = p["page"]
        paragraphs.extend(paras)
        result["pages"].append({"page": p["page"], "removed": len(p["lines"]) - len(kept),
                                "text": " ".join(x["text"] for x in paras)})
        if extract and p["inside"].get("table"):
            result["tables"].append({"page": p["page"], "cells": build_table(p["inside"]["table"])})
        if extract and p["inside"].get("form"):
            form_lines = group_lines(p["inside"]["form"])
            result["forms"].append({"page": p["page"], "fields": extract_form(form_lines)})
    result["sections"] = detect_sections(paragraphs)
    return result


def scorecard():
    pages, truth, page_height = load_fixtures()
    naive = run_pipeline(pages, page_height, order=naive_order)
    good = run_pipeline(pages, page_height)
    print(f"{'page':<6}{'words':>7}{'removed':>9}{'CER naive order':>17}{'CER XY-cut':>12}")
    for pg, a, b, t in zip(pages, naive["pages"], good["pages"], truth["pages"]):
        print(f"{pg['page']:<6}{len(pg['words']):>7}{b['removed']:>9}{cer(t['body'], a['text']):>17.3f}{cer(t['body'], b['text']):>12.3f}")
    titles = [(s["level"], s["title"]) for s in good["sections"]]
    gold = [(o["level"], o["title"]) for o in truth["outline"]]
    print(f"\noutline: {len(titles)} headings found, {sum(1 for t in titles if t in gold)} of {len(gold)} correct")
    s = cell_scores(good["tables"][0]["cells"], [tuple(c) for c in truth["tables"][0]["cells"]])
    print(f"table:   structure F1 {s['structure_f1']:.2f}, exact F1 {s['exact_f1']:.2f}")
    fields = good["forms"][0]["fields"]
    gold_f = truth["forms"][0]["fields"]
    right = [k for k in gold_f if fields[k]["value"] == gold_f[k]]
    flags = review_flags(fields)
    wrong = [k for k in gold_f if fields[k]["value"] != gold_f[k]]
    print(f"form:    {len(right)} of {len(gold_f)} fields exactly right; {len(flags)} flagged for review "
          f"({', '.join(flags) or 'none'}); wrong and not flagged: {[k for k in wrong if k not in flags] or 'none'}")
    bad = [(w["conf"]) for p in pages for w in p["words"] if w["text"] != truth["words"][w["id"]]]
    allc = [w["conf"] for p in pages for w in p["words"]]
    for thr in (0.7, 0.8, 0.95):
        caught = sum(1 for c in bad if c < thr)
        flagged = sum(1 for c in allc if c < thr)
        print(f"words below confidence {thr}: {flagged} of {len(allc)} flagged, catching {caught} of {len(bad)} misread words")


if __name__ == "__main__":
    scorecard()
