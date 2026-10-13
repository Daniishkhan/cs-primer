"""Self-check for Lab 3.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Pure Python, standard library only, no files and no network. Randomness is
seeded, so a failure is repeatable. Prints a check mark / cross / "..." (not
implemented yet) per milestone. Milestone 6 is optional but counted.

The checker keeps its OWN independent validator (ref_validate) for milestones
2-4, so those milestones do not depend on the validate() you write in milestone 5.
"""
import bisect
import contextlib
import importlib
import math
import os
import random
import signal
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []
notes = []


def note(text):
    notes.append(text)


class Timeout(Exception):
    pass


@contextlib.contextmanager
def time_limit(seconds):
    """Never hang: a milestone that runs for too long fails instead (POSIX; a no-op elsewhere)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def boom(signum, frame):
        raise Timeout(f"took longer than {seconds} s (an infinite loop?)")
    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def check(name, fn):
    del notes[:]
    try:
        with time_limit(40):
            fn()
        print(f"  ✔ {name}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)
    for line in notes:
        print(line)


# --- tools that do not depend on the student's code ------------------------------

def leaf(keys):
    n = mod.Node(leaf=True)
    n.keys = list(keys)
    n.values = [k * 10 for k in keys]
    return n


def internal(keys, children):
    n = mod.Node(leaf=False)
    n.keys = list(keys)
    n.children = list(children)
    return n


def link_leaves(root):
    """Set .next on hand-built leaves, left to right."""
    leaves = []

    def go(n):
        if n.leaf:
            leaves.append(n)
        else:
            for c in n.children:
                go(c)
    go(root)
    for a, b in zip(leaves, leaves[1:]):
        a.next = b
    return leaves


def tree_from(root, height, max_keys):
    t = mod.BPlusTree(max_keys=max_keys)
    t.root = root
    t.height = height
    link_leaves(root)
    return t


def ref_leaves(tree):
    node = tree.root
    while not node.leaf:
        node = node.children[0]
    out = []
    while node is not None:
        out.append(node)
        node = node.next
        assert len(out) < 10 ** 6, "the leaf chain loops"
    return out


def ref_depth(tree):
    d, node = 1, tree.root
    while not node.leaf:
        d += 1
        node = node.children[0]
    return d


def ref_validate(tree):
    """Independent invariants check. Raises AssertionError describing the first problem."""
    m = tree.max_keys
    leaf_depths = set()

    def walk(node, depth, lo, hi, is_root):
        ks = node.keys
        assert all(a < b for a, b in zip(ks, ks[1:])), f"keys not sorted: {ks}"
        assert all((lo is None or k >= lo) and (hi is None or k < hi) for k in ks), (
            f"keys {ks} outside the range [{lo}, {hi}) given by the parent separators")
        if node.leaf:
            leaf_depths.add(depth)
            assert len(ks) <= m, f"leaf over-full: {len(ks)} > {m}"
            assert is_root or len(ks) >= m // 2, f"leaf under-full: {len(ks)} < {m // 2}"
            assert len(node.values) == len(ks), "keys and values differ in length"
            return
        assert len(node.children) == len(ks) + 1, "internal node: children != keys + 1"
        assert len(ks) <= m, f"internal node over-full: {len(ks)} > {m}"
        assert len(ks) >= (1 if is_root else max(1, m // 2)), f"internal node under-full: {len(ks)}"
        for i, c in enumerate(node.children):
            walk(c, depth + 1, ks[i - 1] if i else lo, ks[i] if i < len(ks) else hi, False)
    walk(tree.root, 1, None, None, True)
    assert len(leaf_depths) == 1, f"leaves at different depths: {sorted(leaf_depths)}"
    assert leaf_depths == {tree.height}, f"tree.height is {tree.height}, leaves are at depth {leaf_depths}"
    chain = ref_leaves(tree)
    flat = [k for lf in chain for k in lf.keys]
    assert flat == sorted(flat), "the leaf chain does not visit keys in order"


def pages_for(tree, fn):
    before = tree.pages_read
    out = fn()
    return out, tree.pages_read - before


# --- Milestone 1 -----------------------------------------------------------------

def m1():
    # A hand-built 3-level tree (max_keys=3): root -> 2 internal nodes -> 4 leaves.
    a, b, c, d = leaf([1, 5, 9]), leaf([10, 12, 15]), leaf([20, 25, 30]), leaf([40, 45, 50])
    root = internal([20], [internal([10], [a, b]), internal([40], [c, d])])
    t = tree_from(root, 3, 3)
    for lf in (a, b, c, d):
        for k in lf.keys:
            got, pages = pages_for(t, lambda: t.search(k))
            assert got == k * 10, f"search({k}) returned {got!r}, expected {k * 10}"
            assert pages == 3, f"search({k}) touched {pages} pages; a 3-level tree needs exactly 3 (root, internal, leaf)"
    for k in (0, 7, 11, 22, 35, 49, 99):
        got, pages = pages_for(t, lambda: t.search(k))
        assert got is None, f"search({k}) should return None for a missing key, got {got!r}"
        assert pages == 3, f"a failed search still walks to a leaf: expected 3 pages, saw {pages}"
    lf, path = t.find_leaf(10)
    assert lf is b, "find_leaf(10) must go RIGHT at a separator equal to the key (10 belongs to the leaf [10, 12, 15])"
    assert len(path) == 2 and path[0] == (root, 0) and path[1][0] is root.children[0] and path[1][1] == 1, (
        "find_leaf must return the path as (node, child_index) pairs, root first; for key 10 that is "
        "[(root, 0), (left_internal, 1)]")
    empty = mod.BPlusTree(max_keys=4)
    got, pages = pages_for(empty, lambda: empty.search(5))
    assert got is None and pages == 1, f"an empty tree is one leaf: expected None and 1 page, got {got!r} and {pages}"
    note("    search in a 3-level tree touches exactly 3 pages: one per level")


# --- Milestone 2 -----------------------------------------------------------------

def m2():
    m = 4
    full = lambda lo: leaf([lo, lo + 10, lo + 20, lo + 30])      # a full leaf (4 keys)
    l0, l1, l2 = full(10), full(100), full(200)
    root = internal([100, 200], [l0, l1, l2])
    t = tree_from(root, 2, m)
    # one more key in a leaf that has room: nothing splits
    t2 = tree_from(internal([100], [leaf([10, 20]), leaf([100, 110])]), 2, m)
    _, pages = pages_for(t2, lambda: t2.insert(15, 150))
    assert t2.root.children[0].keys == [10, 15, 20], "insert must keep the leaf sorted"
    assert t2.root.children[0].values == [100, 150, 200], "values must stay parallel to keys"
    assert pages == 2, f"an insert that fits touches root + leaf = 2 pages, saw {pages}"
    t2.insert(15, "new")
    assert t2.root.children[0].values == [100, "new", 200], "inserting an existing key must replace its value, not add a duplicate"
    # a split with room in the parent
    _, pages = pages_for(t, lambda: t.insert(25, 250))
    assert t.height == 2, "the root had room: height must stay 2"
    assert len(root.children) == 4, "the leaf split should add one child (a new leaf) to the root"
    assert root.keys == sorted(root.keys) and len(root.keys) == 3, f"root keys should be 3 sorted separators, got {root.keys}"
    right_leaf = root.children[1]
    assert root.keys[0] == right_leaf.keys[0], (
        f"the separator must be the first key of the NEW right leaf: separator {root.keys[0]}, new leaf {right_leaf.keys}")
    assert 25 in (root.children[0].keys + right_leaf.keys), "the inserted key is missing after the split"
    assert len(root.children[0].keys) >= 2 and len(right_leaf.keys) >= 2, "split the leaf roughly in half"
    assert root.children[0].next is right_leaf and right_leaf.next is l1, "the new leaf must be spliced into the leaf chain"
    assert pages == 2, f"find the leaf (2 pages) and split in memory: expected 2 page reads, saw {pages}"
    t.insert(115, 1150)                       # root now holds 4 separators: still legal
    assert len(root.keys) == 4 and t.height == 2
    ref_validate(t)
    assert [k for lf in ref_leaves(t) for k in lf.keys] == sorted([10, 20, 30, 40, 25, 100, 110, 120, 130, 115, 200, 210, 220, 230])
    for k in (10, 25, 115, 230):
        assert t.search(k) == k * 10, f"search({k}) fails after the splits"
    note("    leaf splits keep the leaves sorted, linked and half full (the root is full now: milestone 3 is next)")


# --- Milestone 3 -----------------------------------------------------------------

def build(m, keys):
    t = mod.BPlusTree(max_keys=m)
    for k in keys:
        t.insert(k, k * 10)
    return t


def m3():
    rng = random.Random(3)
    growth = {}
    for m in (2, 3, 4, 5, 8):
        for label, keys in (("ascending", list(range(1, 301))),
                            ("descending", list(range(300, 0, -1))),
                            ("shuffled", rng.sample(range(1, 1000), 300))):
            t = mod.BPlusTree(max_keys=m)
            prev = t.height
            for n, k in enumerate(keys, 1):
                t.insert(k, k * 10)
                assert t.height in (prev, prev + 1), f"m={m}, {label}: height jumped from {prev} to {t.height}"
                if t.height == prev + 1:
                    r = t.root
                    assert not r.leaf and len(r.keys) == 1 and len(r.children) == 2, (
                        "when the tree grows, the new root has exactly one separator and two children")
                    assert t.height == ref_depth(t), "tree.height does not match the real depth"
                prev = t.height
                if n % 25 == 0:
                    try:
                        ref_validate(t)
                    except AssertionError as e:
                        raise AssertionError(f"m={m}, {label}, after {n} inserts: {e}")
            ref_validate(t)
            assert [k for lf in ref_leaves(t) for k in lf.keys] == sorted(keys)
            growth[(m, label)] = t.height
    assert growth[(2, "ascending")] >= 5 and growth[(4, "ascending")] >= 4, (
        "300 keys with tiny pages should make a tall tree; is the root really growing?")
    assert growth[(8, "ascending")] < growth[(2, "ascending")], "a larger fan-out must give a shallower tree"
    note("    heights after 300 ascending keys: " + ", ".join(f"max_keys={m} -> {growth[(m, 'ascending')]}" for m in (2, 3, 4, 5, 8)))


# --- Milestone 4 -----------------------------------------------------------------

def m4():
    rng = random.Random(4)
    keys = list(range(0, 400, 2))
    rng.shuffle(keys)
    t = build(4, keys)
    ref_validate(t)
    srt = sorted(keys)
    cases = [(10, 50), (11, 51), (0, 398), (-5, 7), (390, 1000), (100, 100), (101, 101), (50, 10), (None, 30), (370, None), (None, None), (1000, 2000)]
    for lo, hi in cases:
        want = [(k, k * 10) for k in srt if (lo is None or k >= lo) and (hi is None or k <= hi)]
        got, pages = pages_for(t, lambda: t.range_scan(lo, hi))
        assert got == want, f"range_scan({lo}, {hi}) returned {got[:6]}... ({len(got)} items), expected {want[:6]}... ({len(want)} items)"
        # How many leaves does a scan have to visit? Count from the leaf that holds lo.
        leaves = ref_leaves(t)
        start = 0
        if lo is not None:
            while start + 1 < len(leaves) and leaves[start + 1].keys and leaves[start + 1].keys[0] <= lo:
                start += 1
        end = start
        for i, lf in enumerate(leaves):
            if i >= start and any((lo is None or k >= lo) and (hi is None or k <= hi) for k in lf.keys):
                end = i
        lo_pages = t.height + (end - start)
        assert lo_pages <= pages <= lo_pages + 1, (
            f"range_scan({lo}, {hi}) touched {pages} pages; expected about {lo_pages}: descend once "
            f"({t.height} pages), then one page per extra leaf along the chain, never back up to the root")
    big = list(range(5000))
    rng.shuffle(big)
    t2 = build(8, big)
    got, pages = pages_for(t2, lambda: t2.range_scan(1000, 1999))
    assert got == [(k, k * 10) for k in range(1000, 2000)]
    searches = 0
    for k in (1000, 1001):                    # what 1000 separate lookups would cost
        _, p = pages_for(t2, lambda: t2.search(k))
        searches = p
    note(f"    1000 consecutive keys: range_scan touched {pages} pages; 1000 separate searches would touch {1000 * searches}")
    assert pages < 1000 * searches // 4, "a range scan must walk the leaf chain, not search once per key"


# --- Milestone 5 -----------------------------------------------------------------

def must_flag(name, tree):
    problems = mod.validate(tree)
    assert problems, f"validate() returned no problems for a tree with {name}; it should report it"


def m5():
    # 1. healthy trees give an empty list
    for m in (2, 3, 4, 7):
        t = build(m, random.Random(m).sample(range(2000), 400))
        problems = mod.validate(t)
        assert problems == [], f"validate() flagged a healthy tree (max_keys={m}): {problems[:3]}"
    assert mod.validate(mod.BPlusTree(4)) == [], "an empty tree is healthy"
    # 2. each rule, broken on purpose
    keys = random.Random(5).sample(range(1, 500), 60)

    t = build(4, keys)
    lf = ref_leaves(t)[0]
    lf.keys[0], lf.keys[1] = lf.keys[1], lf.keys[0]
    must_flag("two keys swapped inside a leaf (keys not sorted)", t)

    t = build(4, keys)
    lf = ref_leaves(t)[2]
    del lf.keys[1:], lf.values[1:]
    must_flag("an under-full leaf (1 key; the minimum is 2)", t)

    t = build(4, keys)
    lf = ref_leaves(t)[1]
    lo = lf.keys[0]
    lf.keys[1:1] = [lo + 0.25, lo + 0.5, lo + 0.75]
    lf.values[1:1] = [0, 0, 0]
    must_flag("an over-full leaf (more than max_keys keys)", t)

    t = build(4, keys)
    assert not t.root.leaf
    t.root.keys[0] = 10 ** 9
    must_flag("a wrong parent separator (the right child holds keys smaller than the separator)", t)

    t = build(4, keys)
    first = ref_leaves(t)[0]
    first.next = first.next.next
    must_flag("a broken leaf chain (a leaf skipped)", t)

    uneven = tree_from(internal([10], [leaf([1, 2]), internal([20], [leaf([10, 11]), leaf([20, 21])])]), 3, 4)
    must_flag("leaves at different depths", uneven)

    # 3. the stress test: thousands of keys, validated and compared with a plain dict
    rng = random.Random(55)
    plans = [
        (4, "ascending", list(range(3000))),
        (3, "descending", list(range(2000, 0, -1))),
        (5, "shuffled with repeats", [rng.randrange(4000) for _ in range(6000)]),
        (16, "shuffled", rng.sample(range(100000), 5000)),
        (2, "shuffled", rng.sample(range(5000), 1500)),
    ]
    total = 0
    for m, label, seq in plans:
        t, ref = mod.BPlusTree(max_keys=m), {}
        for n, k in enumerate(seq, 1):
            v = (k, n)
            t.insert(k, v)
            ref[k] = v
            if n % 500 == 0:
                bad = mod.validate(t)
                assert bad == [], f"max_keys={m}, {label}, after {n} inserts, validate() says: {bad[:3]}"
                try:
                    ref_validate(t)
                except AssertionError as e:
                    raise AssertionError(f"max_keys={m}, {label}, after {n} inserts the tree is broken: {e}")
        assert mod.validate(t) == []
        ref_validate(t)
        order = sorted(ref)
        assert t.range_scan(None, None) == [(k, ref[k]) for k in order], f"max_keys={m}, {label}: full scan differs from the sorted dict"
        for k in rng.sample(order, min(300, len(order))):
            assert t.search(k) == ref[k], f"max_keys={m}, {label}: search({k}) differs from the dict"
        for k in range(-3, 0):
            assert t.search(k) is None
        for _ in range(40):
            lo, hi = sorted((rng.randrange(-10, order[-1] + 10), rng.randrange(-10, order[-1] + 10)))
            i, j = bisect.bisect_left(order, lo), bisect.bisect_right(order, hi)
            assert t.range_scan(lo, hi) == [(k, ref[k]) for k in order[i:j]], f"max_keys={m}, {label}: range_scan({lo}, {hi}) differs"
        total += len(seq)
    note(f"    {total} seeded inserts in 5 trees: invariants hold and every answer matches a sorted dict")


# --- Milestone 6 (optional) -------------------------------------------------------

def m6():
    n, fanouts = 100_000, (4, 16, 64, 256)
    rows = mod.measure(n, fanouts, seed=1)
    assert [r["max_keys"] for r in rows] == list(fanouts), "return one dict per fan-out, in the order given"
    note(f"    {n:,} keys:  max_keys  height  pages/lookup  pages in tree   ceil(log_(m+1)(n))")
    last = None
    for r in rows:
        m = r["max_keys"]
        # The tallest and shortest a legal tree of this shape can be.
        lo_h = 1
        while m * (m + 1) ** (lo_h - 1) < n:
            lo_h += 1
        hi_h = 2
        while 2 * (m // 2) * (m // 2 + 1) ** (hi_h - 2) < n:
            hi_h += 1
        note(f"                          {m:>6}  {r['height']:>6}  {r['pages_per_lookup']:>12.2f}  {r['nodes']:>13}   {math.ceil(math.log(n, m + 1)):>10}")
        assert lo_h <= r["height"] <= hi_h, f"max_keys={m}: height {r['height']} is impossible for {n} keys (must be {lo_h}..{hi_h})"
        assert abs(r["pages_per_lookup"] - r["height"]) < 1e-9, f"max_keys={m}: every lookup walks root to leaf, so pages/lookup must equal the height"
        assert r["nodes"] >= n / m, f"max_keys={m}: too few pages for {n} keys"
        assert last is None or r["height"] <= last, "a larger fan-out must never give a taller tree"
        assert last is None or r["nodes"] < prev_nodes, "a larger fan-out must need fewer pages"
        last, prev_nodes = r["height"], r["nodes"]
    assert rows[0]["height"] > rows[-1]["height"], "fan-out 4 should be much taller than fan-out 256"


print(f"Lab 3 checks against {target}.py\n")
check("Milestone 1: node structure and search (count the pages)", m1)
check("Milestone 2: insert with leaf splits", m2)
check("Milestone 3: internal splits and root growth", m3)
check("Milestone 4: range scans along the linked leaves", m4)
check("Milestone 5: the invariants checker, and a stress test against a dict", m5)
check("Milestone 6 (optional): measure height and pages per lookup", m6)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
