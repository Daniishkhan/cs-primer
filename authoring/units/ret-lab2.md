# Unit: ret-lab2

Course: **A5 Retrieval, Search & Document AI** (id `ret`, folder `retrieval/`).

## Course brief
A5 covers lexical and dense retrieval, retrieval evaluation, vector indexes, RAG with citations and document AI (PDF/layout, OCR, tables/forms, visual retrieval, multilingual). Data Systems ch 17 (specialised stores) already introduced inverted indexes: build on it, do not repeat it. Spine sources: Manning, Raghavan & Schütze 'Introduction to Information Retrieval' (free online), Robertson & Zaragoza on BM25, DPR, ColBERT, SPLADE, HNSW (Malkov & Yashunin), FAISS, BEIR, MTEB/MMTEB, Anthropic 'Introducing Contextual Retrieval' (Sept 2024), Lost in the Middle, ColPali, OmniDocBench, Docling, olmOCR. Runnable examples in pure Python/NumPy over small corpora you construct; dense embeddings can be produced by a tiny deterministic method (e.g. hashed character n-grams, or SVD of a co-occurrence matrix) clearly labelled as a stand-in for a trained embedder. OCR/VLM leaderboards change monthly: dated boxes only.

## Your assignment: labs

- Page `retrieval/labs/lab-03-hybrid.html` (data-lab `L3`, after Part 3) with code in `retrieval/labs/code/lab03/` · **Lab 3: Hybrid Retrieval & Reranking**: Dense vectors, BM25, reciprocal rank fusion and a reranker, each measured with your harness. Related chapters: 07, 08, 10.
  - Design notes: Provide a deterministic stand-in embedder (e.g. hashed character trigram TF-IDF vectors, normalised) clearly labelled; the learner implements cosine top-k, BM25 (or imports from a provided module), reciprocal rank fusion and a simple reranker (e.g. a hand-weighted feature cross-encoder stand-in), each evaluated with nDCG@10 and recall@20 on a provided judged collection.
- Page `retrieval/labs/lab-04-hnsw.html` (data-lab `L4`, after Part 4) with code in `retrieval/labs/code/lab04/` · **Lab 4: HNSW from Scratch**: Build a hierarchical navigable small-world graph and chart recall against search effort. Related chapters: 11.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `retrieval/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ret-lab2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).