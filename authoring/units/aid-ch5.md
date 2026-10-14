# Unit: aid-ch5

Course: **A8 Applied AI Delivery Studio** (id `aid`, folder `ai-delivery/`).

## Course brief
A8 is the capstone: the applied / forward-deployed AI engineer's job. Discovery (interviews about past behaviour, requirements under ambiguity, capturing expert knowledge, feasibility triage), building the proof (riskiest-assumption prototypes, evaluation plans customers trust, choosing models under constraints), domains (finance, healthcare, legal, public sector: what each requires and forbids, with real regulation named and dated), delivery (PoC to production, restricted/on-prem/air-gapped environments, cost and ROI, security reviews), productisation and communication (research to product, writing for customers, take-homes, portfolios, interviews). It is broad, not tied to one employer. Good sources: Rob Fitzpatrick 'The Mom Test' (customer interviews), Hamel Husain on evals and on AI consulting, Chip Huyen 'AI Engineering' (2025), Palantir and OpenAI/Anthropic writing on forward-deployed engineering, Sakana AI's public 'Unofficial Guide' and its MUFG lending interview as one example among many, regulators' guidance (US Fed SR 11-7 model risk management, FDA AI-enabled device guidance, EU AI Act, HIPAA, GDPR). Lean heavily on links to A4-A7 and track-1 security/reliability chapters rather than re-teaching.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ai-delivery/chapters/16-research-to-product.html` · chapter 16 · **core** · Part 5 (Productisation & Communication) · **Turning Research into Products**: From a paper and a repository to an interface, SLOs, documentation and support.  → glossary `glossary-src/aid-16.json`
- `ai-delivery/chapters/17-writing-for-customers.html` · chapter 17 · **deep** · Part 5 (Productisation & Communication) · **Writing for Customers**: Status reports, analysis memos and presenting a failure honestly to the people paying.  → glossary `glossary-src/aid-17.json`
- `ai-delivery/chapters/18-getting-hired.html` · chapter 18 · **deep** · Part 5 (Productisation & Communication) · **Take-Homes, Portfolios & Interviews**: What applied AI teams test, how to scope a take-home, and a portfolio that proves judgement.  → glossary `glossary-src/aid-18.json`
- `ai-delivery/chapters/19-where-next.html` · chapter 19 · **intro** · Part 5 (Productisation & Communication) · **Where Next**: Keeping up without drowning, and the next steps after this path.  → glossary `glossary-src/aid-19.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/aid-ch5/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).