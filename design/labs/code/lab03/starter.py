"""Lab 3: Feed Fan-out Simulator, your starter.

A scaled-down social network (a thousand users, not a hundred million) with the same shape as
chapter 9's: one-way follows, and a few accounts with a great many followers. We build the graph,
then replay one seeded stream of posts and feed loads through three timeline strategies and
count the work each does.

  push    fan-out on write: a post is inserted into every follower's timeline list (capped)
  pull    fan-out on read: a feed load merges the recent posts of everyone you follow
  hybrid  push for ordinary authors, pull for "celebrities" (more followers than a threshold)

Standard library only; every random draw comes from a seeded random.Random.
"""
import heapq
import math
import random
from collections import deque

# ------------------------------------------------------------------------------------
# Given: knobs, cost weights and the counters every model fills in
# ------------------------------------------------------------------------------------
CAP = 50            # newest post ids kept in a pushed timeline (and in an author's recent list)
PAGE = 20           # a feed page shows the newest PAGE posts
W_WRITE = 1.0       # one timeline insert (or author-list append)
W_LIST = 1.0        # one cold list fetched at read time
W_HOT = 0.25        # a list of a very popular author: always in cache, so cheaper
W_MERGE = 0.1       # one heap operation while merging
FANOUT_BUDGET = 100     # SLO: no pushed post may need more than this many inserts (freshness)
LISTS_BUDGET = 20       # SLO: p99 feed load may fetch at most this many lists (read latency)
N_USERS, MEAN_FOLLOWERS, CAP_FRAC = 2000, 15, 0.15   # the standard graph used by the experiments


class Counters:
    """Everything the lab measures. Models only ever add to these."""

    def __init__(self):
        self.posts = 0
        self.loads = 0
        self.writes = 0             # timeline inserts + author-list appends
        self.list_reads = 0         # lists fetched at read time (own timeline counts as one)
        self.hot_list_reads = 0     # ... of which lists of hot (very popular) authors
        self.merge_ops = 0          # heap pushes and pops while merging
        self.max_fanout = 0         # the most inserts any single post caused
        self.lists_per_load = []    # lists fetched by each feed load

    def cost(self):
        cold = self.list_reads - self.hot_list_reads
        return (self.writes * W_WRITE + cold * W_LIST + self.hot_list_reads * W_HOT
                + self.merge_ops * W_MERGE)

    def p99_lists(self):
        xs = sorted(self.lists_per_load)
        return xs[max(0, math.ceil(0.99 * len(xs)) - 1)] if xs else 0


# ------------------------------------------------------------------------------------
# Milestone 1: a seeded power-law follower graph
# ------------------------------------------------------------------------------------
class Graph:
    """followers[a] = sorted users who follow a;  followees[u] = sorted authors u follows."""

    def __init__(self, followers, followees):
        self.followers, self.followees = followers, followees
        self.n = len(followers)

    def edges(self):
        return sum(len(f) for f in self.followers)

    def follower_count(self, a):
        return len(self.followers[a])


def zipf_counts(n, mean, s=1.0, cap_frac=CAP_FRAC):
    """Follower counts for n authors by rank: about c * rank**-s, capped at cap_frac * n.

    c is found by bisection so the MEAN stays `mean`; the counts are then rounded to integers
    (largest remainder) so the total is exactly round(mean * n). Returned largest first.
    """
    raise NotImplementedError("TODO milestone 1: zipf_counts")


def make_graph(n, mean_followers, seed, s=1.0, cap_frac=CAP_FRAC):
    """A directed follower graph with Zipf-distributed follower counts.

    Which user is the star is random (a seeded shuffle); each author's followers are a random
    sample of the other users. Nobody follows themselves; no duplicate edges.
    """
    raise NotImplementedError("TODO milestone 1: make_graph")


def standard_graph(seed=1):
    """The graph the experiments use: 2,000 users, 15 followers on average, Zipf s = 1, top accounts capped at 300."""
    return make_graph(N_USERS, MEAN_FOLLOWERS, seed)


# ------------------------------------------------------------------------------------
# Given: a seeded workload (one stream of posts and feed loads)
# ------------------------------------------------------------------------------------
def make_workload(graph, seed, posts_per_user=0.5, reads_per_post=5.0):
    """A time-ordered list of ('post', author, post_id) and ('read', user, None) events.

    Post ids increase with time (like Snowflake ids, chapter 7), so "newest" means "largest id".
    Authors and readers are uniform over users; reads_per_post is the read:write ratio.
    """
    rng = random.Random(seed * 7919 + 13)
    n_posts = int(graph.n * posts_per_user)
    n_reads = int(n_posts * reads_per_post)
    ev = [(rng.random(), 0, rng.randrange(graph.n)) for _ in range(n_posts)]
    ev += [(rng.random(), 1, rng.randrange(graph.n)) for _ in range(n_reads)]
    ev.sort()
    out, pid = [], 0
    for _, kind, who in ev:
        if kind == 0:
            pid += 1
            out.append(("post", who, pid))
        else:
            out.append(("read", who, None))
    return out


def merge_newest(lists, k, counters):
    """K-way merge of lists of post ids (each newest first); return the k newest ids overall.

    A heap holds the head of every non-empty list. Each heap push and each pop adds 1 to
    counters.merge_ops. Stop after k results.
    """
    heap, its, out = [], [iter(l) for l in lists], []
    for i, it in enumerate(its):
        head = next(it, None)
        if head is not None:
            heapq.heappush(heap, (-head, i))
            counters.merge_ops += 1
    while heap and len(out) < k:
        neg, i = heapq.heappop(heap)
        counters.merge_ops += 1
        out.append(-neg)
        nxt = next(its[i], None)
        if nxt is not None:
            heapq.heappush(heap, (-nxt, i))
            counters.merge_ops += 1
    return out


# ------------------------------------------------------------------------------------
# Milestone 2: push (fan-out on write)
# ------------------------------------------------------------------------------------
class PushModel:
    """Every post is inserted into each follower's timeline (a list of ids, newest first, <= cap)."""

    def __init__(self, graph, cap, counters):
        self.graph, self.cap, self.c = graph, cap, counters
        self.timeline = [deque() for _ in range(graph.n)]

    def post(self, author, post_id):
        """Insert post_id at the front of every follower's timeline; trim to cap; count the work."""
        raise NotImplementedError("TODO milestone 2: PushModel.post")

    def read(self, user, k):
        """The k newest ids in the user's own timeline. One list fetched, no merging."""
        raise NotImplementedError("TODO milestone 2: PushModel.read")


# ------------------------------------------------------------------------------------
# Milestone 3: pull (fan-out on read)
# ------------------------------------------------------------------------------------
class PullModel:
    """Posts are only appended to the author's own recent list; readers merge their followees' lists."""

    def __init__(self, graph, cap, counters, hot_cut):
        self.graph, self.cap, self.c, self.hot_cut = graph, cap, counters, hot_cut
        self.recent = [deque() for _ in range(graph.n)]

    def post(self, author, post_id):
        """Append to the author's recent list (trim to cap): one write."""
        raise NotImplementedError("TODO milestone 3: PullModel.post")

    def read(self, user, k):
        """Fetch every followee's recent list and merge: the k newest ids across all of them."""
        raise NotImplementedError("TODO milestone 3: PullModel.read")


# ------------------------------------------------------------------------------------
# Milestone 4: hybrid
# ------------------------------------------------------------------------------------
class HybridModel:
    """Push for authors with <= threshold followers; authors above it ("celebrities") are only
    appended to their own recent list and merged in at read time.

    threshold=None means nobody is a celebrity (pure push); threshold=0 means everybody with a
    follower is (pure pull).
    """

    def __init__(self, graph, cap, counters, threshold, hot_cut):
        self.graph, self.cap, self.c, self.hot_cut = graph, cap, counters, hot_cut
        self.threshold = math.inf if threshold is None else threshold
        self.timeline = [deque() for _ in range(graph.n)]
        self.recent = {}
        self.celeb_followees = [[a for a in graph.followees[u] if self.is_celebrity(a)] for u in range(graph.n)]

    def is_celebrity(self, author):
        raise NotImplementedError("TODO milestone 4: HybridModel.is_celebrity")

    def post(self, author, post_id):
        raise NotImplementedError("TODO milestone 4: HybridModel.post")

    def read(self, user, k):
        """Merge the user's pushed timeline with the recent lists of the celebrities they follow."""
        raise NotImplementedError("TODO milestone 4: HybridModel.read")


def default_hot_cut(graph):
    """Authors with at least 4x the mean number of followers are 'hot': their lists stay cached."""
    return 4 * max(1, graph.edges() // graph.n)


def build_model(strategy, graph, counters, cap=CAP, threshold=None, hot_cut=None):
    hot_cut = default_hot_cut(graph) if hot_cut is None else hot_cut
    if strategy == "push":
        return PushModel(graph, cap, counters)
    if strategy == "pull":
        return PullModel(graph, cap, counters, hot_cut)
    if strategy == "hybrid":
        return HybridModel(graph, cap, counters, threshold, hot_cut)
    raise ValueError(f"unknown strategy {strategy!r}")


def run(graph, workload, strategy, cap=CAP, k=PAGE, threshold=None, hot_cut=None):
    """Replay the workload through one strategy. Returns (pages, counters).

    pages[i] is the feed page returned by the i-th read event (a list of post ids, newest first).
    """
    counters = Counters()
    model = build_model(strategy, graph, counters, cap, threshold, hot_cut)
    pages = []
    for kind, who, pid in workload:
        if kind == "post":
            model.post(who, pid)
        else:
            pages.append(model.read(who, k))
    return pages, counters


def mismatches(graph, workload, threshold, cap=CAP, k=PAGE):
    """Indexes of the feed loads where the hybrid page differs from the pure push page, the pure pull
    page or the uncapped reference. An empty list means the hybrid is correct."""
    raise NotImplementedError("TODO milestone 4: mismatches")


def reference_pages(graph, workload, k=PAGE):
    """Ground truth, no caps and no cleverness: the k newest posts by anyone the user follows."""
    posts_by = [[] for _ in range(graph.n)]
    pages = []
    for kind, who, pid in workload:
        if kind == "post":
            posts_by[who].append(pid)
        else:
            ids = [p for a in graph.followees[who] for p in posts_by[a]]
            pages.append(sorted(ids, reverse=True)[:k])
    return pages


# ------------------------------------------------------------------------------------
# Milestone 5: sweep the threshold and the read:write ratio
# ------------------------------------------------------------------------------------
def candidate_thresholds(graph, ratio=1.5):
    """Thresholds to try: 0 (everyone pulled = pure pull), then a geometric ladder from a quarter of the
    mean follower count up to the largest account (ratio 1.5 per rung), then None (nobody pulled = pure push)."""
    raise NotImplementedError("TODO milestone 5: candidate_thresholds")


def sweep(graph, thresholds, reads_per_post, seed, cap=CAP, k=PAGE, hot_cut=None):
    """Run the hybrid model at every threshold on one workload. Returns a list of dicts:

    {threshold, cost, writes, list_reads, merge_ops, max_fanout, p99_lists}
    """
    raise NotImplementedError("TODO milestone 5: sweep")


def best_threshold(points, fanout_budget=FANOUT_BUDGET, lists_budget=LISTS_BUDGET):
    """The cheapest point whose worst fan-out and p99 lists-per-load both fit their budgets.

    Returns the chosen dict, or None if no threshold satisfies both SLOs.
    """
    raise NotImplementedError("TODO milestone 5: best_threshold")
