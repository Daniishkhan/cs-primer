"""Lab 3 solution: an in-memory B+ tree whose nodes are "pages".

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
import bisect


class Node:
    """One page. A leaf has keys, values and next; an internal node has keys and children."""

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
        """
        node = self._read(self.root)
        path = []
        while not node.leaf:
            i = bisect.bisect_right(node.keys, key)   # equal keys go right
            path.append((node, i))
            node = self._read(node.children[i])
        return node, path

    def search(self, key):
        """Return the value stored for `key`, or None if it is absent."""
        leaf, _ = self.find_leaf(key)
        i = bisect.bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            return leaf.values[i]
        return None

    # --- Milestones 2 and 3: insert ------------------------------------------

    def insert(self, key, value):
        """Insert key/value; if the key exists, replace its value."""
        leaf, path = self.find_leaf(key)
        i = bisect.bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            leaf.values[i] = value
            return
        leaf.keys.insert(i, key)
        leaf.values.insert(i, value)
        if len(leaf.keys) > self.max_keys:
            separator, right = self._split_leaf(leaf)
            self._insert_in_parent(path, leaf, separator, right)

    def _split_leaf(self, leaf):
        """Move the upper half of an over-full leaf into a new right sibling.

        Returns (separator, right): the separator is the first key of the new leaf
        (it is COPIED up; it also stays in the leaf).
        """
        mid = len(leaf.keys) // 2
        right = Node(leaf=True)
        right.keys = leaf.keys[mid:]
        right.values = leaf.values[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]
        right.next = leaf.next                    # splice the new page into the chain
        leaf.next = right
        return right.keys[0], right

    def _insert_in_parent(self, path, left, separator, right):
        """After `left` split into (left, right): register `right` with the parent.

        `path` still holds the ancestors of `left`, root first.
        """
        if not path:                              # `left` was the root: the tree grows
            root = Node(leaf=False)
            root.keys = [separator]
            root.children = [left, right]
            self.root = root
            self.height += 1
            return
        parent, i = path.pop()                    # i = position of `left` among parent's children
        parent.keys.insert(i, separator)
        parent.children.insert(i + 1, right)
        if len(parent.keys) > self.max_keys:      # Milestone 3: the parent is over-full too
            mid = (len(parent.keys)) // 2
            up = parent.keys[mid]                 # this key MOVES up; it is not kept below
            sibling = Node(leaf=False)
            sibling.keys = parent.keys[mid + 1:]
            sibling.children = parent.children[mid + 1:]
            parent.keys = parent.keys[:mid]
            parent.children = parent.children[:mid + 1]
            self._insert_in_parent(path, parent, up, sibling)

    # --- Milestone 4: range scans ---------------------------------------------

    def range_scan(self, lo, hi):
        """Return [(key, value), ...] for lo <= key <= hi, in key order.

        lo=None means "from the smallest key", hi=None means "to the largest".
        Descend once, then follow the leaf links; never climb back up.
        """
        if lo is None:
            node = self._read(self.root)
            while not node.leaf:
                node = self._read(node.children[0])
            leaf = node
        else:
            leaf, _ = self.find_leaf(lo)
        out = []
        while leaf is not None:
            for k, v in zip(leaf.keys, leaf.values):
                if lo is not None and k < lo:
                    continue
                if hi is not None and k > hi:
                    return out
                out.append((k, v))
            leaf = leaf.next
            if leaf is not None:
                self._read(leaf)
        return out


def dump(tree):
    """Given. Print the tree level by level: one line per level, one [list] per page."""
    level = [tree.root]
    while level:
        print("  ".join(str(n.keys) for n in level))
        level = [c for n in level if not n.leaf for c in n.children]


# --- Milestone 5: the invariants checker -------------------------------------

def validate(tree):
    """Return a list of strings describing every broken rule; [] means healthy."""
    problems = []
    m = tree.max_keys
    leaves = []                                    # leaves in left-to-right order
    depths = set()

    def walk(node, depth, lo, hi, is_root):
        n = len(node.keys)
        for a, b in zip(node.keys, node.keys[1:]):
            if a >= b:
                problems.append(f"keys not strictly increasing: {a} before {b}")
                break
        for k in node.keys:                        # parent separators: node covers [lo, hi)
            if (lo is not None and k < lo) or (hi is not None and k >= hi):
                problems.append(f"key {k} lies outside the range [{lo}, {hi}) its parent allows")
        if node.leaf:
            depths.add(depth)
            leaves.append(node)
            if len(node.values) != n:
                problems.append("a leaf has a different number of keys and values")
            if n > m or (not is_root and n < m // 2):
                problems.append(f"leaf holds {n} keys; allowed {0 if is_root else m // 2}..{m}")
            return
        if len(node.children) != n + 1:
            problems.append(f"internal node has {n} keys but {len(node.children)} children")
            return
        if n > m or n < (1 if is_root else max(1, m // 2)):
            problems.append(f"internal node holds {n} keys; allowed {1 if is_root else max(1, m // 2)}..{m}")
        for i, child in enumerate(node.children):
            c_lo = node.keys[i - 1] if i > 0 else lo
            c_hi = node.keys[i] if i < n else hi
            walk(child, depth + 1, c_lo, c_hi, False)

    walk(tree.root, 1, None, None, True)
    if len(depths) > 1:
        problems.append(f"leaves are at different depths: {sorted(depths)}")
    elif depths and depths != {tree.height}:
        problems.append(f"tree.height is {tree.height} but the leaves are at depth {min(depths)}")
    for a, b in zip(leaves, leaves[1:]):           # the linked list must match the tree order
        if a.next is not b:
            problems.append("the leaf chain does not follow the tree order")
            break
    if leaves and leaves[-1].next is not None:
        problems.append("the last leaf's next is not None")
    return problems


# --- Milestone 6 (optional): measure -------------------------------------------

def measure(n, fanouts, seed=1):
    """Build a tree of n shuffled keys for each fan-out; return one dict per fan-out:

        {"max_keys": m, "height": h, "pages_per_lookup": p, "nodes": total_pages}
    pages_per_lookup is the average pages_read per search over 1000 random present keys.
    """
    import random
    rng = random.Random(seed)
    keys = list(range(n))
    rng.shuffle(keys)
    probes = rng.sample(keys, 1000)
    rows = []
    for m in fanouts:
        t = BPlusTree(max_keys=m)
        for k in keys:
            t.insert(k, k)
        before = t.pages_read
        for k in probes:
            t.search(k)
        count, stack = 0, [t.root]
        while stack:
            node = stack.pop()
            count += 1
            if not node.leaf:
                stack.extend(node.children)
        rows.append({"max_keys": m, "height": t.height,
                     "pages_per_lookup": (t.pages_read - before) / len(probes), "nodes": count})
    return rows


if __name__ == "__main__":
    t = BPlusTree(max_keys=4)
    for k in range(1, 21):
        t.insert(k, str(k))
    print("height", t.height, "problems", validate(t))
    before = t.pages_read
    print(t.search(13), "pages touched:", t.pages_read - before)
