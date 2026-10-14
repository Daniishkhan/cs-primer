"""detector.py: the "classifier stand-in" for Lab 6 (given, do not edit).

A real deployment would call a trained prompt-injection classifier (chapter 15). So that the lab runs offline, this
is a small naive Bayes model over words, trained when the module loads on the generated examples of attacks.py:
about 185 injection-like texts against 300 ordinary support messages. It is deliberately modest, like the one in
chapter 15: it has learned that words such as "instructions", "ignore", "system", "prompt" and "decode" go with
attacks, and it knows nothing about French, look-alike letters, 1337-speak or text hidden in base64.

    injection_score(text) -> a number in (0, 1): higher means more like an injection

The score is the sigmoid of the prior log-odds plus the summed log-likelihood ratios of the known words divided by the
square root of how many known words there were (so that long texts do not all saturate at 0 or 1). Words it never saw
in training count for nothing.
"""
import math
import re
from collections import Counter

import attacks

_TOKEN = re.compile(r"[a-z]+")
_FUNCTION_WORDS = set("the a an of to in on at is are was were be do does for and or it this that how what when where why can with from by not".split())


def _tokens(text):
    return [w for w in _TOKEN.findall(text.lower()) if w not in _FUNCTION_WORDS]


def _train():
    pos, neg = Counter(), Counter()
    for t in attacks.injection_training_set():
        pos.update(set(_tokens(t)))
    for t in attacks.benign_training_set():
        neg.update(set(_tokens(t)))
    n_pos, n_neg = len(attacks.injection_training_set()), len(attacks.benign_training_set())
    llr = {}
    for w in set(pos) | set(neg):
        if pos[w] + neg[w] < 3:                  # too rare to trust
            continue
        p = (pos[w] + 1.0) / (n_pos + 2.0)
        q = (neg[w] + 1.0) / (n_neg + 2.0)
        llr[w] = math.log(p / q)
    return llr


_LLR = _train()
_PRIOR = math.log(len(attacks.injection_training_set()) / len(attacks.benign_training_set()))


def injection_score(text):
    known = [w for w in _tokens(text) if w in _LLR]
    s = _PRIOR + (sum(_LLR[w] for w in known) / math.sqrt(len(known)) if known else 0.0)
    return 1.0 / (1.0 + math.exp(-s))
