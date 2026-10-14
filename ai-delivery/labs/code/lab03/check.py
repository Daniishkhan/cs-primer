"""Self-check for Lab 3: A PII Redaction & Audit Pipeline.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 4       # only milestone 4
    python3 check.py solution 1 7     # milestone 1, replaying ONLY the random cases of seed 7

Every person, number and account in corpus.jsonl and in this file is invented. No model is
called and no network is used: the "model" is a scripted stand-in from llm.py. Randomness is
seeded, and a failure prints its seed. The whole check takes well under a second.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import contextlib
import importlib
import json
import os
import random
import re
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


def expect(cond, msg):
    assert cond, msg


def S(start, end, kind):
    return mod.Span(start, end, kind)


def slices(text, spans):
    return [(text[s.start:s.end], s.kind) for s in spans]


def digits_valid_oracle(digits):
    """Independent Luhn: double every second digit from the right using a lookup table."""
    double = [0, 2, 4, 6, 8, 1, 3, 5, 7, 9]
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        total += double[d] if i % 2 == 1 else d
    return total % 10 == 0


def make_card(rng, n=16):
    body = "".join(str(rng.randrange(10)) for _ in range(n - 1))
    body = str(rng.randrange(3, 6)) + body[1:]
    return next(body + str(c) for c in range(10) if digits_valid_oracle(body + str(c)))


def make_iban(rng):
    cc = rng.choice(["GB", "IE", "DE", "FR", "NL", "ES"])
    bban = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(rng.randint(14, 20)))
    n = "".join(str(int(c, 36)) for c in bban + cc + "00")
    return f"{cc}{98 - int(n) % 97:02d}{bban}"


def grouped(s, rng, seps=(" ", "-", "")):
    sep = rng.choice(seps)
    return sep.join(s[i:i + 4] for i in range(0, len(s), 4))


def resolve_oracle(spans):
    """The check's own copy of the longest-first rule, so milestone 1 does not depend on milestone 2."""
    kept = []
    for s in sorted(set(spans), key=lambda s: (-(s[1] - s[0]), mod.KINDS.index(s[2]), s[0])):
        if all(s[1] <= k[0] or s[0] >= k[1] for k in kept):
            kept.append(s)
    return sorted(kept)


def corpus():
    return mod.load_corpus()


# =============================================================================
# Milestone 1: checksums and structured identifiers
# =============================================================================
def m1():
    for good in ("4539 8997 2074 3225", "4111111111111111", "5555-0983-6607-5408", "4716 2131 2205 0764"):
        expect(mod.luhn_valid(good) is True, f"luhn_valid({good!r}) should be True (a real Luhn-valid test number); got {mod.luhn_valid(good)!r}")
    for bad in ("4539 8997 2074 3226", "4929 2260 0621 9588", "1234 5678 9012 3456"):
        expect(mod.luhn_valid(bad) is False, f"luhn_valid({bad!r}) should be False: the checksum fails, so it is an order or policy number, not a card; got {mod.luhn_valid(bad)!r}")
    expect(mod.luhn_valid("0000 0000 0000") is False and mod.luhn_valid("0" * 20) is False,
           "fewer than 13 or more than 19 digits is never a card, even if the checksum is 0 (all zeros pass the arithmetic)")
    expect(mod.luhn_valid("") is False, "an empty string is not a card")
    for good in ("GB29 NWBK 6016 1331 9268 19", "IE29AIBK93115212345678", "de89 3704 0044 0532 0130 00", "NL91 ABNA 0417 1643 00"):
        expect(mod.iban_valid(good) is True, f"iban_valid({good!r}) should be True (published example IBAN); got {mod.iban_valid(good)!r}. "
               "Move the first four characters to the end, turn letters into numbers (A=10), and test number % 97 == 1")
    for bad in ("GB29 NWBK 6016 1331 9268 18", "FR14 2004 1010 0505 0001 3M02 607", "GB29", "1234 5678", "GB29 NWBK 6016 1331 9268 19 99999999999999999999999"):
        expect(mod.iban_valid(bad) is False, f"iban_valid({bad!r}) should be False; got {mod.iban_valid(bad)!r}")

    text = "Mail a.b@example.com or call +44 7700 900123 about card 4539 8997 2074 3225 and GB29 NWBK 6016 1331 9268 19 on 14 March 2025."
    got = slices(text, mod.find_structured(text))
    want = [("a.b@example.com", "EMAIL"), ("+44 7700 900123", "PHONE"), ("4539 8997 2074 3225", "CARD"),
            ("GB29 NWBK 6016 1331 9268 19", "IBAN"), ("14 March 2025", "DATE")]
    expect(got == want, f"find_structured on a line with one of each kind:\n  expected {want}\n  got      {got}")
    spans = mod.find_structured(text)
    expect(spans == sorted(spans) and all(isinstance(s, mod.Span) for s in spans), "return Span(start, end, kind) tuples sorted by position")
    text = "Policy 4929 2260 0621 9588 and ref GB29 NWBK 6016 1331 9268 18 are look-alikes; 03/07/2025 is a date."
    got = slices(text, mod.find_structured(text))
    expect(got == [("03/07/2025", "DATE")], f"a 16-digit number that fails Luhn and an IBAN-shaped string that fails mod 97 must NOT be reported; expected only the date, got {got}")
    expect(mod.find_structured("") == [] and mod.find_structured("nothing to see here, ORD-0045821") == [], "no structured data means an empty list")
    for s in seeds(range(1, 21)):
        rng = random.Random(s)
        card, iban = make_card(rng, rng.choice([15, 16, 16, 19])), make_iban(rng)
        cg, ig = grouped(card, rng), grouped(iban, rng, (" ", ""))
        text = f"x {cg} and {ig} end"
        got = slices(text, mod.find_structured(text))
        expect((cg, "CARD") in got and (ig, "IBAN") in got,
               f"seed {s}: valid card {cg!r} and IBAN {ig!r} in {text!r} should both be found; got {got}")
        pos = rng.randrange(len(card))
        bad = card[:pos] + str((int(card[pos]) + rng.randint(1, 9)) % 10) + card[pos + 1:]
        text = f"x {grouped(bad, rng)} y"
        expect(not any(k == "CARD" for _, k in slices(text, mod.find_structured(text))),
               f"seed {s}: changing one digit of a card breaks the Luhn sum, so {grouped(bad, rng)!r} must not be reported as CARD")
    found = bad = 0
    for d in corpus():
        want = sorted(tuple(x) for x in d["spans"] if x[2] in ("EMAIL", "PHONE", "CARD", "IBAN", "DATE"))
        got = resolve_oracle([tuple(x) for x in mod.find_structured(d["text"])])
        expect(got == want, f"{d['id']}: structured spans differ (after dropping overlaps, longest first; note that digits inside an IBAN can look like a phone number)\n  text     {d['text']}\n  expected {[(d['text'][a:b], k) for a, b, k in want]}\n  got      {[(d['text'][a:b], k) for a, b, k in got]}")
        found += len(want)
    return f"Luhn and mod-97 checks right on the published examples; all {found} structured identifiers in the corpus found, and the look-alikes (a policy number, a bad IBAN) left alone"


# =============================================================================
# Milestone 2: names, places and resolution
# =============================================================================
def m2():
    names = lambda t: slices(t, mod.find_names(t))
    expect(names("Dear Mrs Aoife O'Neill, hello") == [("Aoife O'Neill", "PERSON")], f"title + known first name + surname is one name without the title; got {names('Dear Mrs Aoife O' + chr(39) + 'Neill, hello')}")
    expect(("Sutton", "PERSON") in names("Call from Dr Sutton about it") and len(names("Call from Dr Sutton about it")) == 1,
           f"title + unknown word: just that word ('Sutton'), and the lower-case 'about' is not part of it; got {names('Call from Dr Sutton about it')}")
    expect(names("Mr Tadeusz Wiśniewski wants") == [("Tadeusz", "PERSON")], f"after a title, a second word is joined only if the first is a KNOWN first name (this is a real limitation: the surname leaks); got {names('Mr Tadeusz Wiśniewski wants')}")
    got = names("Dr. Okafor wrote.")
    expect(("Okafor", "PERSON") in got, f"an optional full stop after the title is allowed; got {got}")
    expect(names("Regards, Tom Reilly.") == [("Tom Reilly", "PERSON")], f"known first name + capitalised word; got {names('Regards, Tom Reilly.')}")
    expect(names("The grace period ends; Will you call? Mark the date.") == [], f"'Grace period' (lower case) and 'Will you' / 'Mark the' are not names; got {names('The grace period ends; Will you call? Mark the date.')}")
    expect(names("Hi Priya, thanks") == [("Priya", "PERSON")] and names("Thanks, Marcus. Fine.") == [("Marcus", "PERSON")] and names("Thank you, Kofi!") == [("Kofi", "PERSON")],
           f"greeting + known first name gives the first name alone; got {names('Hi Priya, thanks')}, {names('Thanks, Marcus. Fine.')}, {names('Thank you, Kofi!')}")
    expect(names("Hello, this is the team") == [], "a greeting followed by something that is not a known first name finds nothing")
    both = names("Dear Daniel Moreau,")
    expect(("Daniel Moreau", "PERSON") in both and ("Daniel", "PERSON") in both,
           f"find_names returns every rule's span, overlaps included (resolve picks later); got {both}")
    places = lambda t: slices(t, mod.find_places(t))
    expect(places("He moved from Cork to Kraków, not Corkery.") == [("Cork", "PLACE"), ("Kraków", "PLACE")], f"whole words only, so 'Corkery' is not Cork; got {places('He moved from Cork to Kraków, not Corkery.')}")
    expect(places("cork and dublin") == [], "place matching is case-sensitive (a lower-case 'cork' is a material)")
    got = places("Newcastle upon Tyne and Newcastle")
    expect(got == [("Newcastle", "PLACE"), ("Newcastle upon Tyne", "PLACE"), ("Newcastle", "PLACE")] or got == [("Newcastle upon Tyne", "PLACE"), ("Newcastle", "PLACE"), ("Newcastle", "PLACE")] or sorted(got) == sorted([("Newcastle", "PLACE"), ("Newcastle upon Tyne", "PLACE"), ("Newcastle", "PLACE")]),
           f"find_places returns every match, including the shorter Newcastle inside Newcastle upon Tyne; got {got}")

    a, b, c, d = S(0, 10, "PLACE"), S(5, 8, "PERSON"), S(10, 14, "PHONE"), S(0, 10, "PERSON")
    inp = [a, b, c, d, a]
    keep = list(inp)
    r = mod.resolve(inp)
    expect(inp == keep, "resolve must not change its input list")
    expect(r == [S(0, 10, "PERSON"), S(10, 14, "PHONE")],
           f"longest wins; for equal length the earlier kind in KINDS wins (PERSON before PLACE); a span that only touches another (ends at 10, starts at 10) is kept; duplicates collapse. Got {r}")
    expect(mod.resolve([]) == [], "no spans, no result")
    expect(mod.resolve([S(0, 4, "PLACE"), S(2, 9, "EMAIL")]) == [S(2, 9, "EMAIL")], "a longer span beats a shorter one it overlaps, whatever the kind")
    expect(mod.resolve([S(3, 6, "PLACE"), S(3, 6, "CARD")]) == [S(3, 6, "CARD")], "same span, two kinds: CARD comes before PLACE in KINDS")
    for s in seeds(range(1, 31)):
        rng = random.Random(s)
        spans = []
        for _ in range(rng.randint(0, 12)):
            st = rng.randrange(0, 40)
            spans.append(S(st, st + rng.randint(1, 12), rng.choice(mod.KINDS)))
        r = mod.resolve(spans)
        expect(r == sorted(r), f"seed {s}: result must be sorted by start")
        expect(all(x.end <= y.start for x, y in zip(r, r[1:])), f"seed {s}: result must not overlap: {r}")
        expect(mod.resolve(r) == r, f"seed {s}: resolving twice changes nothing")
        expect(all(any(k.start < i.end and i.start < k.end for k in r) for i in spans), f"seed {s}: every input span must overlap (or be) a kept span, none may vanish")
        expect(set(r) <= set(spans), f"seed {s}: resolve may only keep spans it was given")
        longest = max((i.end - i.start for i in spans), default=0)
        expect(max((k.end - k.start for k in r), default=0) == longest, f"seed {s}: the longest input span is always kept")
    t = "Dr Sutton lives in Sutton; ring 020 7946 0321."
    got = slices(t, mod.detect(t))
    expect(got == [("Sutton", "PERSON"), ("Sutton", "PLACE"), ("020 7946 0321", "PHONE")],
           f"detect combines all finders then resolves; the doctor and the town share a spelling but not a span; got {got}")
    t = "Dear Daniel Moreau, Newcastle upon Tyne."
    got = slices(t, mod.detect(t))
    expect(got == [("Daniel Moreau", "PERSON"), ("Newcastle upon Tyne", "PLACE")], f"overlaps resolve to the longest span; got {got}")
    gold = sum(1 for d in corpus() for x in d["spans"] if x[2] in ("PERSON", "PLACE"))
    hit = sum(1 for d in corpus() for x in d["spans"] if x[2] in ("PERSON", "PLACE") and tuple(x) in {tuple(y) for y in mod.detect(d["text"])})
    expect(hit >= 38, f"on the corpus the rules should find at least 38 of the {gold} names and places exactly (the reference finds 40); you found {hit}. Print the misses with: python3 -c 'import solution'")
    return f"found {hit} of {gold} names and places on the corpus (the rest are names and places the lists do not know)"


# =============================================================================
# Milestone 3: tokens and the vault
# =============================================================================
def m3():
    n = mod.normalise
    expect(n("PERSON", "  Aoife   O'Neill ") == "aoife o'neill" and n("EMAIL", "Priya.Nair@Example.COM") == "priya.nair@example.com" and n("PLACE", "TRALEE") == "tralee",
           "EMAIL, PERSON and PLACE: case-folded with whitespace collapsed")
    expect(n("PHONE", "+44 (0)7700 900-123") == "+4407700900123" and n("PHONE", "087 123 4567") == "0871234567", f"PHONE keeps digits and '+': got {n('PHONE', '+44 (0)7700 900-123')!r}")
    expect(n("CARD", "4539-8997 2074 3225") == "4539899720743225" and n("IBAN", "gb29 nwbk 6016 1331 9268 19") == "GB29NWBK60161331926819", "CARD digits only; IBAN no spaces, upper case")
    expect(n("DATE", "14 March 2025") == "14 March 2025", "other kinds are returned unchanged")
    v = mod.Vault()
    t1 = v.token_for("PERSON", "Aoife O'Neill")
    expect(t1 == "[PERSON_1]", f"first PERSON token is [PERSON_1]; got {t1!r}")
    expect(v.token_for("PERSON", "TOM REILLY") == "[PERSON_2]" and v.token_for("PHONE", "087 123 4567") == "[PHONE_1]", "counters are per kind and rise in order of first appearance")
    expect(v.token_for("PERSON", "aoife  o'neill") == "[PERSON_1]", "the same person written another way keeps the same token")
    expect(v.token_for("PLACE", "aoife o'neill") == "[PLACE_1]", "the key includes the kind: the same text as another kind is a different value")
    expect(v.lookup("[PERSON_1]") == ("PERSON", "Aoife O'Neill"), f"lookup returns the FIRST surface form seen; got {v.lookup('[PERSON_1]')}")
    expect(v.lookup("[PERSON_9]") is None and len(v) == 4, "unknown token -> None; len counts issued tokens")

    v = mod.Vault()
    text = "Hi Priya, call 087 123 4567 or +353 87 123 4567. Thanks, Priya! Card 4539 8997 2074 3225 sent 14 March 2025."
    spans = mod.detect(text)
    out = mod.redact(text, spans, v)
    want = "Hi [PERSON_1], call [PHONE_1] or [PHONE_2]. Thanks, [PERSON_1]! Card [CARD_1] sent [DATE-2025]."
    expect(out == want, f"redact:\n  expected {want!r}\n  got      {out!r}")
    expect(len(v) == 4 and all("2025" not in str(v.lookup(t)) for t in ("[PERSON_1]", "[PHONE_1]")), "a generalised DATE is never stored in the vault (only 4 tokens: PERSON, 2 PHONE, CARD)")
    expect(mod.redact("nothing here", [], mod.Vault()) == "nothing here", "no spans, no change")
    dup = mod.redact(text, list(reversed(spans)) + spans, mod.Vault())
    expect(dup == want, f"redact must resolve its spans first (unsorted and duplicated spans are fine); got {dup!r}")
    back = mod.restore(out, v)
    expect(back == "Hi Priya, call 087 123 4567 or +353 87 123 4567. Thanks, Priya! Card 4539 8997 2074 3225 sent [DATE-2025].",
           f"restore brings back every stored value; dates were generalised and stay so; got {back!r}")
    expect(mod.restore(out, v, allow={"PERSON"}) == "Hi Priya, call [PHONE_1] or [PHONE_2]. Thanks, Priya! Card [CARD_1] sent [DATE-2025].", "allow={'PERSON'} restores only PERSON tokens")
    expect(mod.restore(out, v, allow=set()) == out, "allow=set() restores nothing")
    expect(mod.restore("see [PERSON_7] and [PERSON_1]", v) == "see [PERSON_7] and Priya", "tokens the vault never issued are left exactly as they are")
    w = mod.Vault()
    w.token_for("PERSON", "[PLACE_1]")
    w.token_for("PLACE", "Cork")
    expect(mod.restore("[PERSON_1]", w) == "[PLACE_1]", "restore is a single pass: a restored value that happens to look like a token is not replaced again")
    docs = corpus()
    shared = mod.Vault()
    for d in docs:
        v1 = mod.Vault()
        red = mod.redact(d["text"], mod.detect(d["text"]), v1)
        expected = d["text"]
        for s, e, k in sorted(d["spans"], reverse=True):
            if k == "DATE":
                year = re.search(r"[0-9]{4}", expected[s:e]).group()
                expected = expected[:s] + "[DATE-" + year + "]" + expected[e:]
        got = mod.restore(red, v1)
        # compare only on documents the detector fully covers (misses stay as plain text in both)
        miss = {x for x in map(tuple, d["spans"])} - {tuple(x) for x in mod.detect(d["text"])}
        if not miss:
            expect(got == expected, f"{d['id']}: restore(redact(text)) should equal the text with dates generalised\n  expected {expected!r}\n  got      {got!r}")
        mod.redact(d["text"], mod.detect(d["text"]), shared)
    expect(shared.lookup("[EMAIL_1]") is not None and len(shared) > 40, "a vault shared by many documents keeps counting")
    return "round trip exact on every fully detected document; same value, same token, across spellings and across documents; dates generalised, cards tokenised"


# =============================================================================
# Milestone 4: access policy and the audit log
# =============================================================================
def vault_with(*pairs):
    v = mod.Vault()
    for kind, value in pairs:
        v.token_for(kind, value)
    return v


def m4():
    log = mod.AuditLog()
    expect(log.head() == mod.GENESIS and log.verify() is None, "an empty log is intact and its head is GENESIS")
    e1 = log.append("ana", "support_agent", "reveal", "[PERSON_1]", "PERSON", "allowed", "ok", "dispute")
    expect(list(e1) == ["seq", "time", "user", "role", "action", "token", "kind", "outcome", "reason", "purpose", "prev", "hash"],
           f"entry keys, in this order: seq, time, user, role, action, token, kind, outcome, reason, purpose, prev, hash; got {list(e1)}")
    expect(e1["seq"] == 1 and e1["time"] == 1 and e1["prev"] == mod.GENESIS, "first entry: seq 1, time 1, prev GENESIS")
    expect(e1["hash"] == mod._digest(e1) and len(e1["hash"]) == 64, "hash is _digest(entry) of all the other keys")
    e2 = log.append("ana", "support_agent", "reveal", "[PHONE_1]", "PHONE", "denied", "kind_not_allowed", "dispute")
    expect(e2["seq"] == 2 and e2["prev"] == e1["hash"] and log.head() == e2["hash"], "each entry carries the hash of the one before; head() is the newest hash")
    expect(log.entries[0] is e1 and len(log.entries) == 2, "entries are stored in order in log.entries and append returns the stored entry")

    def fresh(n=6):
        lg = mod.AuditLog()
        for i in range(n):
            lg.append(f"u{i % 2}", "auditor", "reveal", f"[PERSON_{i}]", "PERSON", "denied", "kind_not_allowed", "audit")
        return lg

    lg = fresh()
    expect(lg.verify() is None, "an untouched log verifies (None)")
    head = lg.head()
    lg.entries[3]["outcome"] = "allowed"
    expect(lg.verify() == 3, f"editing entry 3 must be reported at index 3 (its hash no longer matches); got {lg.verify()}")
    lg = fresh()
    del lg.entries[2]
    expect(lg.verify() == 2, f"deleting entry 2 breaks the link of the entry that followed it, now at index 2; got {lg.verify()}")
    lg = fresh()
    lg.entries[1], lg.entries[2] = lg.entries[2], lg.entries[1]
    expect(lg.verify() == 1, f"swapping entries 1 and 2: the first bad one is index 1; got {lg.verify()}")
    lg = fresh()
    lg.entries[2]["outcome"] = "allowed"
    lg.entries[2]["hash"] = mod._digest(lg.entries[2])
    expect(lg.verify() == 3, f"an editor who recomputes entry 2's hash still breaks entry 3, which holds the old hash as its prev; expected 3, got {lg.verify()}")
    lg = fresh()
    head = lg.head()
    lg.entries.pop()
    expect(lg.verify() is None, "cutting the NEWEST entry leaves a chain that is internally consistent: verify() alone cannot see it")
    expect(lg.verify(expected_head=head) == 5, f"with the head hash saved elsewhere, a cut tail is detected: return len(entries) = 5; got {lg.verify(expected_head=head)}")
    lg = fresh()
    expect(lg.verify(expected_head=lg.head()) is None, "a correct expected_head is fine")
    lg = fresh()
    head = lg.head()
    lg.entries[-1]["outcome"] = "allowed"
    lg.entries[-1]["hash"] = mod._digest(lg.entries[-1])
    expect(lg.verify() is None and lg.verify(expected_head=head) == 6, "forging the last entry AND its hash passes the chain, but not the saved head")

    v = vault_with(("PERSON", "Aoife O'Neill"), ("PHONE", "087 123 4567"), ("EMAIL", "a.b@example.com"), ("CARD", "4539 8997 2074 3225"), ("IBAN", "IE29 AIBK 9311 5212 3456 78"))
    text = "[PERSON_1] rang from [PHONE_1], mail [EMAIL_1], card [CARD_1], again [PERSON_1], also [PLACE_4] and [IBAN_1]."
    P = mod.POLICY
    lg = mod.AuditLog()
    out = mod.reveal(text, v, "ana", "support_agent", "dispute", lg, P)
    expect(out == "Aoife O'Neill rang from 087 123 4567, mail [EMAIL_1], card [CARD_1], again Aoife O'Neill, also [PLACE_4] and [IBAN_1].",
           f"a support agent may reveal PERSON, PLACE and PHONE only; got {out!r}")
    got = [(e["token"], e["kind"], e["outcome"], e["reason"]) for e in lg.entries]
    want = [("[PERSON_1]", "PERSON", "allowed", "ok"), ("[PHONE_1]", "PHONE", "allowed", "ok"), ("[EMAIL_1]", "EMAIL", "denied", "kind_not_allowed"),
            ("[CARD_1]", "CARD", "denied", "kind_not_allowed"), ("[PLACE_4]", None, "denied", "unknown_token"), ("[IBAN_1]", "IBAN", "denied", "kind_not_allowed")]
    expect(got == want, f"one entry per DISTINCT token, in order of first appearance:\n  expected {want}\n  got      {got}")
    expect(all(e["action"] == "reveal" and e["user"] == "ana" and e["role"] == "support_agent" and e["purpose"] == "dispute" for e in lg.entries), "every entry records user, role, action and purpose")
    expect(lg.verify() is None, "the log written by reveal verifies")
    dump = json.dumps(lg.entries)
    for secret in ("Aoife", "087 123", "a.b@example", "4539", "AIBK"):
        expect(secret not in dump, f"the log must never contain a real value; found {secret!r}")
    lg = mod.AuditLog()
    out = mod.reveal(text, v, "fay", "fraud_analyst", "fraud_review", lg, P)
    expect("a.b@example.com" in out and "IE29 AIBK 9311 5212 3456 78" in out and "[CARD_1]" in out, f"a fraud analyst also sees EMAIL and IBAN, but nobody sees a CARD; got {out!r}")
    lg = mod.AuditLog()
    out = mod.reveal(text, v, "ola", "auditor", "audit", lg, P)
    expect("Aoife" not in out and "[PERSON_1] rang" in out and all(e["outcome"] == "denied" for e in lg.entries) and len(lg.entries) == 6, "an auditor sees nothing but every attempt is logged")
    lg = mod.AuditLog()
    out = mod.reveal("[PERSON_1]", v, "ana", "support_agent", "Aoife O'Neill is shouting about her card", lg, P)
    expect(out == "[PERSON_1]" and lg.entries[0]["reason"] == "bad_purpose" and "Aoife" not in json.dumps(lg.entries),
           f"a purpose that is not one of PURPOSES is refused (reason bad_purpose) and is NOT copied into the log, because free text carries PII; got {out!r}, {lg.entries}")
    lg = mod.AuditLog()
    out = mod.reveal("[PERSON_1]", v, "ana", "intern", "dispute", lg, P)
    expect(out == "[PERSON_1]" and lg.entries[0]["reason"] == "unknown_role", "an unknown role gets nothing and is logged as unknown_role")
    lg = mod.AuditLog()
    expect(mod.reveal("no tokens at all", v, "ana", "support_agent", "dispute", lg, P) == "no tokens at all" and lg.entries == [], "no tokens, no log entries")
    P2 = {"support_agent": {"PERSON", "CARD"}}
    lg = mod.AuditLog()
    out = mod.reveal("[CARD_1]", v, "ana", "support_agent", "dispute", lg, P2)
    expect(out == "4539 8997 2074 3225", "the policy is a parameter: reveal must read the dict it is given, not the module constant")
    return "policy matrix right (agent / fraud analyst / auditor); unknown tokens, roles and free-text purposes refused; log has no raw values; edit, delete, swap and cut-tail all detected"


# =============================================================================
# Milestone 5: measuring the detector
# =============================================================================
def m5():
    g = [(0, 4, "PERSON"), (10, 15, "PLACE"), (20, 24, "CARD")]
    p = [S(0, 4, "PERSON"), S(10, 14, "PLACE"), S(30, 33, "EMAIL")]
    r = mod.score_spans(g, p)
    expect(r["PERSON"] == {"tp": 1, "fp": 0, "fn": 0}, f"identical triple = true positive; got {r['PERSON']}")
    expect(r["PLACE"] == {"tp": 0, "fp": 1, "fn": 1}, f"a span with the wrong end is both a false positive and a miss (exact match); got {r['PLACE']}")
    expect(r["CARD"] == {"tp": 0, "fp": 0, "fn": 1} and r["EMAIL"] == {"tp": 0, "fp": 1, "fn": 0}, f"a missed card is a false negative, an invented email a false positive; got {r['CARD']}, {r['EMAIL']}")
    expect(set(r) == set(mod.KINDS) and r["IBAN"] == {"tp": 0, "fp": 0, "fn": 0}, "every kind in KINDS is present, with zeros when unseen")
    expect(mod.score_spans([[0, 4, "PERSON"]], [S(0, 4, "PERSON"), S(0, 4, "PERSON")])["PERSON"] == {"tp": 1, "fp": 0, "fn": 0}, "a repeated prediction counts once")
    expect(mod.prf(8, 2, 8) == (0.8, 0.5, 2 * 0.8 * 0.5 / 1.3), f"precision 8/10, recall 8/16, f1 their harmonic mean; got {mod.prf(8, 2, 8)}")
    expect(mod.prf(0, 0, 0) == (1.0, 1.0, 1.0), "nothing to find and nothing predicted is a perfect score by convention")
    expect(mod.prf(0, 3, 0) == (0.0, 1.0, 0.0) and mod.prf(0, 0, 3) == (1.0, 0.0, 0.0), f"all false positives -> precision 0, recall 1.0 (nothing to find), f1 0; all misses -> precision 1.0 (nothing predicted), recall 0, f1 0; got {mod.prf(0, 3, 0)} and {mod.prf(0, 0, 3)}")
    toy = [{"id": "a", "text": "Call Tom Reilly on 087 123 4567 now", "spans": [[5, 15, "PERSON"], [19, 31, "PHONE"]], "indirect": ["now"]},
           {"id": "b", "text": "Mr Tadeusz Wiśniewski in Cork", "spans": [[3, 21, "PERSON"], [25, 29, "PLACE"]], "indirect": []}]
    perfect = lambda t: [S(*x) for d in toy for x in d["spans"] if d["text"] == t]
    r = mod.evaluate(toy, perfect)
    expect(r["ALL"]["tp"] == 4 and r["ALL"]["fn"] == 0 and r["ALL"]["f1"] == 1.0 and r["leaked"] == [], f"a perfect detector scores 4 tp and no leaks; got {r['ALL']} and {r['leaked']}")
    expect(r["indirect"] == (1, 1), f"indirect phrases survive redaction (they are not in any span): expected (1, 1), got {r['indirect']}")
    partial = lambda t: [S(3, 10, "PERSON"), S(25, 29, "PLACE")] if t.startswith("Mr") else []
    r = mod.evaluate(toy, partial)
    expect(r["kinds"]["PERSON"]["tp"] == 0 and r["kinds"]["PERSON"]["fp"] == 1 and r["kinds"]["PERSON"]["fn"] == 2,
           f"on the toy docs the partial detector finds half a name: 0 tp, 1 fp, 2 fn for PERSON; got {r['kinds']['PERSON']}")
    expect(r["leaked"] == [("a", 5, 15, "PERSON"), ("a", 19, 31, "PHONE"), ("b", 3, 21, "PERSON")],
           f"leaks: the two gold spans of doc a (nothing predicted) and the partly covered name in b, in document order; got {r['leaked']}")
    lo, hi = r["kinds"]["PLACE"]["recall_lo"], r["kinds"]["PLACE"]["recall_hi"]
    ref_lo, ref_hi = mod.wilson(1, 1)
    expect(abs(lo - ref_lo) < 1e-12 and abs(hi - ref_hi) < 1e-12, "(recall_lo, recall_hi) is wilson(tp, tp + fn)")
    docs = corpus()
    r = mod.evaluate(docs, mod.detect)
    k = r["kinds"]
    for kind in ("CARD", "IBAN", "EMAIL", "PHONE", "DATE"):
        expect(k[kind]["precision"] == 1.0 and k[kind]["recall"] == 1.0, f"{kind}: structured kinds should be exact on this corpus (precision 1.0, recall 1.0); got {k[kind]['precision']:.2f} and {k[kind]['recall']:.2f}")
    expect(k["PERSON"]["precision"] >= 0.90 and k["PERSON"]["recall"] >= 0.75, f"PERSON precision should be at least 0.90 and recall at least 0.75; got {k['PERSON']['precision']:.2f} and {k['PERSON']['recall']:.2f}")
    expect(k["PLACE"]["recall"] >= 0.90 and k["PLACE"]["precision"] == 1.0, f"PLACE recall should be at least 0.90; got {k['PLACE']['recall']:.2f}")
    allc = r["ALL"]
    expect(allc["tp"] == sum(c["tp"] for c in k.values()) and allc["fn"] == sum(c["fn"] for c in k.values()), "ALL sums the kinds")
    leaked_kinds = sorted({x[3] for x in r["leaked"]})
    expect(set(leaked_kinds) <= {"PERSON", "PLACE"} and 5 <= len(r["leaked"]) <= 9, f"on the corpus a few names and places should leak, nothing else; got {r['leaked']}")
    expect(r["indirect"] == (4, 4), f"all 4 indirect identifiers ('the only chemist in the village', ...) survive redaction: no rule can find them; got {r['indirect']}")
    rows = ", ".join(f"{kind} {k[kind]['recall']:.2f}" for kind in ("PERSON", "PLACE", "EMAIL"))
    return (f"corpus of {len(docs)} messages: {allc['tp']} found, {allc['fp']} false alarm, {allc['fn']} missed (precision {allc['precision']:.1%}, recall {allc['recall']:.1%});\n"
            f"recall by kind: {rows}; {len(r['leaked'])} spans leaked (names and places only), {r['indirect'][0]} of {r['indirect'][1]} indirect identifiers survive")


# =============================================================================
# Milestone 6: the tripwire and the pipeline around a model
# =============================================================================
def m6():
    t = mod.tripwire
    expect(t("Call [PHONE_1] about [CARD_1] on [DATE-2025], ticket 55312, 1,284.50 EUR, ORD-0045821") == [], f"redacted text with tokens, short numbers and amounts is clean; got {t('Call [PHONE_1] about [CARD_1] on [DATE-2025], ticket 55312, 1,284.50 EUR, ORD-0045821')}")
    expect(t("ref 4929 2260 0621 9588") == ["long_digits"], f"16 digits in groups of four trip long_digits; got {t('ref 4929 2260 0621 9588')}")
    expect(t("id 123456789") == ["long_digits"] and t("id 12345678") == [], "9 digits trip it, 8 do not")
    expect(t("write to someone@example.com") == ["at_sign"], "an @ trips at_sign")
    expect(t("pay GB29 NWBK 6016 1331 9268 18 today") == ["iban_shape"] or t("pay GB29 NWBK 6016 1331 9268 18 today") == ["iban_shape", "long_digits"],
           f"an IBAN-shaped string trips iban_shape even though its checksum is wrong; got {t('pay GB29 NWBK 6016 1331 9268 18 today')}")
    expect(t("FR14 2004 1010 0505 0001 3M02 607 and a@b.co") == ["at_sign", "iban_shape", "long_digits"], f"codes are sorted; got {t('FR14 2004 1010 0505 0001 3M02 607 and a@b.co')}")
    docs = corpus()
    covered = []
    for d in docs:
        pred = {tuple(x) for x in mod.detect(d["text"])}
        if {tuple(x) for x in d["spans"]} <= pred and not d["indirect"]:
            covered.append(d)
    expect(len(covered) >= 18, f"the pipeline test needs documents your detector finds in full; only {len(covered)} qualify. Fix milestones 1 and 2 first")
    # 1. the model never sees a raw value; the agent gets names back, never a card
    model = mod.make_summariser()
    vault, log = mod.Vault(), mod.AuditLog()
    shown, blocked = 0, []
    for d in docs:
        try:
            res = mod.answer(model, vault, log, d["text"], "ana", "support_agent", "dispute")
        except mod.LeakBlocked as e:
            blocked.append((d["id"], list(e.args[0])))
            continue
        shown += 1
        if d in covered:
            for s, e, kind in d["spans"]:
                value = d["text"][s:e]
                if kind != "DATE":
                    expect(value not in res["prompt"], f"{d['id']}: the prompt to the model still contains {value!r}")
            expect("[" in res["masked"] or "unnamed" in res["masked"], f"{d['id']}: the model's reply should be built from placeholders; got {res['masked']!r}")
    sent = json.dumps(model.calls)
    for d in covered:
        for s, e, kind in d["spans"]:
            if kind != "DATE":
                expect(d["text"][s:e] not in sent, f"{d['id']}: the real value {d['text'][s:e]!r} reached the model (see model.calls)")
    expect(model.calls and all(c["system"] == mod.SYSTEM for c in model.calls), "every model call carries SYSTEM as its system prompt")
    expect(blocked == [("m06", ["long_digits"]), ("m17", ["iban_shape", "long_digits"])],
           f"exactly two messages hold look-alike numbers that detect() rightly ignores but the tripwire must stop: m06 (a policy number) and m17 (a bad IBAN). Got {blocked}")
    expect(len(model.calls) == len(docs) - 2, f"blocked messages must not be sent to the model at all; calls {len(model.calls)}, expected {len(docs) - 2}")
    nblocked = sum(1 for e in log.entries if e["action"] == "blocked")
    expect(nblocked == 2, f"each block is logged once with action 'blocked'; found {nblocked}")
    be = [e for e in log.entries if e["action"] == "blocked"][0]
    expect(be["outcome"] == "blocked" and be["reason"] == "long_digits" and be["token"] is None and be["kind"] is None and be["user"] == "ana", f"a block entry has outcome 'blocked', the codes as reason and no token or kind; got {be}")
    expect(log.verify() is None, "the log written by answer() verifies")
    dump = json.dumps(log.entries)
    for d in covered:
        for s, e, kind in d["spans"]:
            expect(d["text"][s:e] not in dump, f"{d['id']}: {d['text'][s:e]!r} found in the audit log")
    # 2. one message, three readers
    d = docs[0]
    v1, l1 = mod.Vault(), mod.AuditLog()
    r_agent = mod.answer(mod.make_summariser(), v1, l1, d["text"], "ana", "support_agent", "dispute")
    expect(r_agent["reply"] == "Summary: Aoife O'Neill has a query from Tralee and asks to be called on 087 123 4567.", f"agent reply; got {r_agent['reply']!r}")
    expect(r_agent["masked"] == "Summary: [PERSON_1] has a query from [PLACE_1] and asks to be called on [PHONE_1]." and r_agent["prompt"].startswith("Hello, my name is [PERSON_1]"), f"masked reply and prompt; got {r_agent}")
    r_aud = mod.answer(mod.make_summariser(), mod.Vault(), mod.AuditLog(), d["text"], "ola", "auditor", "audit")
    expect(r_aud["reply"] == r_aud["masked"], "an auditor gets the masked reply")
    # 3. a model that invents a placeholder
    v2, l2 = mod.Vault(), mod.AuditLog()
    r = mod.answer(mod.make_summariser(extra=" Escalate to [PERSON_99]."), v2, l2, d["text"], "ana", "support_agent", "complaint")
    expect(r["reply"].endswith("Escalate to [PERSON_99]."), f"an invented placeholder stays a placeholder; got {r['reply']!r}")
    bad = [e for e in l2.entries if e["token"] == "[PERSON_99]"]
    expect(len(bad) == 1 and bad[0]["reason"] == "unknown_token" and bad[0]["outcome"] == "denied", f"and the attempt is logged as unknown_token; got {bad}")
    # 4. tampering is caught
    tail = l1.head()
    l1.entries[1]["outcome"] = "denied"
    expect(l1.verify() == 1 and l1.verify(expected_head=tail) == 1, "editing the log after the fact is detected")
    return (f"{shown} of {len(docs)} messages summarised, {len(blocked)} stopped by the tripwire ({', '.join(b[0] for b in blocked)}); the model saw 0 raw values;\n"
            f"the agent saw names and phone numbers, the auditor only placeholders; {len(log.entries)} log entries, chain intact, no value in the log")


MILESTONES = [
    (1, "Milestone 1: checksums and structured identifiers", m1),
    (2, "Milestone 2: names, places and one answer for every character", m2),
    (3, "Milestone 3: stable tokens and a vault", m3),
    (4, "Milestone 4: who may look, and a log that notices tampering", m4),
    (5, "Milestone 5: how much does the detector miss?", m5),
    (6, "Milestone 6: the tripwire and the pipeline around a model", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 3 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
