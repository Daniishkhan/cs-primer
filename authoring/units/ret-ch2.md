# Unit: ret-ch2

Course: **A5 Retrieval, Search & Document AI** (id `ret`, folder `retrieval/`).

## Course brief
A5 covers lexical and dense retrieval, retrieval evaluation, vector indexes, RAG with citations and document AI (PDF/layout, OCR, tables/forms, visual retrieval, multilingual). Data Systems ch 17 (specialised stores) already introduced inverted indexes: build on it, do not repeat it. Spine sources: Manning, Raghavan & Schütze 'Introduction to Information Retrieval' (free online), Robertson & Zaragoza on BM25, DPR, ColBERT, SPLADE, HNSW (Malkov & Yashunin), FAISS, BEIR, MTEB/MMTEB, Anthropic 'Introducing Contextual Retrieval' (Sept 2024), Lost in the Middle, ColPali, OmniDocBench, Docling, olmOCR. Runnable examples in pure Python/NumPy over small corpora you construct; dense embeddings can be produced by a tiny deterministic method (e.g. hashed character n-grams, or SVD of a co-occurrence matrix) clearly labelled as a stand-in for a trained embedder. OCR/VLM leaderboards change monthly: dated boxes only.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `retrieval/chapters/04-relevance-metrics.html` · chapter 04 · **deep** · Part 2 (Measuring Retrieval) · **Relevance Metrics**: Precision, recall, MRR, MAP and nDCG: what each rewards and which question it answers.  → glossary `glossary-src/ret-04.json`
- `retrieval/chapters/05-test-collections.html` · chapter 05 · **deep** · Part 2 (Measuring Retrieval) · **Building a Test Collection**: Queries, judgements, pooling and guidelines: a gold set you can trust in a week.  → glossary `glossary-src/ret-05.json`
- `retrieval/chapters/06-retrieval-benchmarks.html` · chapter 06 · **core** · Part 2 (Measuring Retrieval) · **Public Benchmarks & Their Limits**: BEIR, MTEB and domain benchmarks as shortlist filters, not decisions.  → glossary `glossary-src/ret-06.json`
- `retrieval/chapters/07-dense-retrieval.html` · chapter 07 · **deep** · Part 3 (Dense Retrieval) · **Dense Retrieval**: Bi-encoders, contrastive training, hard negatives and fine-tuning an embedder.  → glossary `glossary-src/ret-07.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ret-ch2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).