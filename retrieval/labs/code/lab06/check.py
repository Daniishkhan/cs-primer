"""Self-check for Lab 6: A Document Understanding Pipeline.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 3 2     # milestone 3, replaying ONLY the random scenario of seed 2

Everything is deterministic: the four pages are pages.json and truth.json in this folder (made by
make_data.py), and every random scenario comes from a seeded random.Random. No network, no clock.
The whole check takes about ten seconds. Prints a tick, a cross, or "not implemented yet" for each
milestone.
"""
import importlib
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


# -----------------------------------------------------------------------------
# Test helpers and independent oracles (not the module under test)
# -----------------------------------------------------------------------------
_FIX = {}


def fixtures():
    if not _FIX:
        pages, truth, ph = mod.load_fixtures()
        _FIX.update(pages=pages, truth=truth, ph=ph)
    return _FIX["pages"], _FIX["truth"], _FIX["ph"]


def o_edit(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        diag, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            diag, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, diag + (a[i - 1] != b[j - 1]))
    return d[len(b)]


def o_cer(ref, hyp):
    ref, hyp = " ".join(ref.split()), " ".join(hyp.split())
    return o_edit(ref, hyp) / len(ref) if ref else (0.0 if not hyp else 1.0)


_wid = [0]


def W(text, x, y, size=10, conf=0.97, rng=None):
    """A word box like the fixtures': char width 0.6 * size, height 1.2 * size."""
    _wid[0] += 1
    jx = rng.uniform(-0.4, 0.4) if rng else 0.0
    jy = rng.uniform(-0.3, 0.3) if rng else 0.0
    w, h = 0.6 * size * len(text), 1.2 * size
    return {"id": f"t{_wid[0]}", "text": text, "conf": conf, "box": [x + jx, y + jy, x + jx + w, y + jy + h]}


def row(text, x, y, size=10, rng=None, space=None):
    """Words of `text` laid out from x, with one-character spaces (or `space` points)."""
    out, cur = [], x
    for t in text.split():
        out.append(W(t, cur, y, size, rng=rng))
        cur += 0.6 * size * len(t) + (0.6 * size if space is None else space)
    return out


def L(text, x, y, size=10, conf=0.97):
    """A line dict (via the given make_line) for text laid out from (x, y)."""
    ws = row(text, x, y, size)
    for w in ws:
        w["conf"] = conf
    return mod.make_line(ws)


def texts(items):
    return [it["text"] for it in items]


# =============================================================================
# Milestone 1: the character error rate
# =============================================================================
def m1():
    ed = mod.edit_distance
    cases = [("kitten", "sitting", 3), ("", "abc", 3), ("abc", "", 3), ("same", "same", 0), ("flaw", "lawn", 2),
             ("ab", "ba", 2), ("1,580.00", "1,530.00", 1), ("intention", "execution", 5)]
    for a, b, want in cases:
        got = ed(a, b)
        assert got == want, f"edit_distance({a!r}, {b!r}) should be {want}, got {got}"
    rng = random.Random(61)
    for _ in range(60):
        a = "".join(rng.choice("abc ") for _ in range(rng.randint(0, 12)))
        b = "".join(rng.choice("abc ") for _ in range(rng.randint(0, 12)))
        assert ed(a, b) == o_edit(a, b), f"edit_distance({a!r}, {b!r}) = {ed(a, b)}, expected {o_edit(a, b)}"
        assert ed(a, b) == ed(b, a), f"edit distance must be symmetric: {a!r} and {b!r}"
    cer = mod.cer
    assert near(cer("abcd", "abxd"), 0.25), f"cer('abcd', 'abxd') should be 0.25, got {cer('abcd', 'abxd')}"
    assert near(cer("ab", "abcd"), 1.0), "two insertions into a 2-character reference cost 2/2 = 1.0"
    assert near(cer("ab", "abcdef"), 2.0), "cer can exceed 1.0: four insertions over a reference of 2 is 2.0 (it is a cost, not a probability)"
    assert near(cer("", ""), 0.0) and near(cer("", "x"), 1.0), "an empty reference: 0.0 for an empty hypothesis, else 1.0, never ZeroDivisionError"
    assert near(cer("Total 1,580.00", "Total 1,530.00"), 1 / 14), "one wrong digit in 14 characters is 1/14"
    assert near(cer("two  words\n", "two words"), 0.0), "normalise first: runs of whitespace are one space and the ends are trimmed"
    assert near(cer("ﬁne print", "fine print"), 0.0), "NFKC normalisation turns the ligature 'ﬁ' into 'fi'"
    assert cer("a  b", "a b", normalise_text=False) > 0, "normalise_text=False must compare the raw strings"
    pages, truth, _ = fixtures()
    words = [(truth["words"][w["id"]], w["text"]) for p in pages for w in p["words"]]
    wrong = sum(1 for g, t in words if g != t)
    edits = sum(ed(g, t) for g, t in words)
    chars = sum(len(g) for g, _ in words)
    assert wrong == 31, f"fixture check: expected 31 misread words, found {wrong}"
    return (f"raw OCR engine over {len(words)} words: {wrong} misread, {edits} character edits in {chars} characters: "
            f"CER {edits / chars:.3%}")


# =============================================================================
# Milestone 2: lines and reading order
# =============================================================================
def gen_words(rng):
    """Rows of words in 1 to 3 columns, with the lines they should form, in (top, left) order."""
    ncols = rng.randint(1, 3)
    gutter = rng.uniform(26, 40)
    colw = (500 - gutter * (ncols - 1)) / ncols
    nrows = rng.randint(3, 6)
    words, groups = [], []
    for r in range(nrows):
        y = 80 + r * 14.4
        for c in range(ncols):
            x = 54 + c * (colw + gutter)
            toks, used = [], 0.0
            while True:
                t = "".join(rng.choice("abcdefghij") for _ in range(rng.randint(2, 8)))
                need = 6.0 * len(t) + (rng.uniform(4, 9) if toks else 0)
                if used + need > colw or (len(toks) >= 2 and rng.random() < 0.15):
                    break
                toks.append((t, used + (need - 6.0 * len(t))))
                used += need
            if not toks:
                continue
            ws = [W(t, x + off, y, rng=rng) for t, off in toks]
            words += ws
            groups.append(ws)
    # the lines are ordered by their actual (jittered) top edge, then left edge, like naive_order
    groups.sort(key=lambda g: (min(w["box"][1] for w in g), min(w["box"][0] for w in g)))
    return words, [" ".join(w["text"] for w in g) for g in groups]


def m2():
    ws = row("alpha beta gamma", 54, 100) + row("delta epsilon", 54, 114.4)
    got = mod.group_lines(list(reversed(ws)))
    assert texts(got) == ["alpha beta gamma", "delta epsilon"], f"two rows of words should be two lines; got {texts(got)}"
    assert all(set(ln) >= {"text", "bbox", "words", "conf", "height"} for ln in got), "lines must be make_line dicts"
    two = row("left side", 54, 100) + row("right side", 54 + 54 + 26, 100)
    got = mod.group_lines(two)
    assert texts(got) == ["left side", "right side"], f"a 26-point gutter must split a row into two lines; got {texts(got)}"
    head = [W("Annual", 54, 80, 22), W("Review", 54 + 6 * 13.2 + 13.2, 80, 22)]
    assert texts(mod.group_lines(head)) == ["Annual Review"], "a space in a 22-point heading is 13 points wide: still one line (the limit scales with the height)"
    for seed in seeds(range(1, 7)):
        rng = random.Random(seed)
        words, want = gen_words(rng)
        shuffled = words[:]
        rng.shuffle(shuffled)
        got = texts(mod.group_lines(shuffled))
        assert got == want, (f"seed {seed}: lines wrong or out of order.\n      expected {want}\n      got      {got}\n"
                             f"      hint: join a word to a line only if it overlaps vertically AND the gap is small; replay with `python3 check.py solution 2 {seed}`")

    # reading order, by hand: a title across the page, then two columns of three lines
    items = [{"id": "title", "bbox": [54, 70, 300, 92], "text": "title"}]
    for c, x in enumerate((54, 318)):
        for i in range(3):
            items.append({"id": f"c{c}l{i}", "bbox": [x, 120 + i * 14.4, x + 200, 132 + i * 14.4], "text": f"c{c}l{i}"})
    want = ["title", "c0l0", "c0l1", "c0l2", "c1l0", "c1l1", "c1l2"]
    rng = random.Random(5)
    for _ in range(4):
        rng.shuffle(items)
        got = [it["id"] for it in mod.xy_cut(items)]
        assert got == want, f"title, then the whole left column, then the whole right column.\n      expected {want}\n      got      {got}"
    assert mod.xy_cut([]) == [] and len(mod.xy_cut(items[:1])) == 1, "empty and single-item inputs come back as they are"
    # the pinwheel: no straight cut exists, so the fall-back (sort by top, then left) applies
    pin = [{"id": "a", "bbox": [0, 0, 120, 60]}, {"id": "b", "bbox": [100, 40, 200, 160]}, {"id": "c", "bbox": [80, 140, 200, 200]},
           {"id": "d", "bbox": [0, 100, 90, 200]}, {"id": "e", "bbox": [60, 60, 140, 140]}]
    got = [it["id"] for it in mod.xy_cut(pin)]
    assert sorted(got) == ["a", "b", "c", "d", "e"], f"xy_cut must return every item exactly once; got {got}"
    assert got == [it["id"] for it in mod.naive_order(pin)], "when no band is wider than min_gap, fall back to naive_order"
    for seed in seeds(range(1, 7)):
        rng = random.Random(100 + seed)
        items, want = [], []
        y = 70.0
        for band in range(rng.randint(2, 4)):
            ncols = 1 if band % 2 == 0 else rng.randint(2, 3)
            gutter = rng.uniform(24, 32)
            colw = (500 - gutter * (ncols - 1)) / ncols
            bottom = y
            for c in range(ncols):
                cy = y
                for i in range(rng.randint(2, 7) if ncols > 1 else rng.randint(1, 4)):
                    x0 = 54 + c * (colw + gutter)
                    x1 = x0 + colw * rng.uniform(0.6, 1.0)
                    it = {"id": f"b{band}c{c}l{i}", "bbox": [x0, cy, x1, cy + 12]}
                    items.append(it)
                    want.append(it["id"])
                    cy += 14.4 + (rng.choice([0, 0, 8]) if i else 0)
                bottom = max(bottom, cy - 2.4)
            y = bottom + rng.uniform(16, 30)
        shuffled = items[:]
        rng.shuffle(shuffled)
        got = [it["id"] for it in mod.xy_cut(shuffled)]
        assert got == want, (f"seed {seed}: wrong reading order.\n      expected {want}\n      got      {got}\n"
                             "      hint: cut along the WIDEST empty band first; bands narrower than min_gap are not cuts")
    pages, truth, ph = fixtures()
    body, _ = mod.split_regions(pages[0]["words"], pages[0]["regions"])
    lines = [ln for ln in mod.group_lines(body) if mod.zone_of(ln, ph) is None]
    xy = " ".join(texts(mod.xy_cut(lines)))
    nv = " ".join(texts(mod.naive_order(lines)))
    c_xy, c_nv = o_cer(truth["pages"][0]["body"], xy), o_cer(truth["pages"][0]["body"], nv)
    assert c_nv > 0.4, f"fixture check: the naive order should be bad on page 1 (CER > 0.4), got {c_nv:.3f}"
    assert c_xy < 0.06, f"XY-cut should read page 1 in order (CER < 0.06 against the truth; the OCR itself errs about 1%); got {c_xy:.3f}. Hyphenated line ends add a little: that is milestone 4."
    for n in (1, 2, 3):
        b, _ = mod.split_regions(pages[n]["words"], pages[n]["regions"])
        ls = [ln for ln in mod.group_lines(b) if mod.zone_of(ln, ph) is None]
        assert o_cer(truth["pages"][n]["body"], " ".join(texts(mod.xy_cut(ls)))) < 0.06, f"page {n + 1}: single-column pages must stay in top-to-bottom order"
    return f"page 1 (two columns), CER against the truth: naive top-then-left {c_nv:.3f}, XY-cut {c_xy:.3f}"


# =============================================================================
# Milestone 3: running headers and footers
# =============================================================================
def m3():
    ph = 792
    def page(n, total, body, header="Annual Report | North Region", footer=None):
        ls = [L(header, 54, 28, 9), L(footer or f"Page {n} of {total}", 270, 754, 9)]
        ls += [L(t, 54, 100 + 15 * i) for i, t in enumerate(body)]
        return ls
    pages = [page(k, 4, [f"body {k} one", f"body {k} two"]) for k in range(1, 5)]
    bp = mod.find_boilerplate(pages, ph)
    assert len(bp) == 2, f"a header and a footer repeat on all 4 pages: expected 2 boilerplate entries, got {len(bp)}: {bp}"
    assert {z for z, _ in bp} == {"top", "bottom"}, f"each entry is (zone, shape) with zone 'top' or 'bottom'; got {bp}"
    assert ("bottom", "page # of #") in bp, f"digits become '#': the footer shape is 'page # of #'; got {bp}"
    for pg in pages:
        kept = mod.strip_boilerplate(pg, bp, ph)
        assert texts(kept) == texts(pg)[2:], f"only the header and footer go; got {texts(kept)}"
    assert mod.find_boilerplate(pages[:1], ph) == [], "one page is no evidence of repetition: nothing is boilerplate"
    two = mod.find_boilerplate(pages[:2], ph)
    assert len(two) == 2, "two pages is the least evidence: a line on both is boilerplate"
    # an OCR slip in one page's header must not stop it matching
    noisy = [p[:] for p in pages]
    noisy[2][0] = L("Annuai Report | North Region", 54, 28, 9)
    bp2 = mod.find_boilerplate(noisy, ph)
    assert len(bp2) == 2, f"a one-character misread in a header must still cluster with the others (cer <= 0.15); got {len(bp2)} entries: {bp2}"
    assert texts(mod.strip_boilerplate(noisy[2], bp2, ph)) == texts(noisy[2])[2:], "the noisy header must be removed too"
    # a body line that says the same thing as the header, in the middle of the page, is never removed
    trick = [p[:] for p in pages]
    trick[1].append(L("Annual Report | North Region", 54, 400))
    bp3 = mod.find_boilerplate(trick, ph)
    assert "Annual Report | North Region" in texts(mod.strip_boilerplate(trick[1], bp3, ph)), "removal is by zone as well as by text: a mid-page copy stays"
    # a stamp on one page only is not boilerplate
    stamp = [p[:] for p in pages]
    stamp[0].append(L("DRAFT - NOT FOR ISSUE", 54, 40, 9))
    bp4 = mod.find_boilerplate(stamp, ph)
    assert "DRAFT - NOT FOR ISSUE" in texts(mod.strip_boilerplate(stamp[0], bp4, ph)), "a margin line seen on one page of four is not repeated, so it stays"
    for seed in seeds(range(1, 7)):
        rng = random.Random(300 + seed)
        n = rng.randint(3, 8)
        header = " ".join("".join(rng.choice("abcdefghij") for _ in range(rng.randint(3, 8))) for _ in range(4))
        pgs, bodies = [], []
        for k in range(1, n + 1):
            h = header
            if rng.random() < 0.25:                      # one misread character in some headers
                i = rng.randrange(len(h))
                if h[i] != " ":
                    h = h[:i] + "z" + h[i + 1:]
            body = [" ".join("".join(rng.choice("klmnopqr") for _ in range(rng.randint(2, 7))) for _ in range(rng.randint(3, 8))) for _ in range(rng.randint(4, 9))]
            bodies.append(body)
            pgs.append([L(h, 54, 30, 9), L(f"{k} / {n}", 290, 750, 9)] + [L(t, 54, 90 + 15 * i) for i, t in enumerate(body)])
        bp = mod.find_boilerplate(pgs, ph)
        for k, pg in enumerate(pgs):
            kept = texts(mod.strip_boilerplate(pg, bp, ph))
            assert kept == bodies[k], (f"seed {seed}, page {k + 1} of {n}: expected exactly the {len(bodies[k])} body lines to remain, got {len(kept)}.\n"
                                       f"      boilerplate found: {bp}; replay with `python3 check.py solution 3 {seed}`")
    pages_, truth, ph = fixtures()
    per_page = []
    for pg in pages_:
        body, _ = mod.split_regions(pg["words"], pg["regions"])
        per_page.append(mod.group_lines(body))
    bp = mod.find_boilerplate(per_page, ph)
    assert len(bp) == 2, f"the four real pages have one running header and one page-number footer; found {len(bp)}: {bp}"
    removed = []
    for k, lines in enumerate(per_page):
        kept = mod.strip_boilerplate(lines, bp, ph)
        removed.append(len(lines) - len(kept))
        gone = [ln["text"] for ln in lines if ln not in kept]
        assert len(gone) == 2 and any("Page" in g for g in gone), f"page {k + 1}: expected the header and the footer to go, removed {gone}"
    return f"real document: {len(bp)} repeated margin lines, removed from every page ({removed} lines per page), including the header read as 'Councii' on page 3"


# =============================================================================
# Milestone 4: paragraphs and sections
# =============================================================================
def mini_pipeline():
    pages, truth, ph = fixtures()
    res = mod.run_pipeline(pages, ph, extract=False)
    return res, truth


def m4():
    # --- lines_to_paragraphs, by hand
    lines = [L("first line of text", 54, 100), L("second line of text", 54, 114.4), L("third line.", 54, 128.8),
             L("a new paragraph", 54, 151.2), L("fin", 54, 165.6)]
    ps = mod.lines_to_paragraphs(lines)
    assert [p["text"] for p in ps] == ["first line of text second line of text third line.", "a new paragraph fin"], \
        f"a gap of 8 points above the 4th line starts a new paragraph; got {[p['text'] for p in ps]}"
    assert ps[0]["n_lines"] == 3 and near(ps[0]["bbox"][3], lines[2]["bbox"][3]) and near(ps[0]["height"], 12.0), \
        f"paragraph fields: n_lines 3, bbox the union of its lines, height the lines' height; got {ps[0]}"
    ps = mod.lines_to_paragraphs([L("the new infra-", 54, 100), L("structure was replaced", 54, 114.4)])
    assert ps[0]["text"] == "the new infrastructure was replaced", f"a line-end hyphen before a lower-case start is removed; got {ps[0]['text']!r}"
    ps = mod.lines_to_paragraphs([L("a twenty-", 54, 100), L("One-day pass", 54, 114.4)])
    assert ps[0]["text"] == "a twenty- One-day pass", f"an upper-case start keeps the hyphen (no fusing); got {ps[0]['text']!r}"
    ps = mod.lines_to_paragraphs([L("1. Service performance", 54, 100, 14), L("The council handled", 54, 125)])
    assert len(ps) == 2, "a change of line height (heading to body) starts a new paragraph even when the gap is small"
    col = [L("a sentence that is not", 54, 560), L("finished yet", 318, 170)]
    assert len(mod.lines_to_paragraphs(col)) == 1 and mod.lines_to_paragraphs(col)[0]["text"] == "a sentence that is not finished yet", \
        "a column break in the middle of a sentence (the next line is higher on the page) continues the paragraph"
    col = [L("a sentence that ends.", 54, 560), L("Another begins", 318, 170)]
    assert len(mod.lines_to_paragraphs(col)) == 2, "a column break after a full stop starts a new paragraph"
    assert mod.lines_to_paragraphs([]) == [], "no lines, no paragraphs"
    # --- detect_sections, by hand
    def P(text, height=12.0, n=1, page=1):
        return {"text": text, "height": height, "n_lines": n, "page": page, "bbox": [54, 0, 500, 10]}
    doc = [P("Annual Review", 26.4), P("1. Overview", 16.8), P("Body text goes on for several lines here.", 12, 4),
           P("1.1 Scope", 12), P("More body text for the scope.", 12, 3), P("1. Write to the manager.", 12), P("Closing words follow the list.", 12, 2, 2),
           P("Appendix", 16.8, 1, 2), P("Notes for the appendix.", 12, 2, 2)]
    got = mod.detect_sections(doc)
    want = [(0, "Annual Review"), (1, "1. Overview"), (2, "1.1 Scope"), (1, "Appendix")]
    assert [(s["level"], s["title"]) for s in got] == want, f"outline wrong.\n      expected {want}\n      got      {[(s['level'], s['title']) for s in got]}\n      hint: '1. Write to the manager.' ends in a full stop, so it is body text"
    assert got[2]["text"] == "More body text for the scope. 1. Write to the manager. Closing words follow the list.", \
        f"body paragraphs of a section are joined with single spaces; got {got[2]['text']!r}"
    assert got[1]["text"] == "Body text goes on for several lines here." and got[1]["page"] == 1, f"section fields: level, title, page of the heading, text; got {got[1]}"
    assert got[3]["page"] == 2, "a section's page is the page of its heading"
    pre = mod.detect_sections([P("Preamble words here.", 12, 2), P("1. First", 16.8)])
    assert pre[0]["level"] == 0 and pre[0]["title"] == "" and pre[0]["text"] == "Preamble words here.", "body text before the first heading gets a level-0 section with an empty title"
    assert mod.detect_sections([P("A sentence of body text that happens to be set in a larger size.", 16.8)])[0]["title"] == "", \
        "a long line ending in a full stop is not a heading, however big it is"
    for seed in seeds(range(1, 7)):
        rng = random.Random(400 + seed)
        want, doc, y = [], [], 0
        for s in range(rng.randint(3, 7)):
            level = rng.choice([1, 1, 2, 3])
            num = ".".join(str(rng.randint(1, 9)) for _ in range(level))
            title = f"{num}{'.' if level == 1 else ''} " + " ".join("".join(rng.choice("abcdefgh") for _ in range(rng.randint(3, 8))) for _ in range(rng.randint(1, 4))).capitalize()
            paras = [" ".join("".join(rng.choice("ijklmnop") for _ in range(rng.randint(2, 8))) for _ in range(rng.randint(8, 20))) + "." for _ in range(rng.randint(1, 3))]
            page = 1 + s // 3
            doc.append(P(title, rng.choice([12.0, 14.0, 16.8]), 1, page))
            doc += [P(t, 12.0, rng.randint(2, 5), page) for t in paras]
            want.append((level, title, " ".join(paras)))
        got = mod.detect_sections(doc)
        assert [(g["level"], g["title"], g["text"]) for g in got] == want, \
            f"seed {seed}: sections differ.\n      expected levels/titles {[(w[0], w[1]) for w in want]}\n      got                    {[(g['level'], g['title']) for g in got]}"
    # --- the real document
    res, truth = mini_pipeline()
    got = [(s["level"], s["title"]) for s in res["sections"]]
    gold = [(o["level"], o["title"]) for o in truth["outline"]]
    assert got == gold, f"outline of the real document differs.\n      expected {gold}\n      got      {got}"
    worst = 0.0
    for s, t in zip(res["sections"], truth["sections"]):
        c = o_cer(t["body"], s["text"]) if t["body"] else (0.0 if not s["text"] else 1.0)
        worst = max(worst, c)
    assert worst < 0.06, f"every section body should be within 6 per cent CER of the truth (the OCR errs about 1%); worst is {worst:.3f}"
    page1 = res["pages"][0]["text"]
    assert "infrastructure" in page1 and "infra- " not in page1, "page 1 has a line-end hyphen in 'infrastructure': it must be fused"
    return f"real document: {len(got)} of {len(gold)} headings found at the right level; worst section-body CER {worst:.3f}"


# =============================================================================
# Milestone 5: a table from boxes
# =============================================================================
def m5():
    assert mod.build_table([]) == [], "no words, no cells"
    ws = row("Item", 54, 100) + row("Qty", 200, 100) + row("Pen", 54, 120) + row("12", 200, 120) + row("Red pen", 54, 140) + row("3", 200, 140) + row("Ink", 54, 160) + row("7", 200, 160)
    got = mod.build_table(list(reversed(ws)))
    want = [(0, 0, 1, "Item"), (0, 1, 1, "Qty"), (1, 0, 1, "Pen"), (1, 1, 1, "12"), (2, 0, 1, "Red pen"), (2, 1, 1, "3"), (3, 0, 1, "Ink"), (3, 1, 1, "7")]
    assert sorted(got) == want, f"a 4 x 2 grid, with 'Red pen' as ONE cell.\n      expected {want}\n      got      {sorted(got)}"
    ws = (row("Requests (thousands)", 240, 100) + row("Region", 54, 120) + row("2025", 258, 120) + row("2026", 340, 120) + row("North", 54, 140) + row("120.4", 252, 140)
          + row("131.0", 334, 140) + row("South", 54, 160) + row("98.2", 258, 160) + row("95.1", 346, 160) + row("Asia", 54, 180) + row("210.7", 252, 180) + row("233.5", 334, 180))
    got = sorted(mod.build_table(ws))
    assert got[0] == (0, 1, 2, "Requests (thousands)"), f"a heading that covers columns 1 and 2 is ONE cell with colspan 2; got {got[0]}"
    assert len(got) == 13 and (4, 2, 1, "233.5") in got, f"13 cells expected, with right-aligned numbers in the right columns; got {got}"
    # a row with a missing cell leaves a hole, not a shifted row
    ws = row("A", 54, 100) + row("B", 200, 100) + row("C", 300, 100) + row("x", 54, 120) + row("z", 300, 120) + row("p", 54, 140) + row("q", 200, 140) + row("r", 300, 140) + row("s", 54, 160) + row("t", 200, 160) + row("u", 300, 160)
    got = mod.build_table(ws)
    assert (1, 2, 1, "z") in got and (1, 1, 1, "") not in got, f"a missing middle cell must leave a gap and keep 'z' in column 2; got {sorted(got)}"
    for seed in seeds(range(1, 9)):
        rng = random.Random(500 + seed)
        ncols, nrows = rng.randint(3, 5), rng.randint(4, 8)
        widths = [rng.choice([60, 70, 90]) for _ in range(ncols)]
        gut = rng.uniform(28, 40)
        lefts = [54 + sum(widths[:c]) + gut * c for c in range(ncols)]
        span = rng.randrange(ncols - 1) if rng.random() < 0.7 else None
        words, want = [], []

        def tokens(total_chars, rng):
            """1 to 3 words whose letters and spaces fill total_chars characters exactly."""
            n = min(rng.randint(1, 3), max(1, (total_chars + 1) // 3))
            letters = total_chars - (n - 1)
            cuts = sorted(rng.sample(range(1, letters), n - 1)) if n > 1 else []
            lens = [b - a for a, b in zip([0] + cuts, cuts + [letters])]
            return ["".join(rng.choice("abcdefghijk") for _ in range(k)) for k in lens]
        for r in range(nrows):
            if r == 0 and span is not None:
                # a heading over columns span and span + 1: its text fills the whole width of both
                total_w = widths[span] + gut + widths[span + 1]
                chars = int((total_w - 4) // 6)
                toks = tokens(chars, rng)
                cur = lefts[span] + 2
                for t in toks:
                    words.append(W(t, cur, 100, rng=rng))
                    cur += 6.0 * (len(t) + 1)
                want.append((0, span, 2, " ".join(toks)))
                continue
            for c in range(ncols):
                toks = tokens(int(widths[c] // 6), rng)
                cur = lefts[c]
                for t in toks:
                    words.append(W(t, cur, 100 + r * 19, rng=rng))
                    cur += 6.0 * (len(t) + 1)
                want.append((r, c, 1, " ".join(toks)))
        rng.shuffle(words)
        got = sorted(mod.build_table(words))
        want = sorted(want)
        assert got == want, (f"seed {seed}: grid differs ({ncols} columns, {nrows} rows, heading span {span}).\n      "
                             f"missing  {[c for c in want if c not in got][:4]}\n      surplus  {[c for c in got if c not in want][:4]}\n      "
                             f"replay with `python3 check.py solution 5 {seed}`")
    pages, truth, ph = fixtures()
    _, inside = mod.split_regions(pages[1]["words"], pages[1]["regions"])
    cells = mod.build_table(inside["table"])
    sc = mod.cell_scores(cells, [tuple(c) for c in truth["tables"][0]["cells"]])
    assert sc["structure_f1"] == 1.0, f"the real table's grid (rows, columns, spans) must be exactly right; structure F1 {sc['structure_f1']:.2f}"
    assert sc["exact_f1"] >= 0.9, f"exact F1 (with text) should be about 0.96: one cell is misread by the OCR engine; got {sc['exact_f1']:.2f}"
    return f"real table (7 rows, 4 columns, one spanning heading): structure F1 {sc['structure_f1']:.2f}, exact F1 {sc['exact_f1']:.2f} (87l.2 was misread by the engine)"


# =============================================================================
# Milestone 6: forms
# =============================================================================
def form_lines(rng, values):
    """Build form lines (make_line, so milestone 2 is not needed) in three patterns."""
    lines, y, patt = [], 100, {}
    for name, spec in mod.FORM_SCHEMA.items():
        label, v = spec["label"], values[name]
        lab_words = label.split()
        if spec["kind"] == "choice":
            ws = row(label + ":", 54, y)
            cur = ws[-1]["box"][2] + 6
            for opt in ("Resident", "Visitor", "Business"):
                ws.append(W(mod.TICKED if opt in (v or []) else mod.UNTICKED, cur, y))
                cur += 12
                ws.append(W(opt, cur, y))
                cur += 6.0 * len(opt) + 6
            lines.append(mod.make_line(ws))
            patt[name] = "choice"
        else:
            kind = "blank" if v is None else rng.choice(["inline", "right", "below"])
            patt[name] = kind
            if kind == "inline":
                lines.append(mod.make_line(row(label + ": " + v, 54, y)))
            elif kind == "right":
                lines.append(mod.make_line(row(label, 54, y)))
                lines.append(mod.make_line(row(v, 250, y)))
            elif kind == "below":
                lines.append(mod.make_line(row(label, 54, y)))
                lines.append(mod.make_line(row(v, 54, y + 16)))
            else:
                lines.append(mod.make_line(row(label + ":", 54, y)))
        y += 56
    return lines, patt


def m6():
    values = {"full_name": "Jo Smith", "date_of_birth": "01 May 1990", "address": "4 High Street, Leeds LS1 2AB",
              "vehicle_registration": "AB12 CDE", "permit_zone": "B7", "email": None, "permit_type": ["Visitor"]}
    for seed in seeds(range(1, 7)):
        rng = random.Random(600 + seed)
        vals = dict(values)
        vals["full_name"] = rng.choice(["Jo Smith", "Ana Lopez", "Wei Chen"])
        vals["permit_zone"] = rng.choice(["B7", "C14", "A2"])
        vals["permit_type"] = rng.choice([["Resident"], ["Visitor"], ["Business"]])
        if rng.random() < 0.4:
            vals["email"] = "jo@example.org"
        lines, patt = form_lines(rng, vals)
        rng.shuffle(lines)
        got = mod.extract_form(lines)
        for name in vals:
            assert name in got and set(got[name]) >= {"value", "conf"}, f"seed {seed}: the result needs an entry {{'value', 'conf'}} for every schema field; missing {name}"
            assert got[name]["value"] == vals[name], (f"seed {seed}: field {name} (pattern {patt[name]}): expected {vals[name]!r}, got {got[name]['value']!r}.\n"
                                                      "      hint: inline value, else a line to the right on the same row, else a line just below; a blank field must stay None; "
                                                      f"replay with `python3 check.py solution 6 {seed}`")
        assert near(got["full_name"]["conf"], 0.97) or got["full_name"]["conf"] is not None, "conf is the minimum word confidence of the value"
    # confidence is the minimum over the value's words
    ws = row("Full name:", 54, 100)
    v = row("Maria Okafor", 130, 100)
    v[0]["conf"], v[1]["conf"] = 0.91, 0.62
    fields = mod.extract_form([mod.make_line(ws + v)])
    assert fields["full_name"]["value"] == "Maria Okafor" and near(fields["full_name"]["conf"], 0.62), \
        f"conf of a value is the MINIMUM of its words' confidences (0.62 here); got {fields['full_name']}"
    assert fields["email"] == {"value": None, "conf": None}, "a field that is not on the form at all: value None, conf None"
    # a misread label still matches
    noisy = mod.extract_form([mod.make_line(row("Fu1l name: Ana Lopez", 54, 100))])
    assert noisy["full_name"]["value"] == "Ana Lopez", f"'Fu1l name:' is one misread character away from the label (cer 1/9); got {noisy['full_name']}"
    # a blank field does not steal the next label
    blank = mod.extract_form([mod.make_line(row("Email:", 54, 100)), mod.make_line(row("Permit zone", 54, 128)), mod.make_line(row("C4", 250, 128))])
    assert blank["email"]["value"] is None, f"'Email:' has nothing after it and the next line is another label 28 points down: value None; got {blank['email']}"
    assert blank["permit_zone"]["value"] == "C4"
    # review flags
    ok = {"full_name": {"value": "Jo Smith", "conf": 0.95}, "date_of_birth": {"value": "01 May 1990", "conf": 0.9},
          "address": {"value": "4 High Street", "conf": 0.9}, "vehicle_registration": {"value": "AB12 CDE", "conf": 0.9},
          "permit_zone": {"value": "B7", "conf": 0.9}, "email": {"value": None, "conf": None}, "permit_type": {"value": ["Visitor"], "conf": 0.9}}
    assert mod.review_flags(ok) == [], f"a clean form with a blank OPTIONAL email needs no review; got {mod.review_flags(ok)}"
    def tweak(**kw):
        d = {k: dict(v) for k, v in ok.items()}
        for k, v in kw.items():
            d[k] = v
        return d
    f = mod.review_flags(tweak(address={"value": "4 High Street", "conf": 0.79}))
    assert f == ["address"], f"confidence 0.79 is below the 0.8 threshold: flag it; got {f}"
    f = mod.review_flags(tweak(address={"value": "4 High Street", "conf": 0.8}))
    assert f == [], "confidence exactly at the threshold is accepted (the test is conf < threshold)"
    f = mod.review_flags(tweak(vehicle_registration={"value": "AB1Z CDE", "conf": 0.99}))
    assert f == ["vehicle_registration"], f"a CONFIDENT misread must still be caught by its validator; got {f}"
    f = mod.review_flags(tweak(permit_zone={"value": None, "conf": None}, permit_type={"value": [], "conf": 0.9}))
    assert f == ["permit_type", "permit_zone"], f"required fields that are missing or have nothing ticked are flagged, sorted by name; got {f}"
    f = mod.review_flags(tweak(date_of_birth={"value": "31 Febuary 1990", "conf": 0.95}), threshold=0.5)
    assert f == ["date_of_birth"], f"an impossible date fails its validator even at a low threshold; got {f}"
    f = mod.review_flags(ok, threshold=0.95)
    assert "address" in f and "full_name" not in f, f"the threshold is a parameter: at 0.95, 0.9 is low and 0.95 is not; got {f}"
    # the real form
    res, truth = None, None
    pages, truth, ph = fixtures()
    res = mod.run_pipeline(pages, ph)
    fields = res["forms"][0]["fields"]
    gold = truth["forms"][0]["fields"]
    for k in ("full_name", "address", "permit_zone", "email", "permit_type"):
        assert fields[k]["value"] == gold[k], f"real form, {k}: expected {gold[k]!r}, got {fields[k]['value']!r}"
    assert fields["date_of_birth"]["value"] == "14 Marcb 1987" and fields["vehicle_registration"]["value"] == "KXl9 ZTR", \
        f"the OCR engine's own misreads must be reported as read (never silently corrected); got {fields['date_of_birth']['value']!r}, {fields['vehicle_registration']['value']!r}"
    flags = mod.review_flags(fields)
    assert flags == ["date_of_birth", "vehicle_registration"], \
        f"the two misread fields should be flagged (the date by its low confidence, the registration, read at 0.93, by its validator); got {flags}"
    wrong = [k for k in gold if fields[k]["value"] != gold[k]]
    assert all(k in flags for k in wrong), f"every wrong field must be flagged; wrong but unflagged: {[k for k in wrong if k not in flags]}"
    good = mod.run_pipeline(pages, ph)
    sc = mod.cell_scores(good["tables"][0]["cells"], [tuple(c) for c in truth["tables"][0]["cells"]])
    return (f"real form: {len(gold) - len(wrong)} of {len(gold)} fields exactly right, the other {len(wrong)} flagged for review ({', '.join(flags)});\n"
            f"whole pipeline: 4 pages, 9 headings, table exact F1 {sc['exact_f1']:.2f}, form flags {flags}")


MILESTONES = [
    (1, "Milestone 1: edit distance and the character error rate", m1),
    (2, "Milestone 2: lines, and reading order by XY-cut", m2),
    (3, "Milestone 3: running headers and footers", m3),
    (4, "Milestone 4: paragraphs and the section outline", m4),
    (5, "Milestone 5: a table from word boxes", m5),
    (6, "Milestone 6: a form into typed fields, and what to review", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 6 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
