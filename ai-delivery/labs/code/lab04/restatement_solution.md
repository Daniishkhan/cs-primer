# Requirements restatement

## Goal
A finance analyst asks plain-language questions about three annual reports and wants a short answer with the page it came from, or a clear statement that the reports do not say. A good answer is one the analyst can check by opening that page.

## Inputs
Three invented annual reports of six pages each (Harbourline Freight, Fernwood Energy, Calder & Moss Retail), as plain text with page numbers, and twelve example questions with answers and pages. No tables, scans or images. A reviewer holds more questions that I cannot see.

## Assumptions
- A question names its company, so the company decides which report to search.
- A page is the right unit to retrieve and to cite; nobody needs a paragraph reference.
- A wrong answer is worse than no answer, so I abstain when I cannot support a figure from the page.
- Figures are quoted as printed; I do not convert currencies or recompute totals.

## Questions for the customer
- Is "not in the reports" acceptable for a question that needs arithmetic across pages?
- Who reads the answers, and do they open the cited page every time?
- Which costs more: refusing a fair question, or answering one the reports cannot support?
- Should a prior-year figure be returned when the question names a different year?

## Out of scope
Tables, scanned pages, arithmetic across pages, other languages, a user interface and fine-tuning. The time goes to evidence, not features.

## Success measures
- At least 80% of 40 hidden questions correct (right figure on the right page, or a correct refusal), reported with a 95% interval.
- Every figure in an answer appears on the page it cites.
- Better than the retrieval-only baseline, with the size of the gain given as a paired interval.
