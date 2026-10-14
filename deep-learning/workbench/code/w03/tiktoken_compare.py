"""Real tokenisers, measured: predict token counts from chapter 13's
reasoning, then count them with tiktoken and a Hugging Face tokenizer.

    python tiktoken_compare.py
    python tiktoken_compare.py --hf Qwen/Qwen2.5-0.5B

Needs: tiktoken, transformers (workbench/requirements.txt). The first run
downloads two tiktoken files (1.7 MB and 3.6 MB, from
openaipublic.blob.core.windows.net) and the Qwen tokenizer files
(about 11 MB from Hugging Face). No model weights are loaded."""
import argparse
import math
import re

import tiktoken
from transformers import AutoTokenizer

# ── 1. Settings ──────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--hf", default="Qwen/Qwen2.5-0.5B")
args, _ = ap.parse_known_args()        # notebooks pass their own flags

TEXTS = {
    "English": "The weather is nice today, so we are going for a walk "
               "in the park, and then we will have lunch by the river.",
    "German": "Das Wetter ist heute schön, deshalb gehen wir im Park "
              "spazieren und essen danach am Fluss zu Mittag.",
    "Hindi": "आज मौसम अच्छा है, इसलिए हम पार्क में टहलने जा रहे हैं "
             "और फिर नदी के किनारे दोपहर का खाना खाएँगे।",
    "Japanese": "今日は天気がいいので、公園へ散歩に行って、"
                "そのあと川のそばで昼ご飯を食べます。",
    "Numbers": "In 2024-10-14 we counted 1234567 users, 3.14159 "
               "seconds and 1000000000 bytes.",
    "Code": 'def area(r):\n    if r < 0:\n        raise ValueError("r")\n'
            '    return 3.14159 * r * r\n',
}
# A "word" is a run of non-space characters, except in Japanese, which
# has no spaces: there we count the characters instead.


def words(name, text):
    return len(text) if name == "Japanese" else len(text.split())


# Three counters with the same interface: text -> list of ids.
cl = tiktoken.get_encoding("cl100k_base")
o2 = tiktoken.get_encoding("o200k_base")
hf = AutoTokenizer.from_pretrained(args.hf)
COUNTERS = {
    "cl100k": cl.encode,
    "o200k": o2.encode,
    "hf": lambda s: hf.encode(s, add_special_tokens=False),
}
DECODERS = {"cl100k": cl.decode, "o200k": o2.decode, "hf": hf.decode}
print(f"cl100k_base: {cl.n_vocab:,} entries; o200k_base: {o2.n_vocab:,}; "
      f"{args.hf}: {len(hf):,}\n")

# ── 2. Predict (chapter 13), before any counting ─────────────────────────
# Rule A: English costs about 4 bytes per token in every vocabulary.
# Rule B: a script that UTF-8 stores in 3 bytes per character starts three
#         times longer; an old vocabulary keeps most of that, a new
#         multilingual one gives it back. Prediction: Hindi and Japanese
#         cost 2 to 4 times English per word under cl100k, less under o200k.
# Rule C: cl100k and o200k cut a digit run into groups of three from the
#         left, so a run of d digits costs ceil(d / 3) tokens.
print("predicted tokens (rules A and C)")
eng = TEXTS["English"]
print(f"  English: {len(eng.encode())} bytes / 4 = "
      f"{len(eng.encode()) / 4:.0f} tokens")
runs = re.findall(r"\d+", TEXTS["Numbers"])
c_pred = sum(math.ceil(len(r) / 3) for r in runs)
print("  Hindi cost / English cost, tokens: above 3 under cl100k, below "
      "1.5 under o200k (chapter 13: 55/17 and 16/17)")
print("  hf (Qwen2.5): no rule in the chapter; guess: Hindi cost between "
      "the two, digits one per token")
print(f"  digit runs {runs}: sum of ceil(d/3) = {c_pred} tokens for "
      f"the digits alone")

# ── 3. Measure: tokens, bytes per token, tokens per word ─────────────────
print("\nmeasured")
head = f"  {'text':9}{'bytes':>6}{'words':>6}"
for k in COUNTERS:
    head += f"{k:>9}{'tok/word':>9}"
print(head)
counts = {}
for name, text in TEXTS.items():
    nb, nw = len(text.encode()), words(name, text)
    row = f"  {name:9}{nb:>6}{nw:>6}"
    for k, enc in COUNTERS.items():
        n = len(enc(text))
        counts[name, k] = n
        row += f"{n:>9}{n / nw:>9.2f}"
    print(row)
print("\nHindi tokens / English tokens, and Japanese / English")
for k in COUNTERS:
    h = counts["Hindi", k] / counts["English", k]
    j = counts["Japanese", k] / counts["English", k]
    print(f"  {k:8} Hindi {h:.2f}   Japanese {j:.2f}")
print("\nbytes per token")
for name, text in TEXTS.items():
    nb = len(text.encode())
    cells = "".join(f"{k}={nb / counts[name, k]:.2f}  " for k in COUNTERS)
    print(f"  {name:9}{cells}")

# ── 4. Numbers: where do the cuts fall? ──────────────────────────────────
print("\ndigit runs, cut by each tokeniser")
for r in runs:
    cuts = []
    for k, enc in COUNTERS.items():
        pieces = [DECODERS[k]([i]) for i in enc(r)]
        cuts.append(f"{k}: " + "|".join(pieces))
    print(f"  {r:11} " + "   ".join(cuts))
digits_pred = sum(len(cl.encode(r)) for r in runs)
print(f"  cl100k digits alone: {digits_pred} tokens "
      f"(predicted {c_pred})")

# ── 5. A character split across tokens ───────────────────────────────────
print("\nmulti-byte characters")
for ch in ["é", "語", "🙂"]:
    raw = ch.encode()
    ids = cl.encode(ch)
    pieces = [cl.decode_single_token_bytes(i) for i in ids]
    alone = [cl.decode_bytes([i]).decode("utf-8", errors="replace")
             for i in ids]
    print(f"  {ch}  {len(raw)} bytes {raw.hex(' ')}; cl100k ids {ids} "
          f"= bytes {[p.hex(' ') for p in pieces]}; "
          f"each alone decodes to {alone}; together "
          f"{cl.decode(ids)!r}")
ids = hf.encode("🙂", add_special_tokens=False)
alone = [hf.decode([i]) for i in ids]
print(f"  🙂 hf ids {ids}; each alone decodes to {alone}; "
      f"together {hf.decode(ids)!r}")
print("  tokens that start or end inside a character (decode to "
      "\ufffd alone):")
for name in ("Japanese", "Hindi"):
    row = f"    {name:9}"
    for k, enc in COUNTERS.items():
        ids = enc(TEXTS[name])
        bad = sum("\ufffd" in DECODERS[k]([i]) for i in ids)
        row += f"{k} {bad} of {len(ids)}   "
    print(row)

# ── 6. The streaming fix: buffer bytes until a character is complete ─────
text = "Hi 語🙂"
naive, buf, out = "", b"", ""
for i in cl.encode(text):
    piece = cl.decode_single_token_bytes(i)
    naive += piece.decode("utf-8", errors="replace")
    buf += piece
    try:
        out += buf.decode("utf-8")
        buf = b""                      # complete: send it, clear the buffer
    except UnicodeDecodeError:
        pass                           # incomplete: wait for the next token
print(f"\nstreaming {text!r}: naive {naive!r}, buffered {out!r}")
