from solution import *
import corpus

pages = {p.id: p for p in corpus.pages()}
page = next(p for p in pages.values() if p.kind == "short")
print(page.html)
print("->", repr(extract(page.html)))
print()
art = next(p for p in pages.values() if p.kind == "article")
text = extract(art.html)
print(len(art.html), "characters of HTML ->", len(text), "characters,", len(text.split()), "words")
print(text.split("\n")[0])
