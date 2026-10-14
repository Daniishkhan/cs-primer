# Unit: ml-lab1

Course: **A1 Machine Learning & Data Science** (id `ml`, folder `ml/`).

## Course brief
A1 is classical machine learning and the full data-science process: framing, metrics, EDA, baselines, linear models, trees and gradient boosting, unsupervised methods, validation, leakage, calibration, interpretation, feature engineering, time series, competitions and proving value. Use scikit-learn conventions (fit/predict, X of shape (n_samples, n_features), y) in prose and listings; chapter examples that you run must use the standard library or NumPy (scikit-learn is NOT installed here; show sklearn listings labelled 'not run here' if useful, and run an equivalent you wrote). Datasets: small synthetic ones generated with a seed, described concretely. Link back to A0 for maths (ml-foundations ch 05-15).

## Your assignment: labs

- Page `ml/labs/lab-01-linear-models.html` (data-lab `L1`, after Part 2) with code in `ml/labs/code/lab01/` · **Lab 1: Linear & Logistic Regression from Scratch**: Closed form and gradient descent, L1 and L2 penalties, and log-loss, all checked against hand values. Related chapters: 05, 06.
- Page `ml/labs/lab-02-trees-boosting.html` (data-lab `L2`, after Part 2) with code in `ml/labs/code/lab02/` · **Lab 2: Trees & Gradient Boosting from Scratch**: A CART tree, a random forest and a gradient-boosting regressor in plain Python. Related chapters: 08, 09.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `ml/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ml-lab1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).