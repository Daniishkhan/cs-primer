# Unit: ml-ch5

Course: **A1 Machine Learning & Data Science** (id `ml`, folder `ml/`).

## Course brief
A1 is classical machine learning and the full data-science process: framing, metrics, EDA, baselines, linear models, trees and gradient boosting, unsupervised methods, validation, leakage, calibration, interpretation, feature engineering, time series, competitions and proving value. Use scikit-learn conventions (fit/predict, X of shape (n_samples, n_features), y) in prose and listings; chapter examples that you run must use the standard library or NumPy (scikit-learn is NOT installed here; show sklearn listings labelled 'not run here' if useful, and run an equivalent you wrote). Datasets: small synthetic ones generated with a seed, described concretely. Link back to A0 for maths (ml-foundations ch 05-15).

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ml/chapters/17-feature-engineering.html` · chapter 17 · **deep** · Part 5 (Features & Competitions) · **Feature Engineering**: Encodings, aggregates, interactions, target encoding done safely, and features from domain knowledge.  → glossary `glossary-src/ml-17.json`
- `ml/chapters/18-time-series.html` · chapter 18 · **core** · Part 5 (Features & Competitions) · **Time Series Forecasting**: Trend, seasonality, lag features, backtesting and the forecasting baselines that are hard to beat.  → glossary `glossary-src/ml-18.json`
- `ml/chapters/19-tabular-deep-learning.html` · chapter 19 · **intro** · Part 5 (Features & Competitions) · **Tabular Deep Learning & Foundation Models**: Neural nets for tables, TabPFN-style foundation models, and when they beat boosted trees.  → glossary `glossary-src/ml-19.json`
- `ml/chapters/20-competitions.html` · chapter 20 · **core** · Part 5 (Features & Competitions) · **How Competitions Are Won**: Validation strategy, diverse models, stacking and the habits competition winners describe.  → glossary `glossary-src/ml-20.json`
- `ml/chapters/21-model-to-value.html` · chapter 21 · **core** · Part 6 (From Model to Value) · **From Model to Value**: Offline metrics versus business outcomes, A/B tests, monitoring, drift and retraining.  → glossary `glossary-src/ml-21.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ml-ch5/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).