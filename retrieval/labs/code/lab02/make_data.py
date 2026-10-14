"""Generates qrels.txt and the three run files for Lab 2 (already generated; you do not need to run this).

    python3 make_data.py

A synthetic test collection: 60 queries, 40 candidate documents per query, graded
judgements (0 to 3) for 30 of them, and three systems that each return their top 20.
The simulation: every candidate has a hidden relevance grade, and a system scores a
document as  strength * grade + noise.  "hybrid" is stronger than "bm25" and also finds
the relevant documents that share no words with the query (vocabulary mismatch, chapter 2);
"bm25-tuned" is bm25 with slightly different parameters, so it is almost the same system.
Scores are printed with one decimal, so ties happen, as they do in real runs.
"""
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
N_QUERIES, N_DOCS, N_JUDGED, DEPTH = 60, 40, 30, 20
NO_RELEVANT = {13, 47}              # queries whose judged documents are all non-relevant


def build(seed=2026):
    rng = random.Random(seed)
    qrels, runs = [], {"bm25": [], "bm25-tuned": [], "hybrid": []}
    for qi in range(1, N_QUERIES + 1):
        qid = f"q{qi:02d}"
        docs = [f"d{qi:02d}{j:02d}" for j in range(1, N_DOCS + 1)]
        hidden = {d: 0 for d in docs}
        if qi not in NO_RELEVANT:
            for d in rng.sample(docs, rng.choice([2, 3, 3, 4, 5, 6, 8])):
                hidden[d] = rng.choices([1, 2, 3], [3, 2, 1])[0]
        relevant = [d for d in docs if hidden[d]]
        unjudged = set(rng.sample([d for d in docs if hidden[d] == 0], N_DOCS - N_JUDGED))
        for d in docs:
            if d not in unjudged:
                qrels.append(f"{qid} 0 {d} {hidden[d]}")
        ease = rng.uniform(0.2, 1.8)                                  # how easy this query is
        mismatch = {d for d in relevant if rng.random() < 0.2}      # no words in common with the query
        shared = {d: rng.gauss(0, 1) for d in docs}                  # noise every system sees
        for name, lift, own in (("bm25", 0.0, 0.6), ("bm25-tuned", 0.0, 0.6), ("hybrid", 0.12, 0.6)):
            scored = []
            for d in docs:
                g = hidden[d]
                signal = ease * g + lift * g * (1.0 if name == "hybrid" else 0.0)
                if d in mismatch and name != "hybrid":
                    signal = 0.4 * g                                  # lexical retrievers barely see it
                score = signal + 0.8 * shared[d] + own * rng.gauss(0, 1)
                if name == "bm25-tuned":
                    score = 0.9 * score + 0.1 * rng.gauss(0, 1)
                scored.append((round(score + 5, 1), d))
            scored.sort(key=lambda x: (-x[0], x[1]))
            top = scored[:DEPTH]
            lines = [(qid, d, r, s) for r, (s, d) in enumerate(top, 1)]
            rng.shuffle(lines)                                         # file order is NOT rank order
            runs[name] += [f"{q} Q0 {d} {r} {s:.1f} {name}" for q, d, r, s in lines]
    return qrels, runs


if __name__ == "__main__":
    qrels, runs = build()
    with open(os.path.join(HERE, "qrels.txt"), "w") as f:
        f.write("# qid iteration docid grade   (0 = not relevant ... 3 = perfectly relevant; unlisted = unjudged)\n")
        f.write("\n".join(qrels) + "\n")
    for name, lines in runs.items():
        with open(os.path.join(HERE, f"run_{name}.txt"), "w") as f:
            f.write("# qid Q0 docid rank score tag   (lines are NOT in rank order: sort by score)\n")
            f.write("\n".join(lines) + "\n")
    print("wrote qrels.txt and", len(runs), "run files")
