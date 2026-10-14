# Unit: aid-studio1

Course: **A8 Applied AI Delivery Studio** (id `aid`, folder `ai-delivery/`).

## Course brief
A8 is the capstone: the applied / forward-deployed AI engineer's job. Discovery (interviews about past behaviour, requirements under ambiguity, capturing expert knowledge, feasibility triage), building the proof (riskiest-assumption prototypes, evaluation plans customers trust, choosing models under constraints), domains (finance, healthcare, legal, public sector: what each requires and forbids, with real regulation named and dated), delivery (PoC to production, restricted/on-prem/air-gapped environments, cost and ROI, security reviews), productisation and communication (research to product, writing for customers, take-homes, portfolios, interviews). It is broad, not tied to one employer. Good sources: Rob Fitzpatrick 'The Mom Test' (customer interviews), Hamel Husain on evals and on AI consulting, Chip Huyen 'AI Engineering' (2025), Palantir and OpenAI/Anthropic writing on forward-deployed engineering, Sakana AI's public 'Unofficial Guide' and its MUFG lending interview as one example among many, regulators' guidance (US Fed SR 11-7 model risk management, FDA AI-enabled device guidance, EU AI Act, HIPAA, GDPR). Lean heavily on links to A4-A7 and track-1 security/reliability chapters rather than re-teaching.

## Your assignment: design studios

- `ai-delivery/studios/studio-01-contract-review.html` (data-studio `S1`, after Part 2) · **Take-Home: Contract Clause Review**: A legal team wants risky clauses flagged in supplier contracts. Scope it, build the proof, report. Related chapters: 05, 06, 10.
- `ai-delivery/studios/studio-02-analyst-assistant.html` (data-studio `S2`, after Part 2) · **Take-Home: An Analyst's Research Assistant**: Answer questions over annual reports with numbers that tie to the page they came from. Related chapters: 05, 06, 08.
- `ai-delivery/studios/studio-03-claims-triage.html` (data-studio `S3`, after Part 3) · **Take-Home: Insurance Claims Triage**: Route incoming claims with attachments, and decide what never goes to a model. Related chapters: 04, 06.
- The course toolbox `ai-delivery/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `demo-uis` (Gradio & Streamlit), `fastapi` (FastAPI), `compose` (Docker Compose), `pii-tools` (Presidio for redaction), `writing` (Writing & diagram tools). See guide section 11.

These are take-home simulations (guide section 10, A8 rules). Make sample inputs concrete (describe or include small sample documents inline), and worked answers show an excellent submission's key artefacts.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/aid-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).