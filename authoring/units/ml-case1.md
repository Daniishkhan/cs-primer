# Unit: ml-case1

Course: **A1 Machine Learning & Data Science** (id `ml`, folder `ml/`).

## Course brief
A1 is classical machine learning and the full data-science process: framing, metrics, EDA, baselines, linear models, trees and gradient boosting, unsupervised methods, validation, leakage, calibration, interpretation, feature engineering, time series, competitions and proving value. Use scikit-learn conventions (fit/predict, X of shape (n_samples, n_features), y) in prose and listings; chapter examples that you run must use the standard library or NumPy (scikit-learn is NOT installed here; show sklearn listings labelled 'not run here' if useful, and run an equivalent you wrote). Datasets: small synthetic ones generated with a seed, described concretely. Link back to A0 for maths (ml-foundations ch 05-15).

## Your assignment: case studies

- `ml/cases/case-01-netflix-prize.html` (data-case `C1`) · **The Netflix Prize** · pattern: Ensembles vs deployability · A million-dollar ensemble that won the competition and was never fully deployed. Related: 09, 20, 21.
- `ml/cases/case-02-google-flu-trends.html` (data-case `C2`) · **Google Flu Trends** · pattern: Drift and spurious features · Search queries that predicted flu, until they did not, and what the post-mortems found. Related: 14, 21.
- `ml/cases/case-03-zillow-offers.html` (data-case `C3`) · **Zillow Offers** · pattern: Model risk in a business · An algorithmic home-buying business that shut down after its price forecasts met a turning market. Related: 18, 21.
- `ml/cases/case-04-amazon-recruiting.html` (data-case `C4`) · **A Recruiting Model That Learned Bias** · pattern: Biased labels · A CV-screening model trained on past hiring decisions, and why removing words did not fix it. Related: 02, 16.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ml-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).