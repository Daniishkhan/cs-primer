# Unit: aid-lab2

Course: **A8 Applied AI Delivery Studio** (id `aid`, folder `ai-delivery/`).

## Course brief
A8 is the capstone: the applied / forward-deployed AI engineer's job. Discovery (interviews about past behaviour, requirements under ambiguity, capturing expert knowledge, feasibility triage), building the proof (riskiest-assumption prototypes, evaluation plans customers trust, choosing models under constraints), domains (finance, healthcare, legal, public sector: what each requires and forbids, with real regulation named and dated), delivery (PoC to production, restricted/on-prem/air-gapped environments, cost and ROI, security reviews), productisation and communication (research to product, writing for customers, take-homes, portfolios, interviews). It is broad, not tied to one employer. Good sources: Rob Fitzpatrick 'The Mom Test' (customer interviews), Hamel Husain on evals and on AI consulting, Chip Huyen 'AI Engineering' (2025), Palantir and OpenAI/Anthropic writing on forward-deployed engineering, Sakana AI's public 'Unofficial Guide' and its MUFG lending interview as one example among many, regulators' guidance (US Fed SR 11-7 model risk management, FDA AI-enabled device guidance, EU AI Act, HIPAA, GDPR). Lean heavily on links to A4-A7 and track-1 security/reliability chapters rather than re-teaching.

## Your assignment: labs

- Page `ai-delivery/labs/lab-03-pii-pipeline.html` (data-lab `L3`, after Part 4) with code in `ai-delivery/labs/code/lab03/` · **Lab 3: A PII Redaction & Audit Pipeline**: Detect and redact personal data, keep reversible tokens for authorised users and log every access. Related chapters: 13, 15.
- Page `ai-delivery/labs/lab-04-take-home.html` (data-lab `L4`, after Part 5) with code in `ai-delivery/labs/code/lab04/` · **Lab 4: A Take-Home, End to End**: A timed document-QA system graded by hidden tests, with the memo that goes with it. Related chapters: 05, 06, 18.
  - Design notes: The take-home: a small document-QA mini-system over a provided corpus fixture (e.g. a few short annual-report-style documents as text with page numbers), with a hidden-test style check (questions with gold answers and gold pages); milestones: requirements restatement file (checked for required headings), baseline retrieval, answer with page citations, abstention for unanswerable questions, eval report with bootstrap intervals, and a memo template. Use the stand-in model; numbers must tie to pages.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `ai-delivery/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/aid-lab2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).