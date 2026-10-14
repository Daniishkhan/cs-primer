# Unit: ml-studio1

Course: **A1 Machine Learning & Data Science** (id `ml`, folder `ml/`).

## Course brief
A1 is classical machine learning and the full data-science process: framing, metrics, EDA, baselines, linear models, trees and gradient boosting, unsupervised methods, validation, leakage, calibration, interpretation, feature engineering, time series, competitions and proving value. Use scikit-learn conventions (fit/predict, X of shape (n_samples, n_features), y) in prose and listings; chapter examples that you run must use the standard library or NumPy (scikit-learn is NOT installed here; show sklearn listings labelled 'not run here' if useful, and run an equivalent you wrote). Datasets: small synthetic ones generated with a seed, described concretely. Link back to A0 for maths (ml-foundations ch 05-15).

## Your assignment: design studios

- `ml/studios/studio-01-churn.html` (data-studio `S1`, after Part 1) · **Frame a Churn Prediction Problem**: From 'reduce churn' to a target, a prediction window, a metric, a baseline and an action. Related chapters: 02, 03, 04.
- `ml/studios/studio-02-fraud.html` (data-studio `S2`, after Part 4) · **Design a Fraud Detection Model**: Rare positives, delayed labels, adversaries and a review queue with limited capacity. Related chapters: 13, 14, 15.
- `ml/studios/studio-03-forecasting.html` (data-studio `S3`, after Part 5) · **Design Demand Forecasting for a Retailer**: Thousands of products, promotions, stockouts and the decision the forecast feeds. Related chapters: 17, 18.
- The course toolbox `ml/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `sklearn` (scikit-learn), `gbdt` (XGBoost, LightGBM & CatBoost), `shap` (SHAP), `tracking` (MLflow & Weights & Biases), `kaggle` (Kaggle), `evidently` (Drift monitoring tools). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ml-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).