"""Readability audit for the AI path: one row per course, or per chapter.

    python3 authoring/audit_readability.py              # per course
    python3 authoring/audit_readability.py --chapters   # per chapter, worst first
    python3 authoring/audit_readability.py --spine      # builder-spine chapters only

Measures prose only (no code, SVG, quiz or sources): words, average sentence
length, the share of sentences over 35 words, an approximate Flesch-Kincaid
grade, defined terms per 1,000 words, and whether the chapter has an analogy.
Targets for the builder spine: average sentence 17 words or fewer, grade 9.5
or lower, and an analogy in every deep or core chapter.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_page import ROOT, prose_text, sentences  # noqa: E402

AI = ["ml-foundations", "ml", "deep-learning", "llm-training", "agents",
      "retrieval", "evals", "open-ended", "ai-delivery"]


def syllables(word):
    groups = re.findall(r"[aeiouy]+", word.lower())
    n = len(groups) - (1 if word.lower().endswith("e") and len(groups) > 1 else 0)
    return max(1, n)


def measure(path):
    src = open(path, encoding="utf-8").read()
    text = prose_text(src.split("<article", 1)[-1])
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    sents = sentences(text)
    if not words or not sents:
        return None
    lens = [len(s.split()) for s in sents]
    wps = sum(lens) / len(lens)
    spw = sum(syllables(w) for w in words) / len(words)
    return {
        "words": len(words),
        "wps": wps,
        "long": sum(1 for n in lens if n > 35) / len(lens),
        "grade": 0.39 * wps + 11.8 * spw - 15.59,
        "terms": 1000 * src.count('class="term"') / len(words),
        "analogy": "callout analogy" in src,
    }


def catalog():
    js = ("global.window={};require(%r);console.log(JSON.stringify(window.CS_COURSES.map(c=>({dir:c.dir,"
          "spine:c.spine||null,chapters:c.chapters.map(x=>({id:x.id,file:x.file,depth:x.depth}))}))))"
          % os.path.join(ROOT, "assets/js/catalog.js"))
    return {c["dir"]: c for c in json.loads(subprocess.check_output(["node", "-e", js]))}


def main(argv):
    cat = catalog()
    spine_only = "--spine" in argv
    rows = []
    for d in AI:
        co = cat[d]
        for ch in co["chapters"]:
            if spine_only and not (co["spine"] and ch["id"] in co["spine"]):
                continue
            path = os.path.join(ROOT, d, "chapters", ch["file"])
            if not os.path.exists(path):
                continue
            m = measure(path)
            if m:
                m.update(course=d, file=ch["file"], depth=ch["depth"])
                rows.append(m)
    if "--chapters" in argv:
        print(f"{'chapter':48}{'words':>7}{'w/sent':>8}{'>35w':>6}{'grade':>7}{'terms/1k':>9}  analogy")
        for r in sorted(rows, key=lambda r: -r["wps"]):
            print(f"{r['course'] + '/' + r['file']:48.48}{r['words']:>7}{r['wps']:>8.1f}{r['long']:>6.0%}"
                  f"{r['grade']:>7.1f}{r['terms']:>9.1f}  {'yes' if r['analogy'] else '-'}")
        return
    print(f"{'course':16}{'ch':>4}{'words':>8}{'w/sent':>8}{'>35w':>6}{'grade':>7}{'terms/1k':>9}{'no analogy':>11}")
    for d in AI:
        rs = [r for r in rows if r["course"] == d]
        if not rs:
            continue
        w = sum(r["words"] for r in rs)
        print(f"{d:16}{len(rs):>4}{w:>8}{sum(r['wps'] for r in rs) / len(rs):>8.1f}"
              f"{sum(r['long'] for r in rs) / len(rs):>6.0%}{sum(r['grade'] for r in rs) / len(rs):>7.1f}"
              f"{sum(r['terms'] * r['words'] for r in rs) / w:>9.1f}"
              f"{sum(1 for r in rs if not r['analogy'] and r['depth'] != 'intro'):>11}")
    w = sum(r["words"] for r in rows)
    print(f"{'total':16}{len(rows):>4}{w:>8}  (about {w // 12000} hours at 200 words a minute)")


if __name__ == "__main__":
    main(sys.argv[1:])
