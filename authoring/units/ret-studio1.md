# Unit: ret-studio1

Course: **A5 Retrieval, Search & Document AI** (id `ret`, folder `retrieval/`).

## Course brief
A5 covers lexical and dense retrieval, retrieval evaluation, vector indexes, RAG with citations and document AI (PDF/layout, OCR, tables/forms, visual retrieval, multilingual). Data Systems ch 17 (specialised stores) already introduced inverted indexes: build on it, do not repeat it. Spine sources: Manning, Raghavan & Schütze 'Introduction to Information Retrieval' (free online), Robertson & Zaragoza on BM25, DPR, ColBERT, SPLADE, HNSW (Malkov & Yashunin), FAISS, BEIR, MTEB/MMTEB, Anthropic 'Introducing Contextual Retrieval' (Sept 2024), Lost in the Middle, ColPali, OmniDocBench, Docling, olmOCR. Runnable examples in pure Python/NumPy over small corpora you construct; dense embeddings can be produced by a tiny deterministic method (e.g. hashed character n-grams, or SVD of a co-occurrence matrix) clearly labelled as a stand-in for a trained embedder. OCR/VLM leaderboards change monthly: dated boxes only.

## Your assignment: design studios

- `retrieval/studios/studio-01-enterprise-search.html` (data-studio `S1`, after Part 4) · **Design Enterprise Search with Permissions**: Many sources, per-document access control, freshness and relevance across a whole company. Related chapters: 10, 11, 12.
- `retrieval/studios/studio-02-policy-assistant.html` (data-studio `S2`, after Part 5) · **Design a Policy & Regulation Assistant**: Answers people will act on, from a corpus that changes, with citations a reviewer can check. Related chapters: 13, 16, 17.
- `retrieval/studios/studio-03-document-processing.html` (data-studio `S3`, after Part 6) · **Design a Document-Processing Pipeline**: Millions of scanned forms and invoices a month, with extraction accuracy and human review. Related chapters: 18, 19, 20.
- The course toolbox `retrieval/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `opensearch` (Elasticsearch & OpenSearch), `vector-dbs` (pgvector, Qdrant & friends), `sbert` (sentence-transformers), `ir-eval` (ranx & pytrec_eval), `docling` (Docling, Marker & MinerU), `ocr` (Tesseract & PaddleOCR). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ret-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).