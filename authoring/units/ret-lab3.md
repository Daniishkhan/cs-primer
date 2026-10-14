# Unit: ret-lab3

Course: **A5 Retrieval, Search & Document AI** (id `ret`, folder `retrieval/`).

## Course brief
A5 covers lexical and dense retrieval, retrieval evaluation, vector indexes, RAG with citations and document AI (PDF/layout, OCR, tables/forms, visual retrieval, multilingual). Data Systems ch 17 (specialised stores) already introduced inverted indexes: build on it, do not repeat it. Spine sources: Manning, Raghavan & Schütze 'Introduction to Information Retrieval' (free online), Robertson & Zaragoza on BM25, DPR, ColBERT, SPLADE, HNSW (Malkov & Yashunin), FAISS, BEIR, MTEB/MMTEB, Anthropic 'Introducing Contextual Retrieval' (Sept 2024), Lost in the Middle, ColPali, OmniDocBench, Docling, olmOCR. Runnable examples in pure Python/NumPy over small corpora you construct; dense embeddings can be produced by a tiny deterministic method (e.g. hashed character n-grams, or SVD of a co-occurrence matrix) clearly labelled as a stand-in for a trained embedder. OCR/VLM leaderboards change monthly: dated boxes only.

## Your assignment: labs

- Page `retrieval/labs/lab-05-rag-citations.html` (data-lab `L5`, after Part 5) with code in `retrieval/labs/code/lab05/` · **Lab 5: RAG with Verified Citations**: Chunk, retrieve, answer with citations and reject any answer whose quotes are not in the source. Related chapters: 13, 14, 16.
- Page `retrieval/labs/lab-06-document-pipeline.html` (data-lab `L6`, after Part 6) with code in `retrieval/labs/code/lab06/` · **Lab 6: A Document Understanding Pipeline**: From OCR boxes to reading order, sections and tables, with character error rate measured. Related chapters: 18, 19, 20.
  - Design notes: Inputs are OCR-style JSON fixtures: words with bounding boxes and confidences for a few synthetic pages (two-column layout, a header/footer, a table, a form). Implement reading-order reconstruction (columns, XY-cut), header/footer removal, section detection, table cell grid reconstruction from boxes, key-value extraction for a form, and character error rate against ground truth.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `retrieval/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ret-lab3/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).