"""Lab 5 starter: snapshot isolation from scratch.

An in-memory multi-version key-value store. Concurrency here means several
Transaction objects alive at the same time, with the caller deciding whose turn
it is. No threads, so every run is identical.

Fill in every TODO, one milestone at a time, and run `python3 check.py` after
each one. The lab page walks you through it.

Data model:

    store.versions["alice"] = [Version(value, created_by, deleted_by), ...]   oldest first

    created_by  the txid that wrote this version
    deleted_by  a LIST of txids that replaced or deleted it. (Postgres has a single
                xmax because a second writer waits on a row lock. We detect the
                conflict at commit time instead, so two running transactions may
                both "claim" the same old version. At most one of them can commit.)
"""


class SerializationError(Exception):
    """Raised by commit() when the transaction cannot be allowed to commit. It has been aborted."""


class Version:
    """One version of one key. (Given.)"""

    def __init__(self, value, created_by):
        self.value = value
        self.created_by = created_by
        self.deleted_by = []                    # txids that replaced or deleted this version

    def __repr__(self):
        return "Version(%r, created_by=%r, deleted_by=%r)" % (self.value, self.created_by, self.deleted_by)


class Snapshot:
    """What a transaction can see of the past, frozen at begin(). (Given.)"""

    def __init__(self, txid, active):
        self.txid = txid                        # my own id; everything with a higher id is the future
        self.active = frozenset(active)         # transactions that were still running at that moment


class Store:
    def __init__(self, ssi=False):
        self.ssi = ssi                          # Milestone 5: SSI-lite mode
        self.next_txid = 1                      # the global txid counter
        self.versions = {}                      # key -> [Version, ...], oldest first
        self.status = {}                        # txid -> "active" | "committed" | "aborted"
        self.live = {}                          # txid -> Transaction, for the active ones

    # ---- Milestone 1 -------------------------------------------------------------
    def begin(self):
        """Start a transaction. Steps:
        1. take txid = self.next_txid and advance the counter;
        2. collect the txids whose status is "active" RIGHT NOW (before adding yourself);
        3. set status[txid] = "active", build Transaction(self, txid, Snapshot(txid, active)),
           remember it in self.live, and return it."""
        raise NotImplementedError("TODO milestone 1: Store.begin")

    # ---- Milestone 2 -------------------------------------------------------------
    def committed_before(self, snap, txid):
        """True if `txid` had already committed when snapshot `snap` was taken.
        Three conditions: its status is "committed"; it started before the snapshot's
        owner (txid < snap.txid); and it was not running when the snapshot was taken
        (txid not in snap.active)."""
        raise NotImplementedError("TODO milestone 2: Store.committed_before")

    def visible(self, v, tx):
        """Can transaction `tx` see version `v`?
        Yes if (a) it created v itself, or its creator committed before tx's snapshot, AND
        (b) none of v.deleted_by is tx itself or a transaction that committed before the snapshot."""
        raise NotImplementedError("TODO milestone 2: Store.visible")

    def visible_version(self, tx, key):
        """The one version of `key` that `tx` can see, or None. Newest first is a good search order."""
        raise NotImplementedError("TODO milestone 2: Store.visible_version")

    # ---- Milestone 6 (optional) --------------------------------------------------
    def vacuum(self):
        """Remove versions that no running transaction can see and no future one will.
        Return how many versions were removed. A version is garbage when:
          - its creator aborted, or
          - its creator committed AND a committed transaction deleted it AND no transaction
            in self.live can still see it (use self.visible).
        Drop keys whose version list becomes empty."""
        raise NotImplementedError("TODO milestone 6: Store.vacuum")

    # ---- debugging aid (given) ---------------------------------------------------
    def show(self, key):
        return [(v.value, v.created_by, list(v.deleted_by)) for v in self.versions.get(key, [])]


class Transaction:
    def __init__(self, store, txid, snapshot):
        self.store = store
        self.txid = txid
        self.snapshot = snapshot
        self.read_set = set()                   # keys I have read (Milestone 5)
        self.write_set = set()                  # keys I have written or deleted (Milestone 4)

    def _require_active(self):
        """(Given.) Using a finished transaction is a programming error."""
        if self.store.status[self.txid] != "active":
            raise RuntimeError("transaction %d is %s" % (self.txid, self.store.status[self.txid]))

    # ---- Milestones 1 and 2 ------------------------------------------------------
    def read(self, key):
        """Return the value of `key` this transaction can see, or None.
        Call self._require_active() first and record the key in self.read_set."""
        raise NotImplementedError("TODO milestone 2: Transaction.read")

    def write(self, key, value):
        self._put(key, value, tombstone=False)

    def delete(self, key):
        self._put(key, None, tombstone=True)

    def _put(self, key, value, tombstone):
        """Create a new version of `key` (or, for tombstone=True, just delete it).
        1. _require_active(); add key to self.write_set.
        2. If this transaction already wrote the key (a version it created and has not
           deleted), update that version's value in place (or, for a delete, mark it
           deleted_by me) and stop.
        3. Otherwise find the version you are replacing and append your txid to its
           deleted_by, then append Version(value, my txid) to store.versions[key]
           (unless this is a delete).

        Milestone 1: for "the version you are replacing", the newest version with an empty
        deleted_by is good enough. Milestone 2: use self.store.visible_version(self, key)
        instead, because the newest version might belong to a transaction you cannot see."""
        raise NotImplementedError("TODO milestone 1: Transaction._put")

    # ---- Milestones 1, 3, 4, 5 ---------------------------------------------------
    def commit(self):
        """Milestone 1: _require_active(), then set status to "committed" and remove yourself
        from store.live.
        Milestone 4: BEFORE that, check for write-write conflicts (see _check_write_conflicts);
        on SerializationError call self.abort() and re-raise.
        Milestone 5: if self.store.ssi, also run _check_read_conflicts() the same way."""
        raise NotImplementedError("TODO milestone 1: Transaction.commit")

    def abort(self):
        """_require_active(); mark the transaction "aborted"; remove it from store.live.
        Do not touch the versions. Their creator's status is enough to hide them."""
        raise NotImplementedError("TODO milestone 3: Transaction.abort")

    def _concurrent_committers(self, key):
        """Txids that committed a change to `key` AFTER my snapshot was taken: for every
        version of the key, look at its creator and its deleters; keep those t != me with
        status "committed" and not store.committed_before(self.snapshot, t)."""
        raise NotImplementedError("TODO milestone 4: Transaction._concurrent_committers")

    def _check_write_conflicts(self):
        """Milestone 4: for each key in self.write_set, if _concurrent_committers(key) is
        non-empty, raise SerializationError (first committer wins)."""
        raise NotImplementedError("TODO milestone 4: Transaction._check_write_conflicts")

    def _check_read_conflicts(self):
        """Milestone 5 (SSI-lite): the same test, but for each key in self.read_set."""
        raise NotImplementedError("TODO milestone 5: Transaction._check_read_conflicts")


# ---- Milestone 4 -------------------------------------------------------------------
def run_transaction(store, fn, retries=5):
    """Run fn(tx) in a fresh transaction and commit it. If commit raises SerializationError,
    start over with a NEW transaction (a new snapshot), up to `retries` attempts in total,
    then raise SerializationError. If fn raises anything else, abort the transaction if it
    is still active and re-raise. Return fn's result."""
    raise NotImplementedError("TODO milestone 4: run_transaction")


# ---- Milestone 5 -------------------------------------------------------------------
DOCTORS = ("alice", "bob")      # key -> True while that doctor is on call


def go_off_call(tx, who):
    """The hospital rule: a doctor may go off call only if at least two doctors are on call.
    Read both DOCTORS inside `tx`; if fewer than two are on call return False; otherwise
    write False to key `who` and return True."""
    raise NotImplementedError("TODO milestone 5: go_off_call")
