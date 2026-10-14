# Unit: ml-ch1

Course: **A1 Machine Learning & Data Science** (id `ml`, folder `ml/`).

## Course brief
A1 is classical machine learning and the full data-science process: framing, metrics, EDA, baselines, linear models, trees and gradient boosting, unsupervised methods, validation, leakage, calibration, interpretation, feature engineering, time series, competitions and proving value. Use scikit-learn conventions (fit/predict, X of shape (n_samples, n_features), y) in prose and listings; chapter examples that you run must use the standard library or NumPy (scikit-learn is NOT installed here; show sklearn listings labelled 'not run here' if useful, and run an equivalent you wrote). Datasets: small synthetic ones generated with a seed, described concretely. Link back to A0 for maths (ml-foundations ch 05-15).

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ml/chapters/00-start-here.html` · chapter 00 · **intro** · Part 0 (Orientation) · **Start Here**: Learning from examples, the data-science loop, and where this course fits.  → glossary `glossary-src/ml-00.json`
- `ml/chapters/01-generalisation.html` · chapter 01 · **deep** · Part 1 (Framing Problems) · **What Learning Is: Generalisation**: Training, validation and test sets, overfitting, underfitting and the no-free-lunch idea.  → glossary `glossary-src/ml-01.json`
- `ml/chapters/02-framing-metrics.html` · chapter 02 · **deep** · Part 1 (Framing Problems) · **Framing Problems & Choosing Metrics**: Turning a business question into a prediction task with a metric that matches the cost of errors.  → glossary `glossary-src/ml-02.json`
- `ml/chapters/03-eda.html` · chapter 03 · **core** · Part 1 (Framing Problems) · **Exploratory Data Analysis**: Distributions, missingness, duplicates, shifts between train and test, and the questions to ask first.  → glossary `glossary-src/ml-03.json`
- `ml/chapters/04-baselines.html` · chapter 04 · **core** · Part 1 (Framing Problems) · **Baselines First**: Majority class, simple rules and linear models: the numbers every fancy model must beat.  → glossary `glossary-src/ml-04.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ml-ch1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).