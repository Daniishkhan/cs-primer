"""Lab 3: a PII redaction and audit pipeline.

The brief: a retail bank wants an assistant that summarises customer messages for its
support staff. The messages are full of personal data (names, cards, accounts, phone
numbers), and the bank's rules are plain: the model provider must never see a raw
identifier, a member of staff may see only what their job needs, and every time anyone
looks at a real value there must be a record that cannot be quietly edited afterwards.

You build the pipeline in six steps: detect the identifiers, tell real ones from look-alikes
(a checksum), resolve overlapping detections, replace each value with a stable token kept in
a vault, release tokens only to people allowed to see them while writing a tamper-evident
audit log, and finally measure what the detector misses and wire it all around a model.

What is GIVEN: the constants and patterns, `Span`, `wilson`, the corpus loader and a stand-in
summarising model. What YOU write is marked TODO:

    1  luhn_valid, iban_valid, find_structured
    2  find_names, find_places, resolve, detect
    3  normalise, Vault.token_for, redact, restore
    4  AuditLog.append, AuditLog.verify, reveal
    5  score_spans, prf, evaluate
    6  tripwire, answer

`python3 check.py` runs the milestones; the lab page explains each one.
Every person, account and number in the corpus is invented.
"""
import hashlib
import json
import math
import os
import re
from collections import namedtuple

from llm import ScriptedModel, text_of

HERE = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# GIVEN: constants, patterns and small helpers
# =============================================================================
# A detected span of text: characters start .. end (end exclusive) hold a value of this kind.
Span = namedtuple("Span", "start end kind")

# Kinds in PRIORITY order: when two detections of the same length overlap, the earlier kind wins.
KINDS = ["CARD", "IBAN", "EMAIL", "PHONE", "DATE", "PERSON", "PLACE"]
GENERALISE = {"DATE"}            # replaced by a coarser value (the year), never stored: not reversible

PATTERNS = {                     # candidates only: some need a checksum before they count
    "EMAIL": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "PHONE": re.compile(r"(?<![\w+])(?:\+\d{1,3}|0) ?\d(?: ?\d){7,10}(?!\w)"),
    "CARD": re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?!\d)"),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b"),
    "DATE": re.compile(r"\b(?:\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}|\d{2}/\d{2}/\d{4})\b"),
}

TITLES = ["Mr", "Mrs", "Ms", "Miss", "Mx", "Dr", "Prof"]
FIRST_NAMES = {
    "Aoife", "Tom", "Maria", "John", "James", "Priya", "Daniel", "Emma", "Chloe", "Mark", "Grace", "Will",
    "Sarah", "Ahmed", "Fatima", "Liam", "Noah", "Olivia", "Sean", "Ciara", "Marcus", "Elena", "Pavel",
    "Hannah", "David", "Laura", "Peter", "Anna", "Kofi", "Yusuf", "Mei", "Eleanor",
}
PLACES = ["Dublin", "Cork", "Galway", "Tralee", "Limerick", "Leeds", "Manchester", "Bristol", "Sutton",
          "Milton Keynes", "Newcastle", "Newcastle upon Tyne", "Glasgow", "Cardiff", "Lagos", "Kraków"]
GREETINGS = ["Hi", "Hello", "Dear", "Thanks", "Thank you"]

TOKEN_RE = re.compile(r"\[([A-Z]+)_(\d+)\]")          # [PERSON_1], [PHONE_3] ...

# Who may look at which real values, and for which recorded reasons. Nobody may reveal a CARD.
POLICY = {
    "support_agent": {"PERSON", "PLACE", "PHONE"},
    "fraud_analyst": {"PERSON", "PLACE", "PHONE", "EMAIL", "IBAN"},
    "auditor": set(),          # reads the log, never the values
}
PURPOSES = {"dispute", "fraud_review", "complaint", "audit"}      # codes, never free text (free text holds PII)
GENESIS = "0" * 64             # the "previous hash" of the first log entry

SYSTEM = "You summarise customer messages for support staff in one sentence. Keep placeholders like [PERSON_1] exactly as written."


def clean_purpose(purpose):
    """GIVEN. What may be written to the log as a purpose: the code itself if it is one of
    PURPOSES, otherwise the word "invalid". Free text typed by a person can contain personal data,
    so it must never be copied into a log."""
    return purpose if purpose in PURPOSES else "invalid"


def wilson(k, n, z=1.96):
    """GIVEN. Wilson 95% interval (lo, hi) for k of n (the same as Lab 1)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def load_corpus():
    """GIVEN. 30 invented customer messages: id, text, spans (gold [start, end, kind] triples)
    and indirect (phrases that identify someone without being an identifier any rule can name)."""
    with open(os.path.join(HERE, "corpus.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def make_summariser(extra=""):
    """GIVEN. A stand-in 'model' for the pipeline of milestone 6. It reads the placeholders in the
    message and writes a one-sentence summary that repeats them, so you can see what a real model
    would be handed and what it would hand back. `extra` is appended to every reply (use it to make
    the model invent a placeholder or a raw value)."""
    def reply(messages, tools, system):
        body = messages[-1]["content"]
        found = [m.group() for m in TOKEN_RE.finditer(body)]
        by_kind = {}
        for t in found:
            by_kind.setdefault(TOKEN_RE.match(t).group(1), t)
        who = by_kind.get("PERSON", "an unnamed customer")
        parts = [f"Summary: {who} has a query"]
        if "PLACE" in by_kind:
            parts.append(f"from {by_kind['PLACE']}")
        if "PHONE" in by_kind:
            parts.append(f"and asks to be called on {by_kind['PHONE']}")
        if "EMAIL" in by_kind:
            parts.append(f"or at {by_kind['EMAIL']}")
        return " ".join(parts) + "." + extra
    return ScriptedModel(reply)


# =============================================================================
# Milestone 1: structured identifiers, and telling the real from the look-alike
# =============================================================================
def luhn_valid(number):
    """True if `number` passes the Luhn checksum used by payment cards. Spaces and dashes are
    ignored; fewer than 13 or more than 19 digits is not a card, so False.

    luhn_valid("4539 8997 2074 3225") -> True;  luhn_valid("4539 8997 2074 3226") -> False."""
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:                       # every second digit from the right is doubled
            d *= 2
            if d > 9:
                d -= 9                       # same as adding the two digits of the product
        total += d
    return total % 10 == 0


def iban_valid(value):
    """True if `value` is a well-formed IBAN with correct check digits (ISO 13616 mod 97).
    Spaces are ignored and case does not matter. Shape: two letters, two digits, then 11 to 30
    letters or digits. Move the first four characters to the end, turn each letter into a number
    (A=10 ... Z=35), read the result as one big integer, and require it to leave remainder 1
    when divided by 97.

    iban_valid("GB29 NWBK 6016 1331 9268 19") -> True;  the same with the last digit changed -> False."""
    s = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    rearranged = s[4:] + s[:4]
    number = "".join(str(int(c, 36)) for c in rearranged)     # int('A', 36) == 10
    return int(number) % 97 == 1


def find_structured(text):
    """All EMAIL, PHONE, CARD, IBAN and DATE spans in `text`, as Span(start, end, kind), sorted.

    Use the regexes in PATTERNS to find candidates. A CARD candidate counts only if luhn_valid
    accepts it, and an IBAN candidate only if iban_valid accepts it; the rest count as found.
    Overlaps are NOT resolved here (milestone 2 does that)."""
    spans = []
    for kind, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            if kind == "CARD" and not luhn_valid(m.group()):
                continue
            if kind == "IBAN" and not iban_valid(m.group()):
                continue
            spans.append(Span(m.start(), m.end(), kind))
    return sorted(spans)


# =============================================================================
# Milestone 2: names, places, and one answer for every character
# =============================================================================
# --solution-only-begin
_WORD = r"[A-Z][\w'’-]*"                      # a capitalised word, apostrophes and hyphens allowed
_FIRST = "|".join(sorted(map(re.escape, FIRST_NAMES)))
_TITLE_RE = re.compile(rf"\b(?:{'|'.join(TITLES)})\.?\s+({_WORD})(?:\s+({_WORD}))?")
_FULL_RE = re.compile(rf"\b(?:{_FIRST})\s+{_WORD}")
_GREET_RE = re.compile(rf"\b(?:{'|'.join(GREETINGS)}),?\s+({_FIRST})\b")
# --solution-only-end


def find_names(text):
    """PERSON spans from three rules. The span never includes a title or a greeting.

    A. TITLE rule: a title from TITLES (optional full stop) then a capitalised word. If that word
       is in FIRST_NAMES and another capitalised word follows, the name is both words ("Mrs Aoife
       O'Neill" -> "Aoife O'Neill"); otherwise only the first ("Dr Sutton" -> "Sutton").
    B. FULL-NAME rule: a word from FIRST_NAMES followed by a capitalised word ("Tom Reilly").
    C. GREETING rule: a greeting from GREETINGS, an optional comma, then a word from FIRST_NAMES
       ("Hi Priya", "Thanks, Marcus"): the span is the first name alone.
    Rules may produce overlapping spans (rules A and B both find "Aoife O'Neill"); return the
    distinct spans, sorted. Case matters: "Grace period" is not a name."""
    spans = []
    for m in _TITLE_RE.finditer(text):
        end = m.end(2) if m.group(2) and m.group(1) in FIRST_NAMES else m.end(1)
        spans.append(Span(m.start(1), end, "PERSON"))
    for m in _FULL_RE.finditer(text):
        spans.append(Span(m.start(), m.end(), "PERSON"))
    for m in _GREET_RE.finditer(text):
        spans.append(Span(m.start(1), m.end(1), "PERSON"))
    return sorted(set(spans))


def find_places(text):
    """PLACE spans: every whole-word, case-sensitive occurrence of a name in PLACES, sorted.
    Overlapping matches (Newcastle inside Newcastle upon Tyne) are all returned; resolve() picks."""
    spans = []
    for place in PLACES:
        for m in re.finditer(r"\b" + re.escape(place) + r"\b", text):
            spans.append(Span(m.start(), m.end(), "PLACE"))
    return sorted(spans)


def resolve(spans):
    """One kind per character. Given possibly overlapping, possibly duplicated spans, return a
    sorted list of non-overlapping spans: consider spans longest first (ties: earlier kind in
    KINDS, then earlier start) and keep a span only if it overlaps nothing kept so far.
    Touching spans (one ends where the next starts) do not overlap. The input is not changed."""
    order = sorted(set(spans), key=lambda s: (-(s.end - s.start), KINDS.index(s.kind), s.start))
    kept = []
    for s in order:
        if all(s.end <= k.start or s.start >= k.end for k in kept):
            kept.append(s)
    return sorted(kept)


def detect(text):
    """Every PII span in `text`, resolved: structured, names and places combined."""
    return resolve(find_structured(text) + find_names(text) + find_places(text))


# =============================================================================
# Milestone 3: stable tokens and a vault
# =============================================================================
def normalise(kind, value):
    """The form in which two mentions count as the same value.

    EMAIL, PERSON, PLACE: lower-cased (casefold) with runs of whitespace collapsed to one space.
    PHONE: only digits and '+' kept.  CARD: digits only.  IBAN: no whitespace, upper case.
    Any other kind: unchanged."""
    if kind in ("EMAIL", "PERSON", "PLACE"):
        return " ".join(value.casefold().split())
    if kind == "PHONE":
        return re.sub(r"[^\d+]", "", value)
    if kind == "CARD":
        return re.sub(r"\D", "", value)
    if kind == "IBAN":
        return re.sub(r"\s", "", value).upper()
    return value


class Vault:
    """Maps tokens to real values. Tokens look like [PERSON_1]: the kind, then a counter that
    starts at 1 for each kind and rises in order of first appearance. The same normalised value
    always gets the same token, so a model can still tell that two mentions are one person.
    In a real system the vault is an encrypted store behind its own access control; here it is
    a dictionary."""

    def __init__(self):
        self._token_of = {}      # (kind, normalised value) -> token
        self._entry = {}         # token -> (kind, first surface form seen)
        self._count = {}         # kind -> how many tokens issued

    def token_for(self, kind, value):
        """The token for `value`, issuing a new one the first time its normalised form is seen.
        The first surface form seen is what lookup() later returns."""
        key = (kind, normalise(kind, value))
        if key not in self._token_of:
            n = self._count.get(kind, 0) + 1
            self._count[kind] = n
            token = f"[{kind}_{n}]"
            self._token_of[key] = token
            self._entry[token] = (kind, value)
        return self._token_of[key]

    def lookup(self, token):
        """(kind, value) for a token this vault issued, else None. (GIVEN)"""
        return self._entry.get(token)

    def __len__(self):
        return len(self._entry)


def redact(text, spans, vault):
    """`text` with every span replaced. The spans may overlap or repeat: pass them through
    resolve() first. A span whose kind is in GENERALISE is replaced by "[KIND-YYYY]" with the
    four-digit year found inside it (nothing is stored); every other span becomes
    vault.token_for(kind, the text it covers)."""
    out, pos = [], 0
    for s in resolve(spans):
        out.append(text[pos:s.start])
        value = text[s.start:s.end]
        if s.kind in GENERALISE:
            year = re.search(r"\d{4}", value).group()
            out.append(f"[{s.kind}-{year}]")
        else:
            out.append(vault.token_for(s.kind, value))
        pos = s.end
    out.append(text[pos:])
    return "".join(out)


def restore(text, vault, allow=None):
    """Put real values back. Every token in `text` that the vault issued is replaced by its
    value, except that when `allow` is a set of kinds, only tokens of those kinds are replaced.
    Unknown tokens and anything else are left exactly as they are. One pass: restored values
    are never searched for tokens again."""
    def swap(m):
        entry = vault.lookup(m.group())
        if entry is None or (allow is not None and entry[0] not in allow):
            return m.group()
        return entry[1]
    return TOKEN_RE.sub(swap, text)


# =============================================================================
# Milestone 4: who may look, and a log that notices tampering
# =============================================================================
def _digest(entry):
    """GIVEN. SHA-256 of an entry's fields (without its own 'hash'), as canonical JSON."""
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class AuditLog:
    """An append-only list of access records in which each entry carries the hash of the one
    before it, so changing, deleting or reordering an earlier entry breaks every hash after it.
    Time is a counter (1, 2, 3 ...) so a run is repeatable; a real log uses a trusted clock."""

    def __init__(self):
        self.entries = []

    def head(self):
        """The hash of the newest entry, or GENESIS when the log is empty. (GIVEN)"""
        return self.entries[-1]["hash"] if self.entries else GENESIS

    def append(self, user, role, action, token, kind, outcome, reason, purpose):
        """Add one entry and return it. The entry is a dict with exactly these keys:
        seq (1-based position), time (equals seq), user, role, action, token, kind, outcome,
        reason, purpose, prev (the previous entry's hash, or GENESIS) and hash (_digest of all
        the other keys)."""
        entry = {"seq": len(self.entries) + 1, "time": len(self.entries) + 1, "user": user, "role": role,
                 "action": action, "token": token, "kind": kind, "outcome": outcome, "reason": reason,
                 "purpose": purpose, "prev": self.head()}
        entry["hash"] = _digest(entry)
        self.entries.append(entry)
        return entry

    def verify(self, expected_head=None):
        """Index (0-based) of the first entry that cannot be trusted, or None if the log is intact.
        Entry i is bad if its 'prev' is not the hash of entry i - 1 (GENESIS for i = 0) or its
        'hash' is not _digest(entry). If every entry is fine and expected_head is given but is not
        the last hash, the tail was cut off: return len(entries), the index of the first missing
        entry."""
        prev = GENESIS
        for i, e in enumerate(self.entries):
            if e["prev"] != prev or e["hash"] != _digest(e):
                return i
            prev = e["hash"]
        if expected_head is not None and expected_head != prev:
            return len(self.entries)
        return None


def reveal(text, vault, user, role, purpose, log, policy=POLICY):
    """Show `user` the real values behind the tokens in `text`, as far as the policy allows, and
    log every decision. Returns the text with the allowed tokens restored.

    For each DISTINCT token in `text`, in order of first appearance, decide and call
    log.append(user, role, "reveal", token, kind, outcome, reason, clean_purpose(purpose)) with kind
    None for an unknown token, outcome "allowed" or "denied", and the first reason that applies:
      unknown_token   the vault never issued it
      unknown_role    `role` is not a key of `policy`
      bad_purpose     `purpose` is not in PURPOSES
      kind_not_allowed  the kind is not in policy[role]
      ok              allowed
    Never put a real value into the log."""
    seen = []
    for m in TOKEN_RE.finditer(text):
        if m.group() not in seen:
            seen.append(m.group())
    allowed_kinds = set()
    for tok in seen:
        entry = vault.lookup(tok)
        kind = entry[0] if entry else None
        if entry is None:
            reason = "unknown_token"
        elif role not in policy:
            reason = "unknown_role"
        elif purpose not in PURPOSES:
            reason = "bad_purpose"
        elif kind not in policy[role]:
            reason = "kind_not_allowed"
        else:
            reason = "ok"
        if reason == "ok":
            allowed_kinds.add(kind)
        log.append(user, role, "reveal", tok, kind, "allowed" if reason == "ok" else "denied", reason, clean_purpose(purpose))
    return restore(text, vault, allow=allowed_kinds)


# =============================================================================
# Milestone 5: how much does the detector miss?
# =============================================================================
def score_spans(gold, pred):
    """Exact-match counts per kind. `gold` and `pred` are lists of (start, end, kind) triples
    (lists or Spans). A predicted span is a true positive if the identical triple is in gold.
    Returns {kind: {"tp": ., "fp": ., "fn": .}} for every kind in KINDS (zeros if unseen)."""
    g = {tuple(x) for x in gold}
    p = {tuple(x) for x in pred}
    out = {k: {"tp": 0, "fp": 0, "fn": 0} for k in KINDS}
    for x in p:
        out[x[2]]["tp" if x in g else "fp"] += 1
    for x in g:
        if x not in p:
            out[x[2]]["fn"] += 1
    return out


def prf(tp, fp, fn):
    """(precision, recall, f1). precision = tp / (tp + fp), or 1.0 when nothing was predicted;
    recall = tp / (tp + fn), or 1.0 when there was nothing to find; f1 = their harmonic mean,
    or 0.0 when both are 0."""
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def evaluate(docs, detector):
    """Run `detector(text) -> spans` over every doc (docs as from load_corpus) and report.

    Returns {"kinds": {kind: {tp, fp, fn, precision, recall, f1, recall_lo, recall_hi}},
             "ALL": the same keys summed over kinds,
             "leaked": [(doc id, start, end, kind), ...],
             "indirect": (surviving, total)}.
    (recall_lo, recall_hi) is wilson(tp, tp + fn). A gold span has LEAKED if some character of it
    is not covered by any predicted span (a partial hit still leaves part of the value in the
    redacted text); list the leaks in document order, then start order. `indirect` counts the
    phrases in each doc's "indirect" list that are still present in the text after redact()
    with a fresh Vault, against the total number of such phrases."""
    totals = {k: {"tp": 0, "fp": 0, "fn": 0} for k in KINDS}
    leaked, surviving, total = [], 0, 0
    for doc in docs:
        pred = detector(doc["text"])
        for kind, c in score_spans(doc["spans"], pred).items():
            for key in c:
                totals[kind][key] += c[key]
        covered = set()
        for s in pred:
            covered.update(range(s[0], s[1]))
        for s, e, kind in sorted(doc["spans"]):
            if any(i not in covered for i in range(s, e)):
                leaked.append((doc["id"], s, e, kind))
        redacted = redact(doc["text"], pred, Vault())
        for phrase in doc["indirect"]:
            total += 1
            surviving += phrase in redacted

    def finish(c):
        p, r, f = prf(c["tp"], c["fp"], c["fn"])
        lo, hi = wilson(c["tp"], c["tp"] + c["fn"])
        return dict(c, precision=p, recall=r, f1=f, recall_lo=lo, recall_hi=hi)

    kinds = {k: finish(c) for k, c in totals.items()}
    allc = {key: sum(c[key] for c in totals.values()) for key in ("tp", "fp", "fn")}
    return {"kinds": kinds, "ALL": finish(allc), "leaked": leaked, "indirect": (surviving, total)}


# =============================================================================
# Milestone 6: a tripwire, and the pipeline around a model
# =============================================================================
class LeakBlocked(Exception):
    """Raised when text that should be clean still looks sensitive. Carries the reason codes."""


def tripwire(text):
    """A deliberately over-sensitive second check run on text that has ALREADY been redacted.
    Returns a sorted list of reason codes (empty means clean):
      long_digits   a run of 9 or more digits, optionally separated by single spaces or dashes
      at_sign       an '@' anywhere
      iban_shape    two capital letters, two digits, then two or more groups of four capitals or
                    digits (checksum NOT tested: a look-alike still trips it)
    It must not trip on tokens such as [PHONE_1] or generalised dates such as [DATE-2025]."""
    codes = []
    if re.search(r"\d(?:[ -]?\d){8,}", text):
        codes.append("long_digits")
    if "@" in text:
        codes.append("at_sign")
    if re.search(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,}\b", text):
        codes.append("iban_shape")
    return sorted(codes)


def answer(model, vault, log, doc, user, role, purpose, policy=POLICY):
    """Summarise `doc` with `model` without the model ever seeing a raw identifier.

    1. spans = detect(doc); safe = redact(doc, spans, vault).
    2. codes = tripwire(safe). If there are any: log.append(user, role, "blocked", None, None,
       "blocked", ",".join(codes), clean_purpose(purpose)) and raise LeakBlocked(codes). The model is not called.
    3. Ask the model: model.complete([{"role": "user", "content": safe}], system=SYSTEM).
    4. masked = text_of(reply); shown = reveal(masked, vault, user, role, purpose, log, policy).
    Returns {"prompt": safe, "masked": masked, "reply": shown}."""
    safe = redact(doc, detect(doc), vault)
    codes = tripwire(safe)
    if codes:
        log.append(user, role, "blocked", None, None, "blocked", ",".join(codes), clean_purpose(purpose))
        raise LeakBlocked(codes)
    resp = model.complete([{"role": "user", "content": safe}], system=SYSTEM)
    masked = text_of(resp)
    shown = reveal(masked, vault, user, role, purpose, log, policy)
    return {"prompt": safe, "masked": masked, "reply": shown}
