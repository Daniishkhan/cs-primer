"""Lab 5 solution: a multi-version key-value store with snapshot isolation.

Concurrency here is *interleaving*: several Transaction objects exist at once and
the caller decides, call by call, whose turn it is. No threads, so every run is
the same. That is enough to reproduce every anomaly in chapters 11 and 12.

Data model:

    store.versions["alice"] = [Version(value, created_by, deleted_by), ...]   oldest first

    created_by  the txid that wrote this version
    deleted_by  a LIST of txids that replaced or deleted it. Postgres has a single
                xmax because a second writer waits on a row lock. We detect the
                conflict at commit time instead (first committer wins), so two
                still-running transactions may both "claim" the same old version.
                At most one of them can ever commit.
"""


class SerializationError(Exception):
    """Raised by commit() when the transaction cannot be allowed to commit. It has been aborted."""


class Version:
    """One version of one key."""

    def __init__(self, value, created_by):
        self.value = value
        self.created_by = created_by
        self.deleted_by = []                    # txids that replaced or deleted this version

    def __repr__(self):
        return "Version(%r, created_by=%r, deleted_by=%r)" % (self.value, self.created_by, self.deleted_by)


class Snapshot:
    """What a transaction can see of the past: frozen when begin() is called."""

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
        txid = self.next_txid
        self.next_txid += 1
        active = [t for t, s in self.status.items() if s == "active"]     # BEFORE adding myself
        self.status[txid] = "active"
        tx = Transaction(self, txid, Snapshot(txid, active))
        self.live[txid] = tx
        return tx

    # ---- Milestone 2 -------------------------------------------------------------
    def committed_before(self, snap, txid):
        """Was `txid` committed before the snapshot `snap` was taken?"""
        return (self.status.get(txid) == "committed"
                and txid < snap.txid
                and txid not in snap.active)

    def visible(self, v, tx):
        """Can transaction `tx` see version `v`?"""
        c = v.created_by
        if c != tx.txid and not self.committed_before(tx.snapshot, c):
            return False                        # created by the future, a running tx, or an aborted tx
        for d in v.deleted_by:
            if d == tx.txid or self.committed_before(tx.snapshot, d):
                return False                    # I deleted it, or a visible commit did
        return True

    def visible_version(self, tx, key):
        for v in reversed(self.versions.get(key, [])):
            if self.visible(v, tx):
                return v
        return None

    # ---- Milestone 6 -------------------------------------------------------------
    def vacuum(self):
        """Remove versions nobody can ever see again. Returns how many were removed."""
        removed = 0
        for key in list(self.versions):
            keep = []
            for v in self.versions[key]:
                v.deleted_by = [d for d in v.deleted_by if self.status[d] != "aborted"]
                if self._dead(v):
                    removed += 1
                else:
                    keep.append(v)
            if keep:
                self.versions[key] = keep
            else:
                del self.versions[key]
        return removed

    def _dead(self, v):
        if self.status[v.created_by] == "aborted":
            return True                         # never visible to anyone
        if self.status[v.created_by] != "committed":
            return False                        # its creator is still running
        if not any(self.status[d] == "committed" for d in v.deleted_by):
            return False                        # still the current version for new snapshots
        # Deleted by a committed transaction, so every FUTURE snapshot skips it.
        # It is garbage only if no snapshot that already exists can still see it.
        return not any(self.visible(v, tx) for tx in self.live.values())

    # ---- debugging aid -----------------------------------------------------------
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
        if self.store.status[self.txid] != "active":
            raise RuntimeError("transaction %d is %s" % (self.txid, self.store.status[self.txid]))

    # ---- Milestones 1 and 2 ------------------------------------------------------
    def read(self, key):
        self._require_active()
        self.read_set.add(key)
        v = self.store.visible_version(self, key)
        return v.value if v is not None else None

    def write(self, key, value):
        self._put(key, value, tombstone=False)

    def delete(self, key):
        self._put(key, None, tombstone=True)

    def _put(self, key, value, tombstone):
        self._require_active()
        self.write_set.add(key)
        chain = self.store.versions.setdefault(key, [])
        for v in reversed(chain):               # writing a key I already wrote: reuse my version
            if v.created_by == self.txid and self.txid not in v.deleted_by:
                if tombstone:
                    v.deleted_by.append(self.txid)
                else:
                    v.value = value
                return
        old = self.store.visible_version(self, key)         # the version I am replacing
        if old is not None:
            old.deleted_by.append(self.txid)
        if not tombstone:
            chain.append(Version(value, self.txid))

    # ---- Milestones 1, 3, 4, 5 ---------------------------------------------------
    def commit(self):
        self._require_active()
        try:
            self._check_write_conflicts()       # Milestone 4
            if self.store.ssi:
                self._check_read_conflicts()    # Milestone 5
        except SerializationError:
            self.abort()
            raise
        self.store.status[self.txid] = "committed"
        del self.store.live[self.txid]

    def abort(self):
        self._require_active()
        self.store.status[self.txid] = "aborted"    # that is all: its versions are now invisible
        del self.store.live[self.txid]

    def _concurrent_committers(self, key):
        """Txids that committed a change to `key` AFTER my snapshot was taken."""
        found = set()
        for v in self.store.versions.get(key, []):
            for t in [v.created_by] + v.deleted_by:
                if (t != self.txid and self.store.status[t] == "committed"
                        and not self.store.committed_before(self.snapshot, t)):
                    found.add(t)
        return found

    def _check_write_conflicts(self):
        for key in sorted(self.write_set):
            other = self._concurrent_committers(key)
            if other:
                raise SerializationError("write-write conflict on %r: tx %d committed first"
                                         % (key, min(other)))

    def _check_read_conflicts(self):
        for key in sorted(self.read_set):
            other = self._concurrent_committers(key)
            if other:
                raise SerializationError("read-write conflict on %r: tx %d changed it after my snapshot"
                                         % (key, min(other)))


# ---- Milestone 4 -------------------------------------------------------------------
def run_transaction(store, fn, retries=5):
    """Run fn(tx) in a fresh transaction and commit. Retry on SerializationError."""
    for attempt in range(retries):
        tx = store.begin()
        try:
            result = fn(tx)
            tx.commit()
            return result
        except SerializationError:
            continue                            # commit() already aborted tx; try again with a new snapshot
        except BaseException:
            if store.status[tx.txid] == "active":
                tx.abort()
            raise
    raise SerializationError("gave up after %d attempts" % retries)


# ---- Milestone 5 -------------------------------------------------------------------
DOCTORS = ("alice", "bob")


def go_off_call(tx, who):
    """The hospital rule: a doctor may go off call only if at least two are on call.
    Returns True if `who` went off call, False if the request was refused."""
    on_call = [d for d in DOCTORS if tx.read(d)]
    if len(on_call) < 2:
        return False
    tx.write(who, False)
    return True
