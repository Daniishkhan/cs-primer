# Unit: ret-case1

Course: **A5 Retrieval, Search & Document AI** (id `ret`, folder `retrieval/`).

## Course brief
A5 covers lexical and dense retrieval, retrieval evaluation, vector indexes, RAG with citations and document AI (PDF/layout, OCR, tables/forms, visual retrieval, multilingual). Data Systems ch 17 (specialised stores) already introduced inverted indexes: build on it, do not repeat it. Spine sources: Manning, Raghavan & Schütze 'Introduction to Information Retrieval' (free online), Robertson & Zaragoza on BM25, DPR, ColBERT, SPLADE, HNSW (Malkov & Yashunin), FAISS, BEIR, MTEB/MMTEB, Anthropic 'Introducing Contextual Retrieval' (Sept 2024), Lost in the Middle, ColPali, OmniDocBench, Docling, olmOCR. Runnable examples in pure Python/NumPy over small corpora you construct; dense embeddings can be produced by a tiny deterministic method (e.g. hashed character n-grams, or SVD of a co-occurrence matrix) clearly labelled as a stand-in for a trained embedder. OCR/VLM leaderboards change monthly: dated boxes only.

## Your assignment: case studies

- `retrieval/cases/case-01-contextual-retrieval.html` (data-case `C1`) · **Contextual Retrieval** · pattern: Context before embedding · Prepending chunk context, hybrid search and reranking, and the failure rates each step removed. Related: 14, 10.
- `retrieval/cases/case-02-bert-search.html` (data-case `C2`) · **BERT Comes to Web Search** · pattern: Understanding queries · When a search engine started reading the little words in queries. Related: 03, 07.
- `retrieval/cases/case-03-lost-in-the-middle.html` (data-case `C3`) · **Lost in the Middle** · pattern: Long context is not free · Models that used evidence at the start and end of the context and missed it in the middle. Related: 13, agt:12.
- `retrieval/cases/case-04-air-canada.html` (data-case `C4`) · **The Chatbot's Promise: Air Canada** · pattern: Grounded answers are a liability question · A tribunal held an airline to a refund policy its chatbot made up. Related: 16, 17.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ret-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).