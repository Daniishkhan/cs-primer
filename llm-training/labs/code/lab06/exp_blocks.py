"""Milestone 1 experiment: block tables. Three requests grow and shrink; pages end up scattered."""
from solution import PageAllocator

a = PageAllocator(total_pages=10, page_tokens=4)
a.reserve("A", 10)      # 3 pages
a.reserve("B", 6)       # 2 pages
a.reserve("C", 7)       # 2 pages
print("start        ", {r: a.block_table(r) for r in "ABC"}, "free", a.free_pages)
a.release("B")
print("B finishes   ", {r: a.block_table(r) for r in "AC"}, "free", a.free_pages)
a.reserve("A", 17)      # 5 pages: grows by two
a.reserve("D", 8)       # 2 pages
print("A grows, D in", {r: a.block_table(r) for r in "ACD"}, "free", a.free_pages)
print("a request of 12 tokens needs", a.pages_needed(12), "pages; reserve ->", a.reserve("E", 12), "(", a.free_pages, "page free)")
