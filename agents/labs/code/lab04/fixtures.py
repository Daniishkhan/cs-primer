"""fixtures.py: the world Lab 4 runs in. GIVEN: do not edit.

Everything here is deterministic. `desk_model` is a stand-in "language model": one plain function
from (messages, tools, system) to a reply that behaves differently depending on which workflow step
is calling it (it reads the first word of the system prompt). Real models are probabilistic; this
one is fixed so that token counts, prices and times are exactly reproducible.

    TICKETS      24 labelled support tickets (with what the stand-in classifier will say about each)
    JUDGE_ITEMS  200 yes/no items for the voting experiment, 20% of them "hard" for every judge
    POLICY_DAYS  refund windows per branch, for the orchestrator-workers task
    make_model() a fresh ScriptedModel(desk_model) that also records every request
"""
import hashlib
import json
import re

from llm import ScriptedModel

ORDERS = {
    "A-1001": {"status": "shipped", "eta": "Friday"},
    "A-1002": {"status": "processing", "eta": "Monday"},
    "A-1003": {"status": "delivered", "eta": "Tuesday"},
    "A-1004": {"status": "shipped", "eta": "Thursday"},
}
POLICY_DAYS = {"Leeds": 30, "Derby": 14, "York": 45, "Hull": 28, "Bath": 60}

# (id, text, true intent, label the stand-in classifier gives, its confidence)
_RAW = [
    ("T01", "Where is my parcel A-1001? It was due yesterday.", "tracking", "tracking", 0.88),
    ("T02", "Order A-1004 has not arrived and it is late.", "tracking", "tracking", 0.90),
    ("T03", "Has A-1002 shipped yet?", "tracking", "tracking", 0.84),
    ("T04", "My delivery never came and nobody has told me why.", "tracking", "tracking", 0.79),
    ("T05", "Tracking says delivered but A-1003 is not here.", "tracking", "tracking", 0.86),
    ("T06", "Where is it?? I have waited a week.", "tracking", "tracking", 0.66),
    ("T07", "Can you check on A-1001 for me please", "tracking", "tracking", 0.72),
    ("T08", "Parcel A-1004 is late again, this is the third time.", "tracking", "tracking", 0.91),
    ("T09", "I want my money back for A-1003, it arrived broken.", "refund", "refund", 0.93),
    ("T10", "Please refund A-1001, I ordered it twice.", "refund", "refund", 0.95),
    ("T11", "Refund me now or I will dispute the charge.", "refund", "refund", 0.91),
    ("T12", "Money back on A-1004 please.", "refund", "refund", 0.92),
    ("T13", "Where is my refund for A-1003?", "refund", "tracking", 0.64),
    ("T14", "The charge on my card was wrong, can I get it back?", "refund", "refund", 0.62),
    ("T15", "I cannot log in to my account.", "account", "account", 0.90),
    ("T16", "Reset my password please.", "account", "account", 0.93),
    ("T17", "How do I change my email address?", "account", "account", 0.85),
    ("T18", "My account is locked after too many tries.", "account", "account", 0.88),
    ("T19", "Why can't I sign in on my phone?", "account", "account", 0.68),
    ("T20", "Your driver was lovely, thank you!", "other", "other", 0.41),
    ("T21", "Do you have a shop in Leeds?", "other", "other", 0.38),
    ("T22", "Can I speak to a manager about something unrelated to orders?", "other", "account", 0.58),
    ("T23", "Refund please, and reset my password.", "multi", "refund", 0.93),
    ("T24", "Where is A-1002? Also I want my money back if it is late.", "multi", "tracking", 0.81),
]
TICKETS = [{"id": i, "text": t, "intent": intent, "model_label": lab, "model_conf": c} for i, t, intent, lab, c in _RAW]
_BY_TEXT = {t["text"]: t for t in TICKETS}

# 200 yes/no items ("does this ticket need a human?"); every fifth is hard for ALL judges alike.
JUDGE_ITEMS = []
for _i in range(200):
    _h = int(hashlib.sha256(f"truth:{_i}".encode()).hexdigest(), 16)
    JUDGE_ITEMS.append({"id": f"J{_i:03d}", "text": f"Ticket J{_i:03d}: customer message number {_i} about an order problem.",
                        "truth": "yes" if _h % 2 else "no", "hard": _i % 5 == 0})
_ITEM_BY_ID = {it["id"]: it for it in JUDGE_ITEMS}
JUDGE_Q = 0.875        # chance a judge is right on a non-hard item, so one judge is right 0.8 x 0.875 = 70% overall


def _judge(system, user):
    k = int(re.match(r"JUDGE-(\d+)", system).group(1))
    item = _ITEM_BY_ID[re.search(r"Ticket (J\d+)", user).group(1)]
    flip = {"yes": "no", "no": "yes"}
    if item["hard"]:
        return flip[item["truth"]]                              # every judge fooled in the same way
    h = int(hashlib.sha256(f"{item['id']}:{k}".encode()).hexdigest(), 16) % 1000
    return item["truth"] if h < JUDGE_Q * 1000 else flip[item["truth"]]


def desk_model(messages, tools, system):
    """The stand-in model. The first word of the system prompt says which step is calling."""
    user = messages[-1]["content"]
    word = system.split()[0].rstrip(":")
    if word == "EXTRACT":
        m = re.search(r"\b([A-Z]-\d{4})\b", user)
        late = re.search(r"late|not arrived|never came|due|waited|not here", user)
        return json.dumps({"order_id": m.group(1) if m else None, "issue": "late" if late else "other"})
    if word == "DRAFT":
        d = json.loads(user.split("FACTS:", 1)[1])
        return (f"Sorry about the wait with order {d['order_id']}. It is {d['status']} and should arrive "
                f"on {d['eta']}. Reply here if it does not.")
    if word == "CLASSIFY":
        t = _BY_TEXT.get(user)
        return f"{t['model_label']}|{t['model_conf']:.2f}" if t else "other|0.30"
    if word.startswith("HANDLE-"):
        return f"[{word[7:]}] I have passed this to the {word[7:]} team and will update you: " + user[:50]
    if word.startswith("CHECK-"):
        low = user.lower()
        bad = {"CHECK-pii": "password" in low or "@" in low, "CHECK-tone": "??" in low or " now or " in low,
               "CHECK-policy": "dispute" in low or "manager" in low}[word]
        return "flag: needs a look" if bad else "ok"
    if word.startswith("JUDGE-"):
        return _judge(system, user)
    if word == "PLAN":
        return json.dumps([{"task": f"Find the refund window for {c}", "city": c}
                           for c in re.findall(r"\b(Leeds|Derby|York|Hull|Bath)\b", user)])
    if word == "WORK":
        c = re.search(r"for (\w+)", user).group(1)
        return f"{c}: {POLICY_DAYS[c]} days"
    if word == "SYNTH":
        facts = sorted(user.splitlines(), key=lambda s: int(re.search(r"(\d+) days", s).group(1)))
        return f"Shortest window: {facts[0]}. Longest: {facts[-1]}."
    return "?"


def make_model():
    """A fresh stand-in model. Its .calls list keeps every request it received."""
    return ScriptedModel(desk_model)
