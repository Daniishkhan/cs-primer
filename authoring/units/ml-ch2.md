# Unit: ml-ch2

Course: **A1 Machine Learning & Data Science** (id `ml`, folder `ml/`).

## Course brief
A1 is classical machine learning and the full data-science process: framing, metrics, EDA, baselines, linear models, trees and gradient boosting, unsupervised methods, validation, leakage, calibration, interpretation, feature engineering, time series, competitions and proving value. Use scikit-learn conventions (fit/predict, X of shape (n_samples, n_features), y) in prose and listings; chapter examples that you run must use the standard library or NumPy (scikit-learn is NOT installed here; show sklearn listings labelled 'not run here' if useful, and run an equivalent you wrote). Datasets: small synthetic ones generated with a seed, described concretely. Link back to A0 for maths (ml-foundations ch 05-15).

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ml/chapters/05-linear-models.html` · chapter 05 · **deep** · Part 2 (Core Models) · **Linear & Logistic Regression**: Fitting lines and probabilities, gradient descent, and reading coefficients carefully.  → glossary `glossary-src/ml-05.json`
- `ml/chapters/06-regularisation.html` · chapter 06 · **deep** · Part 2 (Core Models) · **Regularisation & the Bias-Variance Trade-off**: Why simpler models generalise, L1 and L2 penalties, and learning curves.  → glossary `glossary-src/ml-06.json`
- `ml/chapters/07-neighbours-bayes.html` · chapter 07 · **core** · Part 2 (Core Models) · **Nearest Neighbours, Naive Bayes & Kernels**: Similarity-based and probabilistic classifiers, and the kernel trick in one picture.  → glossary `glossary-src/ml-07.json`
- `ml/chapters/08-decision-trees.html` · chapter 08 · **deep** · Part 2 (Core Models) · **Decision Trees**: Splits, impurity, depth, and why a single tree is both readable and unstable.  → glossary `glossary-src/ml-08.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/ml-ch2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).