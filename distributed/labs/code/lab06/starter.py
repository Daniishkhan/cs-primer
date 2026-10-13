"""Lab 6: CRDTs That Converge  --  starter.

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

The file has two halves:  GIVEN (helpers, base class, the fields and state() of each type) and YOURS
(the operations, value() and merge() of each type).
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
# YOURS.  The fields and state() of every class are given so that the check can compare replicas.
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
        """Add n (>= 0) to THIS replica's own slot.  A negative n raises ValueError."""
        raise NotImplementedError("TODO milestone 1: GCounter.increment")

    def value(self):
        raise NotImplementedError("TODO milestone 1: GCounter.value")

    def merge(self, other):
        """Return a NEW GCounter (rid = self.rid) with, for every replica id, the MAXIMUM of the two counts."""
        raise NotImplementedError("TODO milestone 1: GCounter.merge")


class PNCounter(CRDT):
    """Counter that can go down: two G-Counters, one for increments and one for decrements."""

    def __init__(self, rid):
        super().__init__(rid)
        self.p = GCounter(rid)
        self.n = GCounter(rid)

    def state(self):
        return (self.p.state(), self.n.state())

    def increment(self, n=1):
        raise NotImplementedError("TODO milestone 1: PNCounter.increment")

    def decrement(self, n=1):
        raise NotImplementedError("TODO milestone 1: PNCounter.decrement")

    def value(self):
        raise NotImplementedError("TODO milestone 1: PNCounter.value")

    def merge(self, other):
        raise NotImplementedError("TODO milestone 1: PNCounter.merge")


# ---- milestone 2: registers --------------------------------------------------------------------

class LWWRegister(CRDT):
    """Last-writer-wins.  entry = (ts, rid, value) or None.  Order entries by (ts, rid): the
    replica id breaks ties, so every replica picks the same winner."""

    def __init__(self, rid):
        super().__init__(rid)
        self.entry = None

    def state(self):
        return self.entry

    def set(self, value, ts):
        """Write `value` at timestamp `ts`.  A replica's own writes must never go backwards: if ts
        is not newer than the timestamp already held, use that timestamp + 1.  Return the stamp (ts, rid) used."""
        raise NotImplementedError("TODO milestone 2: LWWRegister.set")

    def value(self):
        raise NotImplementedError("TODO milestone 2: LWWRegister.value")

    def merge(self, other):
        """Keep the entry with the larger (ts, rid).  Either entry may be None.  Never compare values."""
        raise NotImplementedError("TODO milestone 2: LWWRegister.merge")


class MVRegister(CRDT):
    """Multi-value register.  entries = list of (value, version-vector) pairs that are mutually
    concurrent.  A version vector is stored as a tuple of sorted (rid, count) pairs; use
    dict(vv) to get a dict for vv_leq / vv_join."""

    def __init__(self, rid):
        super().__init__(rid)
        self.entries = []

    def state(self):
        return tuple(sorted(self.entries, key=_key))

    def set(self, value):
        """Replace ALL current entries by one: (value, vv) where vv = the join of every vv you
        hold, with your own counter increased by one.  Return vv as a dict."""
        raise NotImplementedError("TODO milestone 2: MVRegister.set")

    def value(self):
        """The distinct values, sorted by repr (a list)."""
        raise NotImplementedError("TODO milestone 2: MVRegister.value")

    def merge(self, other):
        """Union of the entries, then drop every entry whose vv is strictly below another entry's vv."""
        raise NotImplementedError("TODO milestone 2: MVRegister.merge")


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
        """Add e under a fresh tag (self.rid, n), n one more than any n you have used.  Return the tag."""
        raise NotImplementedError("TODO milestone 3: ORSet.add")

    def remove(self, e):
        """Tombstone every not-yet-removed tag of e that THIS replica holds.  Return that set of tags."""
        raise NotImplementedError("TODO milestone 3: ORSet.remove")

    def value(self):
        """The set of elements with at least one live tag."""
        raise NotImplementedError("TODO milestone 3: ORSet.value")

    def entries(self):
        """The live (element, tag) pairs: one per 'add' that nobody removed."""
        raise NotImplementedError("TODO milestone 3: ORSet.entries")

    def contains(self, e):
        return e in self.value()

    def merge(self, other):
        raise NotImplementedError("TODO milestone 3: ORSet.merge")


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
        raise NotImplementedError("TODO milestone 5: TwoPSet.add")

    def remove(self, e):
        """Only an element this replica has seen can be removed.  Return True if a removal was recorded."""
        raise NotImplementedError("TODO milestone 5: TwoPSet.remove")

    def value(self):
        raise NotImplementedError("TODO milestone 5: TwoPSet.value")

    def merge(self, other):
        raise NotImplementedError("TODO milestone 5: TwoPSet.merge")


class Cart(CRDT):
    """A shopping cart for several devices, built only from the types above.

      lines    an ORSet of (sku, qty) entries, one per tap on 'add to cart'
      address  an LWWRegister (the delivery address)
      note     an MVRegister (a gift note; concurrent notes are all shown)
    """

    def __init__(self, rid):
        super().__init__(rid)
        self.lines = ORSet(rid)
        self.address = LWWRegister(rid)
        self.note = MVRegister(rid)

    def state(self):
        return (self.lines.state(), self.address.state(), self.note.state())

    def add_item(self, sku, qty=1):
        """One tap on 'add to cart'.  Return the unique tag."""
        raise NotImplementedError("TODO milestone 5: Cart.add_item")

    def remove_item(self, sku):
        """Remove every line for sku that THIS device can see.  Return the set of removed tags."""
        raise NotImplementedError("TODO milestone 5: Cart.remove_item")

    def set_address(self, text, ts):
        raise NotImplementedError("TODO milestone 5: Cart.set_address")

    def set_note(self, text):
        raise NotImplementedError("TODO milestone 5: Cart.set_note")

    def items(self):
        """{sku: total quantity}, summing the live lines.  Two taps of the same item add up."""
        raise NotImplementedError("TODO milestone 5: Cart.items")

    def value(self):
        return {"items": self.items(), "address": self.address.value(), "note": self.note.value()}

    def merge(self, other):
        raise NotImplementedError("TODO milestone 5: Cart.merge")
