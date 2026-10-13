"""Lab 6: CRDTs That Converge  --  reference solution.

Every type here is a STATE-BASED CRDT (a "CvRDT"): a replica holds a state, local operations
change it, and replicas exchange whole states and combine them with merge().

The contract every class obeys (the check tests all of it):

    merge(other) is PURE      it returns a NEW replica and changes neither input
    merge is commutative      a.merge(b) == b.merge(a)
    merge is associative      (a.merge(b)).merge(c) == a.merge(b.merge(c))
    merge is idempotent       a.merge(a) == a
    merge only moves up       a.merge(b) is "at least" a and "at least" b

"==" means: state() is equal.  state() is a canonical, comparable snapshot of the internals;
value() is what a user of the type would see.  A set of states with such a merge is a join
semilattice, and the merge is the join (least upper bound).

The file has two halves:  GIVEN (helpers, base class, state()) and YOURS (the operations and merge).
"""
import copy

# =============================================================================================
# GIVEN
# =============================================================================================


def vv_leq(a, b):
    """Version vector a <= b ?  (dicts rid -> count; a missing entry is 0)."""
    return all(b.get(k, 0) >= v for k, v in a.items())


def vv_join(a, b):
    """Entry-wise maximum of two version vectors."""
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in set(a) | set(b)}


def _key(x):
    return repr(x)


class CRDT:
    """Base class.  A replica has an id (`rid`, a string) that is unique in the cluster."""

    def __init__(self, rid):
        self.rid = rid

    def copy(self):
        return copy.deepcopy(self)

    def state(self):
        """A canonical, comparable snapshot of the internal state (same state => equal)."""
        raise NotImplementedError

    def value(self):
        """What a user of the type sees."""
        raise NotImplementedError

    def merge(self, other):
        """Return a NEW replica (with self's rid) holding the join of self and other."""
        raise NotImplementedError


# =============================================================================================
# YOURS
# =============================================================================================

# ---- milestone 1: counters -------------------------------------------------------------------

class GCounter(CRDT):
    """Grow-only counter.  counts[rid] = how many increments replica `rid` has done."""

    def __init__(self, rid):
        super().__init__(rid)
        self.counts = {}

    def state(self):
        return tuple(sorted((k, v) for k, v in self.counts.items() if v))

    def increment(self, n=1):
        if n < 0:
            raise ValueError("a G-Counter only grows")
        self.counts[self.rid] = self.counts.get(self.rid, 0) + n

    def value(self):
        return sum(self.counts.values())

    def merge(self, other):
        out = GCounter(self.rid)
        for k in set(self.counts) | set(other.counts):
            out.counts[k] = max(self.counts.get(k, 0), other.counts.get(k, 0))
        return out


class PNCounter(CRDT):
    """Counter that can go down: two G-Counters, one for increments and one for decrements."""

    def __init__(self, rid):
        super().__init__(rid)
        self.p = GCounter(rid)
        self.n = GCounter(rid)

    def state(self):
        return (self.p.state(), self.n.state())

    def increment(self, n=1):
        self.p.increment(n)

    def decrement(self, n=1):
        self.n.increment(n)

    def value(self):
        return self.p.value() - self.n.value()

    def merge(self, other):
        out = PNCounter(self.rid)
        out.p = self.p.merge(other.p)
        out.n = self.n.merge(other.n)
        return out


# ---- milestone 2: registers --------------------------------------------------------------------

class LWWRegister(CRDT):
    """Last-writer-wins.  entry = (ts, rid, value) or None.  Order by (ts, rid): the replica id
    breaks ties, so every replica picks the same winner."""

    def __init__(self, rid):
        super().__init__(rid)
        self.entry = None

    def state(self):
        return self.entry

    def set(self, value, ts):
        """Write `value` at timestamp `ts`.  A replica's own writes must never go backwards, so
        if ts is not newer than what it holds, use one more than that.  Returns the stamp (ts, rid)."""
        if self.entry is not None and ts <= self.entry[0]:
            ts = self.entry[0] + 1
        self.entry = (ts, self.rid, value)
        return (ts, self.rid)

    def value(self):
        return None if self.entry is None else self.entry[2]

    def merge(self, other):
        out = LWWRegister(self.rid)
        cands = [e for e in (self.entry, other.entry) if e is not None]
        out.entry = max(cands, key=lambda e: (e[0], e[1])) if cands else None
        return out


class MVRegister(CRDT):
    """Multi-value register.  entries = list of (value, version-vector) pairs that are mutually
    concurrent.  A write replaces everything the writer has seen; a merge keeps every entry that
    no other entry dominates."""

    def __init__(self, rid):
        super().__init__(rid)
        self.entries = []              # [(value, ((rid, count), ...)), ...]

    def state(self):
        return tuple(sorted(self.entries, key=_key))

    def set(self, value):
        """Write value; returns the new version vector (a dict)."""
        vv = {}
        for _, e in self.entries:
            vv = vv_join(vv, dict(e))
        vv[self.rid] = vv.get(self.rid, 0) + 1
        self.entries = [(value, tuple(sorted(vv.items())))]
        return dict(vv)

    def value(self):
        return sorted({v for v, _ in self.entries}, key=_key)

    def merge(self, other):
        out = MVRegister(self.rid)
        allv = {(v, e) for v, e in self.entries} | {(v, e) for v, e in other.entries}
        keep = []
        for v, e in allv:
            dominated = any(e != e2 and vv_leq(dict(e), dict(e2)) for _, e2 in allv)
            if not dominated:
                keep.append((v, e))
        out.entries = sorted(keep, key=_key)
        return out


# ---- milestone 3: the observed-remove set -------------------------------------------------------

class ORSet(CRDT):
    """Add-wins set.  Every add creates a unique tag (rid, n).  A remove records the tags it has
    SEEN as removed.  An element is present iff it has at least one tag that is not removed."""

    def __init__(self, rid):
        super().__init__(rid)
        self.adds = set()              # {(element, (rid, n))}
        self.removed = set()           # {(rid, n)}   tombstones

    def state(self):
        return (tuple(sorted(self.adds, key=_key)), tuple(sorted(self.removed)))

    def add(self, e):
        """Add e with a fresh unique tag; returns the tag."""
        n = 1 + max([t[1] for _, t in self.adds if t[0] == self.rid], default=0)
        tag = (self.rid, n)
        self.adds.add((e, tag))
        return tag

    def remove(self, e):
        """Remove e: tombstone every tag of e this replica can see.  Returns the set of tags."""
        tags = {t for el, t in self.adds if el == e and t not in self.removed}
        self.removed |= tags
        return tags

    def value(self):
        return {el for el, t in self.adds if t not in self.removed}

    def entries(self):
        """The live (element, tag) pairs.  One pair per 'add' that nobody removed."""
        return {(el, t) for el, t in self.adds if t not in self.removed}

    def contains(self, e):
        return e in self.value()

    def merge(self, other):
        out = ORSet(self.rid)
        out.adds = self.adds | other.adds
        out.removed = self.removed | other.removed
        return out


# ---- milestone 5: an application, and the type it should not be built from -----------------------

class TwoPSet(CRDT):
    """2P-Set: a grow-only set of adds and a grow-only set of removes.  Present = added and not
    removed.  Once an element is removed it can NEVER be present again."""

    def __init__(self, rid):
        super().__init__(rid)
        self.added = set()
        self.removed = set()

    def state(self):
        return (tuple(sorted(self.added, key=_key)), tuple(sorted(self.removed, key=_key)))

    def add(self, e):
        self.added.add(e)

    def remove(self, e):
        """Only an element this replica has seen can be removed.  Returns True if it recorded one."""
        if e in self.added:
            self.removed.add(e)
            return True
        return False

    def value(self):
        return self.added - self.removed

    def merge(self, other):
        out = TwoPSet(self.rid)
        out.added = self.added | other.added
        out.removed = self.removed | other.removed
        return out


class Cart(CRDT):
    """A shopping cart for several devices: lines (an OR-Set of (sku, qty) entries, one per
    'add to cart' tap), a delivery address (LWW) and a gift note (MV: concurrent notes are shown)."""

    def __init__(self, rid):
        super().__init__(rid)
        self.lines = ORSet(rid)
        self.address = LWWRegister(rid)
        self.note = MVRegister(rid)

    def state(self):
        return (self.lines.state(), self.address.state(), self.note.state())

    def add_item(self, sku, qty=1):
        """One tap on 'add to cart'.  Returns the unique tag."""
        return self.lines.add((sku, qty))

    def remove_item(self, sku):
        """Remove every line for sku that THIS device can see.  Returns the set of removed tags."""
        tags = set()
        for el in sorted(self.lines.value(), key=_key):
            if el[0] == sku:
                tags |= self.lines.remove(el)
        return tags

    def set_address(self, text, ts):
        return self.address.set(text, ts)

    def set_note(self, text):
        return self.note.set(text)

    def items(self):
        """{sku: total quantity}"""
        out = {}
        for (sku, qty), _tag in self.lines.entries():     # one entry per tap, so two taps add up
            out[sku] = out.get(sku, 0) + qty
        return out

    def value(self):
        return {"items": self.items(), "address": self.address.value(), "note": self.note.value()}

    def merge(self, other):
        out = Cart(self.rid)
        out.lines = self.lines.merge(other.lines)
        out.address = self.address.merge(other.address)
        out.note = self.note.merge(other.note)
        return out
