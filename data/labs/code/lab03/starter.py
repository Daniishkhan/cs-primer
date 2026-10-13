"""Lab 3 starter: an in-memory B+ tree whose nodes are "pages".

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

Every Node stands for one page of a database file. Each time the tree looks at a
node, it calls self._read(node); that counter (pages_read) is our stand-in for
"pages fetched from disk". Rules of this tree (the same as the chapter's):

  * Leaves hold the keys and values, sorted; leaves are linked left to right.
  * Internal nodes hold separator keys and children. For an internal node with
    keys [k0, k1, ...] and children [c0, c1, c2, ...]:
        everything under c0 is  < k0
        everything under c1 is >= k0 and < k1
        ... and so on. A key equal to a separator goes to the RIGHT.
  * max_keys is the most keys a node may hold. A node that reaches max_keys + 1
    keys is split. Every non-root node therefore holds between max_keys // 2
    and max_keys keys.
"""
import bisect  # bisect_left / bisect_right do the binary search inside one page


class Node:
    """One page. A leaf has keys, values and next; an internal node has keys and children. (Given.)"""

    def __init__(self, leaf):
        self.leaf = leaf
        self.keys = []
        self.values = [] if leaf else None        # leaves only: values[i] belongs to keys[i]
        self.children = None if leaf else []      # internal only: len(children) == len(keys) + 1
        self.next = None                          # leaves only: the next leaf to the right


class BPlusTree:
    def __init__(self, max_keys=4):
        if max_keys < 2:
            raise ValueError("max_keys must be at least 2")
        self.max_keys = max_keys
        self.root = Node(leaf=True)               # an empty tree is a single empty leaf
        self.height = 1                           # number of levels; a lone leaf is height 1
        self.pages_read = 0                       # total node visits so far

    def _read(self, node):
        """Given. 'Fetch' a page: count it, and hand it back."""
        self.pages_read += 1
        return node

    # --- Milestone 1: node structure and search ------------------------------

    def find_leaf(self, key):
        """Walk from the root to the leaf that does (or would) hold `key`.

        Returns (leaf, path). path lists the internal nodes passed on the way as
        (node, child_index) pairs, root first. Insert will need it to find parents.

        Hints: start with node = self._read(self.root). While the node is not a
        leaf, bisect.bisect_right(node.keys, key) is the index of the child to
        follow (bisect_right sends a key equal to a separator to the right).
        Call self._read on EVERY node you step onto, including the root and the leaf.
        """
        raise NotImplementedError("TODO milestone 1: BPlusTree.find_leaf")

    def search(self, key):
        """Return the value stored for `key`, or None if it is absent.

        Hint: find_leaf, then bisect.bisect_left inside the leaf's keys.
        """
        raise NotImplementedError("TODO milestone 1: BPlusTree.search")

    # --- Milestones 2 and 3: insert ------------------------------------------

    def insert(self, key, value):
        """Insert key/value; if the key exists, replace its value.

        Milestone 2: find_leaf; put the key into the sorted leaf (keys and values
        stay parallel). If len(leaf.keys) > self.max_keys, split the leaf with
        _split_leaf and register the new page with _insert_in_parent.
        """
        raise NotImplementedError("TODO milestone 2: BPlusTree.insert")

    def _split_leaf(self, leaf):
        """Move the upper half of an over-full leaf into a new right sibling.

        Returns (separator, right): the separator is the first key of the new leaf
        (it is COPIED up; it also stays in the leaf).

        Hints: mid = len(leaf.keys) // 2. The new Node(leaf=True) takes keys[mid:]
        and values[mid:]. Splice it into the chain: right.next = leaf.next, then
        leaf.next = right.
        """
        raise NotImplementedError("TODO milestone 2: BPlusTree._split_leaf")

    def _insert_in_parent(self, path, left, separator, right):
        """After `left` split into (left, right): register `right` with the parent.

        `path` still holds the ancestors of `left`, root first, as (node, index)
        pairs where index is the position of the child we descended into.

        Milestone 2 (the parent has room): pop the last (parent, i) from path,
            parent.keys.insert(i, separator); parent.children.insert(i + 1, right).
        Milestone 3 (the other two cases):
            * path is empty: `left` was the root. Make a new internal root with
              keys [separator] and children [left, right]; self.height += 1.
            * the parent now has more than max_keys keys: split it too. Its middle
              key MOVES up (it is not kept in either half); the left half keeps
              keys[:mid] and children[:mid + 1], the new sibling gets keys[mid + 1:]
              and children[mid + 1:]. Then call _insert_in_parent again, one level up.
        """
        raise NotImplementedError("TODO milestone 2: BPlusTree._insert_in_parent")

    # --- Milestone 4: range scans ---------------------------------------------

    def range_scan(self, lo, hi):
        """Return [(key, value), ...] for lo <= key <= hi, in key order.

        lo=None means "from the smallest key", hi=None means "to the largest".
        Descend once to the leaf holding `lo` (or to the leftmost leaf when lo is
        None), then follow `leaf.next`; never climb back up. Call self._read on
        every leaf you move to. Stop at the first key greater than hi.
        """
        raise NotImplementedError("TODO milestone 4: BPlusTree.range_scan")


def dump(tree):
    """Given. Print the tree level by level: one line per level, one [list] per page."""
    level = [tree.root]
    while level:
        print("  ".join(str(n.keys) for n in level))
        level = [c for n in level if not n.leaf for c in n.children]


# --- Milestone 5: the invariants checker -------------------------------------

def validate(tree):
    """Return a list of strings describing every broken rule; [] means healthy.

    Check, walking the whole tree from tree.root:
      1. Keys strictly increasing inside every node.
      2. Parent separators correct: a node reached as child i of a parent must
         have all keys >= parent.keys[i-1] (if i > 0) and < parent.keys[i] (if
         i < len(parent.keys)). Pass the allowed [lo, hi) range down the recursion.
      3. Fill: leaves hold at most max_keys keys; every non-root node holds at
         least max_keys // 2 (an internal non-root: at least max(1, max_keys // 2));
         an internal root holds at least 1 key. Internal nodes have len(keys)+1 children.
      4. All leaves at the same depth, and that depth equals tree.height.
      5. Following leaf.next from the leftmost leaf visits the leaves in tree order
         and ends with None.
    """
    raise NotImplementedError("TODO milestone 5: validate")


# --- Milestone 6 (optional): measure -------------------------------------------

def measure(n, fanouts, seed=1):
    """Build a tree of n shuffled keys for each fan-out; return one dict per fan-out:

        {"max_keys": m, "height": h, "pages_per_lookup": p, "nodes": total_pages}

    pages_per_lookup is the average pages_read per search over 1000 random present
    keys (diff tree.pages_read before and after). nodes is the number of pages in
    the whole tree (count them with a stack or recursion).
    Use random.Random(seed) to shuffle, so runs are repeatable.
    """
    raise NotImplementedError("TODO milestone 6: measure")
