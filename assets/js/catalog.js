/* Single source of truth for every course on the site.
   The hub, sidebars, prev/next pagers, roadmaps, cross-links and progress
   tracking are all built from this file. Each course lives in its own folder
   (course.dir) with chapters/, labs/, cases/ and studios/ inside.

   To add a page: add an entry to the right course array, then create
   <course.dir>/<kind folder>/<file> with the matching data-* attribute on <body>.
   depth: "deep" | "core" | "intro". related: ids in this course ("05") or
   another course ("ret:13"). Studios are interview-style design exercises. */

(function () {
  /* =====================================================================
     Zero to AI Systems: courses A0 to A8. course.track = "ai" and course.num
     gives the label ("A0").
     ===================================================================== */

  /* ---------- A0: Math & Code for Machine Learning ---------- */
  var MLF_PARTS = [
    { title: "Orientation",            blurb: "What an AI systems engineer does, and the map of the path." },
    { title: "Python for ML & Program Search", blurb: "Arrays, tidy data and experiments you can rerun, then functions, objects and programs as data: the Python an evolution loop is made of." },
    { title: "Linear Algebra",         blurb: "Vectors, matrices and decompositions: the language every model is written in." },
    { title: "Calculus & Optimisation", blurb: "Derivatives, automatic differentiation and the optimisers that train every network." },
    { title: "Probability & Information", blurb: "Distributions, likelihood, entropy and the statistics that tell signal from noise." },
    { title: "Working Practice",       blurb: "Reading papers, paying for compute, writing things down and working with AI assistants." }
  ];
  var MLF_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "What AI systems engineers build, the nine courses, and how to use them without drowning." },
    { id: "01", part: 1, depth: "core",  file: "01-python-numerics.html",     title: "Python for Numerical Work",                blurb: "Numbers, lists and loops, why pure Python is slow for maths, and the idea of vectorising." },
    { id: "02", part: 1, depth: "deep",  file: "02-numpy-arrays.html",        title: "NumPy, Arrays & Broadcasting",             blurb: "Shapes, strides, axes and broadcasting: the mental model behind every tensor library." },
    { id: "03", part: 1, depth: "core",  file: "03-data-wrangling.html",      title: "Data Wrangling: pandas, SQL & Tidy Data",  blurb: "Loading, joining, grouping and cleaning tables, and the questions to ask any dataset." },
    { id: "04", part: 1, depth: "core",  file: "04-reproducible-experiments.html", title: "Reproducible Experiments",            blurb: "Environments, pinned versions, seeds, notebooks versus scripts and experiment logs." },
    { id: "20", part: 1, depth: "deep",  file: "20-functions-objects.html",   title: "Functions, Closures & Objects",            blurb: "Functions as values, closures, small classes and dataclasses, dunder methods and exceptions." },
    { id: "21", part: 1, depth: "deep",  file: "21-programs-as-data.html",    title: "Programs as Data",                         blurb: "Read Python source as a tree, change it, turn it back into code and run it with a step budget." },
    { id: "22", part: 1, depth: "core",  file: "22-running-candidates.html",  title: "Running Many Candidates Safely",           blurb: "Timeouts, separate processes, worker pools, caching by content hash and archives you can replay." },
    { id: "05", part: 2, depth: "deep",  file: "05-vectors-similarity.html",  title: "Vectors, Dot Products & Similarity",       blurb: "Vectors as arrows and as lists, length, angle, cosine similarity and projections." },
    { id: "06", part: 2, depth: "deep",  file: "06-matrices.html",            title: "Matrices as Functions",                    blurb: "Matrix multiplication as composing transformations, shapes as contracts, and inverses." },
    { id: "07", part: 2, depth: "deep",  file: "07-decompositions.html",      title: "Eigenvectors, SVD & Low Rank",             blurb: "Eigenvectors, the singular value decomposition and why low-rank structure is everywhere." },
    { id: "08", part: 3, depth: "deep",  file: "08-derivatives.html",         title: "Derivatives & the Chain Rule",             blurb: "Slopes, partial derivatives, gradients and the one rule that makes deep learning possible." },
    { id: "09", part: 3, depth: "deep",  file: "09-autodiff.html",            title: "Automatic Differentiation",                blurb: "Computation graphs, forward and reverse mode, and a tiny autograd engine built by hand." },
    { id: "10", part: 3, depth: "deep",  file: "10-optimisers.html",          title: "Gradient Descent & Optimisers",            blurb: "Learning rates, SGD, momentum, Adam and AdamW, schedules and what can go wrong." },
    { id: "11", part: 3, depth: "core",  file: "11-numerics.html",            title: "Floating Point & Numerical Stability",     blurb: "How floats work, overflow and underflow, stable softmax, and fp16, bf16 and fp8." },
    { id: "12", part: 4, depth: "deep",  file: "12-probability.html",         title: "Probability, Distributions & Sampling",    blurb: "Random variables, common distributions, expectation, Bayes' rule and sampling." },
    { id: "13", part: 4, depth: "deep",  file: "13-likelihood-losses.html",   title: "Maximum Likelihood & Loss Functions",      blurb: "Why squared error and cross-entropy are not arbitrary: they are likelihoods in disguise." },
    { id: "14", part: 4, depth: "deep",  file: "14-information-theory.html",  title: "Entropy, Cross-Entropy & KL Divergence",   blurb: "Surprise, bits, perplexity and the divergence that appears in every post-training method." },
    { id: "15", part: 4, depth: "deep",  file: "15-statistics.html",          title: "Statistics for Experiments",               blurb: "Confidence intervals, the bootstrap, hypothesis tests, power and the peeking trap." },
    { id: "16", part: 5, depth: "core",  file: "16-reading-papers.html",      title: "Reading Papers Efficiently",               blurb: "A three-pass method, what to skip, how to check claims and how to reproduce a result." },
    { id: "17", part: 5, depth: "core",  file: "17-compute-costs.html",       title: "GPUs, Clouds & What Compute Costs",        blurb: "What a GPU is good at, memory versus FLOPs, renting hardware and estimating a bill." },
    { id: "18", part: 5, depth: "core",  file: "18-technical-writing.html",   title: "Writing for Engineers",                    blurb: "Design docs, experiment reports and error-analysis memos that people actually read." },
    { id: "19", part: 5, depth: "intro", file: "19-ai-assistants.html",       title: "Learning with AI Assistants",              blurb: "Using coding assistants to go faster without outsourcing the understanding." }
  ];
  var MLF_LABS = [
    { id: "L1", file: "lab-01-linalg.html",     title: "A Small Linear Algebra Library",  afterPart: 2, related: ["05", "06", "07"], blurb: "Vectors, matrix multiply, transpose, Gram-Schmidt and power iteration, tested against hand values." },
    { id: "L2", file: "lab-02-autograd.html",   title: "Build an Autograd Engine",        afterPart: 3, related: ["08", "09"],       blurb: "A scalar Value class with reverse-mode autodiff, checked against numerical gradients." },
    { id: "L3", file: "lab-03-optimisers.html", title: "The Optimiser Race",              afterPart: 3, related: ["10", "11"],       blurb: "SGD, momentum, RMSProp, Adam and AdamW on classic test surfaces, with schedules and clipping." },
    { id: "L4", file: "lab-04-likelihood.html", title: "Sampling, Likelihood & Entropy",  afterPart: 4, related: ["12", "13", "14"], blurb: "Samplers, maximum-likelihood fits, stable log-softmax, temperature, entropy and KL." },
    { id: "L5", file: "lab-05-statistics.html", title: "A Statistics Toolkit for Experiments", afterPart: 4, related: ["15"],          blurb: "Bootstrap intervals, permutation tests, power by simulation and a demonstration of peeking." },
    { id: "L6", file: "lab-06-evolution-engine.html", title: "A Tiny Evolution Engine",     afterPart: 1, related: ["20", "21", "22"], blurb: "Mutate bin-packing heuristics as Python code, score them safely and keep an archive: evolution with no language model." }
  ];
  var MLF_CASES = [
    { id: "C1", file: "case-01-reinhart-rogoff.html", title: "A Spreadsheet Error That Shaped Policy", pattern: "Reproducible analysis", related: ["03", "04"], blurb: "An influential economics result that a student could not reproduce, and what the spreadsheet hid." },
    { id: "C2", file: "case-02-patriot-missile.html", title: "The Patriot Missile Clock",       pattern: "Floating-point drift",    related: ["11"],       blurb: "A tiny rounding error, accumulated over 100 hours of uptime, and a missed interception." },
    { id: "C3", file: "case-03-adamw.html",           title: "AdamW: Weight Decay Done Right",  pattern: "Optimiser details matter", related: ["10"],     blurb: "Why L2 regularisation and weight decay stop being the same thing inside Adam." },
    { id: "C4", file: "case-04-mixed-precision.html", title: "Mixed-Precision Training",        pattern: "Fewer bits, same model",  related: ["11", "17"], blurb: "Half-precision arithmetic, loss scaling and fp32 master weights: training in fewer bits without losing accuracy." },
    { id: "C5", file: "case-05-peeking.html",         title: "Peeking at A/B Tests",            pattern: "Valid stopping rules",    related: ["15"],       blurb: "Why checking a running experiment every day inflates false positives, and how sequential tests fix it." }
  ];
  var MLF_STUDIOS = [
    { id: "S1", file: "studio-01-experiment-design.html", title: "Design an Experiment That Can Fail", afterPart: 4, related: ["15", "04"], blurb: "Decide whether a change really helped: metric, sample size, stopping rule and what would change your mind." },
    { id: "S2", file: "studio-02-compute-budget.html",    title: "Budget the Compute for a Project",   afterPart: 5, related: ["17", "16"], blurb: "Turn a research plan into GPU-hours, memory, storage and a bill, with the risky assumptions named." }
  ];
  var MLF_TOOLS = [
    { id: "jupyter",  name: "Jupyter & notebooks",         chapters: ["01", "03", "04"],       blurb: "Interactive exploration, and the discipline that keeps notebooks reproducible." },
    { id: "numpy",    name: "NumPy",                       chapters: ["02", "05", "06", "07"], blurb: "The array library underneath almost every numerical Python tool." },
    { id: "pandas",   name: "pandas & DuckDB",             chapters: ["03"],                   blurb: "Tables in memory, and SQL over files without a server." },
    { id: "uv",       name: "uv & virtual environments",   chapters: ["04"],                   blurb: "Fast, pinned, reproducible Python environments." },
    { id: "plotting", name: "matplotlib",                  chapters: ["03", "12", "15"],       blurb: "Plots that answer a question, and the habit of looking at your data." },
    { id: "free-gpus", name: "Colab & Kaggle notebooks",   chapters: ["17"],                   blurb: "Free and cheap GPUs for learning, and their limits." },
    { id: "papers",   name: "arXiv, Semantic Scholar & Papers with Code", chapters: ["16"],     blurb: "Finding, tracking and checking papers and their code." }
  ];

  /* ---------- A1: Machine Learning & Data Science ---------- */
  var ML_PARTS = [
    { title: "Orientation",            blurb: "What it means for a machine to learn, and why most of the work is not modelling." },
    { title: "Framing Problems",       blurb: "Generalisation, metrics, exploratory analysis and baselines: deciding what to predict and how to judge it." },
    { title: "Core Models",            blurb: "Linear models, regularisation, neighbours, trees and boosted ensembles." },
    { title: "Unsupervised Learning",  blurb: "Finding structure without labels: clustering, projections and anomalies." },
    { title: "Validation & Trust",     blurb: "Cross-validation, leakage, imbalance, calibration and explanations: whether to believe the number." },
    { title: "Features & Competitions", blurb: "Feature engineering, time series, tabular foundation models and how competitions are won." },
    { title: "From Model to Value",    blurb: "Proving a model helps in the real world, and keeping it helpful." }
  ];
  var ML_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "Learning from examples, the data-science loop, and where this course fits." },
    { id: "01", part: 1, depth: "deep",  file: "01-generalisation.html",      title: "What Learning Is: Generalisation",         blurb: "Training, validation and test sets, overfitting, underfitting and the no-free-lunch idea." },
    { id: "02", part: 1, depth: "deep",  file: "02-framing-metrics.html",     title: "Framing Problems & Choosing Metrics",      blurb: "Turning a business question into a prediction task with a metric that matches the cost of errors." },
    { id: "03", part: 1, depth: "core",  file: "03-eda.html",                 title: "Exploratory Data Analysis",                blurb: "Distributions, missingness, duplicates, shifts between train and test, and the questions to ask first." },
    { id: "04", part: 1, depth: "core",  file: "04-baselines.html",           title: "Baselines First",                          blurb: "Majority class, simple rules and linear models: the numbers every fancy model must beat." },
    { id: "05", part: 2, depth: "deep",  file: "05-linear-models.html",       title: "Linear & Logistic Regression",             blurb: "Fitting lines and probabilities, gradient descent, and reading coefficients carefully." },
    { id: "06", part: 2, depth: "deep",  file: "06-regularisation.html",      title: "Regularisation & the Bias-Variance Trade-off", blurb: "Why simpler models generalise, L1 and L2 penalties, and learning curves." },
    { id: "07", part: 2, depth: "core",  file: "07-neighbours-bayes.html",    title: "Nearest Neighbours, Naive Bayes & Kernels", blurb: "Similarity-based and probabilistic classifiers, and the kernel trick in one picture." },
    { id: "08", part: 2, depth: "deep",  file: "08-decision-trees.html",      title: "Decision Trees",                           blurb: "Splits, impurity, depth, and why a single tree is both readable and unstable." },
    { id: "09", part: 2, depth: "deep",  file: "09-ensembles-boosting.html",  title: "Random Forests & Gradient Boosting",       blurb: "Bagging, boosting, XGBoost, LightGBM and CatBoost: why boosted trees rule tabular data." },
    { id: "10", part: 3, depth: "core",  file: "10-clustering.html",          title: "Clustering",                               blurb: "k-means, hierarchical clustering and DBSCAN, and how to tell whether clusters are real." },
    { id: "11", part: 3, depth: "core",  file: "11-dimensionality-reduction.html", title: "Dimensionality Reduction",             blurb: "PCA, t-SNE and UMAP: compressing and visualising high-dimensional data honestly." },
    { id: "12", part: 3, depth: "core",  file: "12-anomaly-detection.html",   title: "Anomaly Detection",                        blurb: "Statistical, distance-based and isolation methods for finding the rare and the strange." },
    { id: "13", part: 4, depth: "deep",  file: "13-cross-validation.html",    title: "Cross-Validation Done Right",              blurb: "k-fold, grouped, stratified and time-based splits that mirror how the model will be used." },
    { id: "14", part: 4, depth: "deep",  file: "14-leakage.html",             title: "Leakage: The Silent Killer",               blurb: "Target leakage, train-test contamination and preprocessing leaks, and how to hunt them." },
    { id: "15", part: 4, depth: "deep",  file: "15-imbalance-calibration.html", title: "Imbalance, Thresholds & Calibration",    blurb: "Rare positives, precision-recall trade-offs, choosing thresholds by cost, and calibrated probabilities." },
    { id: "16", part: 4, depth: "core",  file: "16-interpretability.html",    title: "Interpreting Models",                      blurb: "Permutation importance, partial dependence and SHAP, and what explanations cannot tell you." },
    { id: "17", part: 5, depth: "deep",  file: "17-feature-engineering.html", title: "Feature Engineering",                      blurb: "Encodings, aggregates, interactions, target encoding done safely, and features from domain knowledge." },
    { id: "18", part: 5, depth: "core",  file: "18-time-series.html",         title: "Time Series Forecasting",                  blurb: "Trend, seasonality, lag features, backtesting and the forecasting baselines that are hard to beat." },
    { id: "19", part: 5, depth: "intro", file: "19-tabular-deep-learning.html", title: "Tabular Deep Learning & Foundation Models", blurb: "Neural nets for tables, TabPFN-style foundation models, and when they beat boosted trees." },
    { id: "20", part: 5, depth: "core",  file: "20-competitions.html",        title: "How Competitions Are Won",                 blurb: "Validation strategy, diverse models, stacking and the habits competition winners describe." },
    { id: "21", part: 6, depth: "core",  file: "21-model-to-value.html",      title: "From Model to Value",                      blurb: "Offline metrics versus business outcomes, A/B tests, monitoring, drift and retraining." }
  ];
  var ML_LABS = [
    { id: "L1", file: "lab-01-linear-models.html",  title: "Linear & Logistic Regression from Scratch", afterPart: 2, related: ["05", "06"], blurb: "Closed form and gradient descent, L1 and L2 penalties, and log-loss, all checked against hand values." },
    { id: "L2", file: "lab-02-trees-boosting.html", title: "Trees & Gradient Boosting from Scratch",   afterPart: 2, related: ["08", "09"], blurb: "A CART tree, a random forest and a gradient-boosting regressor in plain Python." },
    { id: "L3", file: "lab-03-unsupervised.html",   title: "k-means, PCA & Anomalies",                 afterPart: 3, related: ["10", "11", "12"], blurb: "k-means++ with restarts, PCA by power iteration, and an isolation-style anomaly score." },
    { id: "L4", file: "lab-04-leakage-hunt.html",   title: "The Leakage Hunt",                         afterPart: 4, related: ["13", "14"], blurb: "Build a validation harness that catches four planted leaks, including one in preprocessing." },
    { id: "L5", file: "lab-05-calibration.html",    title: "Thresholds & Calibration",                 afterPart: 4, related: ["15"],       blurb: "PR curves, cost-based thresholds, reliability diagrams, Platt scaling and isotonic regression." },
    { id: "L6", file: "lab-06-features-stacking.html", title: "Feature Pipelines & Stacking",          afterPart: 5, related: ["17", "20"], blurb: "Leak-safe target encoding, out-of-fold predictions and a stacked ensemble that beats its parts." }
  ];
  var ML_CASES = [
    { id: "C1", file: "case-01-netflix-prize.html",    title: "The Netflix Prize",                      pattern: "Ensembles vs deployability",  related: ["09", "20", "21"], blurb: "A million-dollar ensemble that won the competition and was never fully deployed." },
    { id: "C2", file: "case-02-google-flu-trends.html", title: "Google Flu Trends",                     pattern: "Drift and spurious features", related: ["14", "21"],       blurb: "Search queries that predicted flu, until they did not, and what the post-mortems found." },
    { id: "C3", file: "case-03-zillow-offers.html",    title: "Zillow Offers",                          pattern: "Model risk in a business",    related: ["18", "21"],       blurb: "An algorithmic home-buying business that shut down after its price forecasts met a turning market." },
    { id: "C4", file: "case-04-amazon-recruiting.html", title: "A Recruiting Model That Learned Bias",  pattern: "Biased labels",               related: ["02", "16"],       blurb: "A CV-screening model trained on past hiring decisions, and why removing words did not fix it." },
    { id: "C5", file: "case-05-xgboost.html",          title: "XGBoost: A System, Not Just an Algorithm", pattern: "Engineering wins benchmarks", related: ["09"],           blurb: "Sparsity-aware splits, cache-aware blocks and out-of-core training behind a competition favourite." },
    { id: "C6", file: "case-06-competition-leaks.html", title: "Leaks That Won Competitions",           pattern: "Leakage",                     related: ["14", "20"],       blurb: "Row orders, IDs and timestamps that gave away the answer, and how organisers learned to prevent them." },
    { id: "C7", file: "case-07-compas.html",           title: "COMPAS and Competing Definitions of Fair", pattern: "Calibration vs error balance", related: ["15", "16"],    blurb: "A risk score that was calibrated and still unequal in its errors, and why both sides were right." }
  ];
  var ML_STUDIOS = [
    { id: "S1", file: "studio-01-churn.html",       title: "Frame a Churn Prediction Problem",      afterPart: 1, related: ["02", "03", "04"], blurb: "From 'reduce churn' to a target, a prediction window, a metric, a baseline and an action." },
    { id: "S2", file: "studio-02-fraud.html",       title: "Design a Fraud Detection Model",        afterPart: 4, related: ["13", "14", "15"], blurb: "Rare positives, delayed labels, adversaries and a review queue with limited capacity." },
    { id: "S3", file: "studio-03-forecasting.html", title: "Design Demand Forecasting for a Retailer", afterPart: 5, related: ["17", "18"], blurb: "Thousands of products, promotions, stockouts and the decision the forecast feeds." }
  ];
  var ML_TOOLS = [
    { id: "sklearn",  name: "scikit-learn",                 chapters: ["04", "05", "06", "07", "10", "11", "13"], blurb: "The reference library for classical ML, with a consistent fit/predict interface." },
    { id: "gbdt",     name: "XGBoost, LightGBM & CatBoost", chapters: ["09", "17", "20"],             blurb: "The three boosted-tree libraries that dominate tabular problems." },
    { id: "shap",     name: "SHAP",                         chapters: ["16"],                         blurb: "Per-prediction feature attributions, and plots to read them with care." },
    { id: "tracking", name: "MLflow & Weights & Biases",    chapters: ["13", "21"],                   blurb: "Log every run's parameters, metrics and artefacts so results can be compared and reproduced." },
    { id: "kaggle",   name: "Kaggle",                       chapters: ["20"],                         blurb: "Competitions, datasets, notebooks with free GPUs, and the forums where winners explain themselves." },
    { id: "evidently", name: "Drift monitoring tools",      chapters: ["21"],                         blurb: "Compare live data with training data and alert on shifts." }
  ];

  /* ---------- A2: Deep Learning & Transformers from Scratch ---------- */
  var DL_PARTS = [
    { title: "Orientation",              blurb: "From a single neuron to a language model, and how this course builds one." },
    { title: "Neural Networks",          blurb: "Layers, backpropagation, training dynamics and the tools that make deep nets train." },
    { title: "Representation",           blurb: "Embeddings, convolutions and recurrence: how networks represent words, images and sequences." },
    { title: "Attention & the Transformer", blurb: "Attention from first principles, the Transformer block, positions and a GPT built by hand." },
    { title: "Tokens & Language Modelling", blurb: "Tokenisers, the next-token objective and the decoding strategies that turn probabilities into text." },
    { title: "Training at Scale",        blurb: "Counting parameters, FLOPs and memory, keeping training stable, and the laws of scale." },
    { title: "Modern Architectures",     blurb: "Efficient attention, mixture of experts, vision-language models and alternatives to attention." }
  ];
  var DL_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "What deep learning is, what changed in 2012 and 2017, and the road to building a GPT." },
    { id: "01", part: 1, depth: "deep",  file: "01-neurons-layers.html",      title: "Neurons, Layers & Activations",            blurb: "Weighted sums, non-linearities, layers and why depth helps." },
    { id: "02", part: 1, depth: "deep",  file: "02-backpropagation.html",     title: "Backpropagation Through a Network",        blurb: "The chain rule applied to whole layers: matrix gradients, by hand and in code." },
    { id: "03", part: 1, depth: "deep",  file: "03-training-dynamics.html",   title: "Initialisation, Normalisation & Residuals", blurb: "Vanishing and exploding signals, careful initialisation, LayerNorm and skip connections." },
    { id: "04", part: 1, depth: "core",  file: "04-deep-regularisation.html", title: "Regularising Deep Networks",               blurb: "Weight decay, dropout, data augmentation, early stopping and the strange case of double descent." },
    { id: "05", part: 1, depth: "core",  file: "05-pytorch.html",             title: "PyTorch as an Autodiff Engine",            blurb: "Tensors, autograd, modules, optimisers and the standard training loop." },
    { id: "06", part: 2, depth: "deep",  file: "06-embeddings.html",          title: "Embeddings: Words as Vectors",             blurb: "One-hot to dense vectors, word2vec, and why meaning becomes geometry." },
    { id: "07", part: 2, depth: "core",  file: "07-convolutions.html",        title: "Convolutions & Images",                    blurb: "Filters, weight sharing, pooling and the ideas from vision that carried over." },
    { id: "08", part: 2, depth: "core",  file: "08-sequences-rnns.html",      title: "Sequences & Recurrent Networks",           blurb: "RNNs and LSTMs, the bottleneck of a single hidden state, and why they gave way to attention." },
    { id: "09", part: 3, depth: "deep",  file: "09-attention.html",           title: "Attention from First Principles",          blurb: "Queries, keys and values, scaled dot products, softmax weights, masking and multiple heads." },
    { id: "10", part: 3, depth: "deep",  file: "10-transformer-block.html",   title: "The Transformer Block",                    blurb: "Attention, MLPs, residual streams and normalisation, assembled and explained." },
    { id: "11", part: 3, depth: "core",  file: "11-positions.html",           title: "Positional Information",                   blurb: "Why attention needs positions: learned, sinusoidal, relative and rotary (RoPE) encodings." },
    { id: "12", part: 3, depth: "deep",  file: "12-building-gpt.html",        title: "Building a GPT",                           blurb: "A decoder-only Transformer, end to end, trained on characters and read line by line." },
    { id: "13", part: 4, depth: "deep",  file: "13-tokenisation.html",        title: "Tokenisation",                             blurb: "Characters, bytes and byte-pair encoding, vocabulary size, and the bugs tokenisers cause." },
    { id: "14", part: 4, depth: "deep",  file: "14-language-modelling.html",  title: "The Language-Modelling Objective",         blurb: "Next-token prediction, cross-entropy, perplexity and what a model learns from it." },
    { id: "15", part: 4, depth: "core",  file: "15-decoding.html",            title: "Decoding Strategies",                      blurb: "Greedy, temperature, top-k, top-p, beam search and constrained decoding." },
    { id: "16", part: 5, depth: "deep",  file: "16-resource-accounting.html", title: "Parameters, FLOPs & Memory",               blurb: "Counting a model's parameters, the 6ND rule, activation memory and what fits on a GPU." },
    { id: "17", part: 5, depth: "core",  file: "17-training-stability.html",  title: "Mixed Precision & Training Stability",     blurb: "bf16 training, loss spikes, gradient clipping, learning-rate warmup and what logs to watch." },
    { id: "18", part: 5, depth: "core",  file: "18-scaling-laws.html",        title: "Scaling Laws",                             blurb: "Loss as a power law of compute, data and parameters, and the compute-optimal recipe." },
    { id: "19", part: 6, depth: "core",  file: "19-efficient-attention.html", title: "Efficient Attention",                      blurb: "Multi-query and grouped-query attention, sliding windows and FlashAttention's memory trick." },
    { id: "20", part: 6, depth: "intro", file: "20-mixture-of-experts.html",  title: "Mixture of Experts",                       blurb: "Routing tokens to a few of many experts: more parameters for the same compute, and the catches." },
    { id: "21", part: 6, depth: "core",  file: "21-vision-language.html",     title: "Vision-Language Models",                   blurb: "Patches, image encoders, projectors and how a language model learns to read a picture." },
    { id: "22", part: 6, depth: "intro", file: "22-beyond-attention.html",    title: "Beyond Attention",                         blurb: "State-space models, linear attention and hybrids, and what they trade away." }
  ];
  var DL_LABS = [
    { id: "L1", file: "lab-01-mlp.html",          title: "A Neural Network from Scratch",     afterPart: 1, related: ["01", "02", "03"], blurb: "Matrix ops, a two-layer network, backprop by hand and a training loop on a toy dataset." },
    { id: "L2", file: "lab-02-embeddings.html",   title: "Word Embeddings",                   afterPart: 2, related: ["06"],             blurb: "Skip-gram with negative sampling on a small corpus, then nearest neighbours and analogies." },
    { id: "L3", file: "lab-03-attention.html",    title: "Attention & a Transformer Block",   afterPart: 3, related: ["09", "10", "11"], blurb: "Scaled dot-product attention, causal masks, multi-head attention and a block, checked shape by shape." },
    { id: "L4", file: "lab-04-tiny-gpt.html",     title: "Train a Tiny GPT",                  afterPart: 3, related: ["12", "14"],       blurb: "A character-level GPT in pure Python, trained until it invents plausible names." },
    { id: "L5", file: "lab-05-tokeniser.html",    title: "A BPE Tokeniser & Decoders",        afterPart: 4, related: ["13", "15"],       blurb: "Train byte-pair encoding, round-trip any text, then implement greedy, top-k and top-p sampling." },
    { id: "L6", file: "lab-06-resources.html",    title: "The Model Resource Calculator",     afterPart: 5, related: ["16", "18"],       blurb: "Parameters, FLOPs, memory and compute-optimal sizes for real published models." }
  ];
  var DL_CASES = [
    { id: "C1", file: "case-01-alexnet.html",         title: "AlexNet and ImageNet, 2012",          pattern: "Data + compute + method",   related: ["07", "04"], blurb: "Two GPUs, a big labelled dataset and ReLUs: the result that restarted neural networks." },
    { id: "C2", file: "case-02-transformer.html",     title: "Attention Is All You Need",           pattern: "Parallel sequence models",  related: ["09", "10"], blurb: "The 2017 translation paper whose architecture became the foundation of modern large language models." },
    { id: "C3", file: "case-03-gpt-scaling.html",     title: "From GPT-2 to GPT-3",                 pattern: "Scale changes behaviour",   related: ["14", "18"], blurb: "A language model that learned tasks nobody trained it for, and the in-context learning surprise." },
    { id: "C4", file: "case-04-chinchilla.html",      title: "Chinchilla: Compute-Optimal Training", pattern: "Balance data and size",    related: ["16", "18"], blurb: "Why a smaller model trained on more tokens beat a model four times its size." },
    { id: "C5", file: "case-05-flashattention.html",  title: "FlashAttention",                      pattern: "IO-aware algorithms",       related: ["19"], blurb: "Same maths, far less memory traffic: an exact attention kernel that changed context lengths." },
    { id: "C6", file: "case-06-glitch-tokens.html",   title: "SolidGoldMagikarp: Glitch Tokens",    pattern: "Tokeniser-model mismatch",  related: ["13"],       blurb: "Tokens that existed in the vocabulary but almost never in training, and the odd behaviour they caused." },
    { id: "C7", file: "case-07-opt-logbook.html",     title: "Training OPT-175B: The Logbook",      pattern: "Operating a training run",  related: ["17"],       blurb: "A public diary of restarts, loss spikes and hardware failures in a large training run." }
  ];
  var DL_STUDIOS = [
    { id: "S1", file: "studio-01-debug-training.html", title: "Debug a Training Run That Will Not Learn", afterPart: 5, related: ["03", "17"], blurb: "Flat loss, then a spike, then NaNs: find the causes in order, with the evidence for each." },
    { id: "S2", file: "studio-02-small-model-plan.html", title: "Plan a Small Model on a Budget",       afterPart: 6, related: ["16", "18", "19"], blurb: "Pick size, tokens, context length and architecture for a domain model with a fixed GPU budget." }
  ];
  var DL_TOOLS = [
    { id: "pytorch",  name: "PyTorch",                       chapters: ["05", "12"],             blurb: "The deep-learning framework this course's chapters use, from tensors to training loops." },
    { id: "nanogpt",  name: "nanoGPT, nanochat & minGPT",    chapters: ["12", "14", "16"],       blurb: "Karpathy's small, readable GPT implementations to train and modify." },
    { id: "tokenisers", name: "Tokeniser playgrounds",      chapters: ["13"],                   blurb: "See exactly how text becomes tokens, and compare tokenisers side by side." },
    { id: "tensorboard", name: "TensorBoard & W&B",         chapters: ["03", "17"],             blurb: "Watch loss, gradients and activations while a model trains." },
    { id: "profiler", name: "PyTorch profiler",              chapters: ["16", "19"],             blurb: "Find where the time and memory of a training step actually go." },
    { id: "colab",    name: "Free GPU notebooks",            chapters: ["05", "12"],             blurb: "Run the chapters' PyTorch code on a free GPU when your laptop is too slow." }
  ];

  /* ---------- A3: Training, Post-training & Serving LLMs ---------- */
  var LLM_PARTS = [
    { title: "Orientation",            blurb: "The life of a model: pretraining, post-training, serving and judging." },
    { title: "Pretraining Systems",    blurb: "Data pipelines, GPU memory, parallelism, kernels and keeping long runs alive." },
    { title: "Reinforcement Learning Foundations", blurb: "Bandits, MDPs, policy gradients and PPO: the RL a post-training engineer needs." },
    { title: "Post-training",          blurb: "Fine-tuning, LoRA, preference optimisation, reward models, RL with verifiable rewards and distillation." },
    { title: "Cheap Adaptation",       blurb: "Changing a model without full training: merging, evolution and adapters generated on demand." },
    { title: "Inference",              blurb: "The KV cache, quantisation, serving engines, speculative decoding and the economics of a token." },
    { title: "Judging Models",         blurb: "Did training help? Held-out evaluation for models you trained yourself." }
  ];
  var LLM_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "Base models, chat models and reasoning models, and the stages that make each." },
    { id: "01", part: 1, depth: "deep",  file: "01-pretraining-data.html",    title: "Pretraining Data",                         blurb: "Crawling, extracting, filtering, deduplicating and mixing trillions of tokens." },
    { id: "02", part: 1, depth: "deep",  file: "02-gpu-memory.html",          title: "GPU Memory & Why Training Runs Out of It", blurb: "Weights, gradients, optimiser state and activations, and the tricks that trade compute for memory." },
    { id: "03", part: 1, depth: "core",  file: "03-parallelism.html",         title: "Parallel Training",                        blurb: "Data, tensor, pipeline and sequence parallelism, ZeRO and FSDP, and the communication each costs." },
    { id: "04", part: 1, depth: "intro", file: "04-kernels.html",             title: "Kernels & Performance",                    blurb: "Why a fused kernel beats three small ones, and a first look at Triton." },
    { id: "05", part: 1, depth: "core",  file: "05-long-runs.html",           title: "Checkpoints, Failures & Long Runs",        blurb: "Hardware failures, checkpointing, restarts and monitoring a run that lasts for weeks." },
    { id: "06", part: 2, depth: "core",  file: "06-bandits-mdps.html",        title: "Bandits & Markov Decision Processes",      blurb: "Rewards, exploration versus exploitation, states, actions, returns and discounting." },
    { id: "07", part: 2, depth: "deep",  file: "07-policy-gradients.html",    title: "Policy Gradients",                         blurb: "REINFORCE derived step by step, baselines and why variance is the enemy." },
    { id: "08", part: 2, depth: "deep",  file: "08-ppo.html",                 title: "PPO & KL Penalties",                       blurb: "Clipped objectives, trust regions and the KL leash that keeps a fine-tuned model sane." },
    { id: "09", part: 2, depth: "core",  file: "09-value-functions.html",     title: "Value Functions & Advantage",              blurb: "Critics, temporal-difference learning and generalised advantage estimation." },
    { id: "10", part: 3, depth: "deep",  file: "10-sft.html",                 title: "Supervised Fine-Tuning",                   blurb: "Instruction data, chat templates, loss masking, data quality and catastrophic forgetting." },
    { id: "11", part: 3, depth: "deep",  file: "11-lora.html",                title: "LoRA, QLoRA & Parameter-Efficient Tuning", blurb: "Low-rank updates, why they work, rank and alpha, and fine-tuning in 4-bit." },
    { id: "12", part: 3, depth: "deep",  file: "12-preference-optimisation.html", title: "Preference Optimisation: RLHF & DPO",  blurb: "Learning from comparisons: the RLHF pipeline, the DPO derivation and their relatives." },
    { id: "13", part: 3, depth: "core",  file: "13-reward-models.html",       title: "Reward Models & Reward Hacking",           blurb: "Training reward models, over-optimisation, sycophancy and Goodhart's law in practice." },
    { id: "14", part: 3, depth: "deep",  file: "14-rlvr-grpo.html",           title: "RL with Verifiable Rewards & GRPO",        blurb: "Checkable rewards, group-relative advantages and how reasoning models are trained." },
    { id: "15", part: 3, depth: "core",  file: "15-distillation.html",        title: "Distillation & Synthetic Data",            blurb: "Teaching small models with big ones, logit distillation, synthetic data and model collapse." },
    { id: "16", part: 4, depth: "core",  file: "16-model-merging.html",       title: "Model Merging & Evolutionary Merging",     blurb: "Averaging weights, task vectors, TIES and DARE, and searching for merge recipes by evolution." },
    { id: "17", part: 4, depth: "intro", file: "17-adapters-on-demand.html",  title: "Adapters on Demand",                       blurb: "Self-adaptive models and hypernetworks that generate adapters from a task description." },
    { id: "18", part: 5, depth: "deep",  file: "18-kv-cache.html",            title: "The KV Cache & the Cost of Decoding",      blurb: "Prefill versus decode, why generation is memory-bound, and what the cache costs." },
    { id: "19", part: 5, depth: "core",  file: "19-quantisation.html",        title: "Quantisation",                             blurb: "int8, int4 and fp8, per-channel scales, outliers, GPTQ and AWQ, and measuring the damage." },
    { id: "20", part: 5, depth: "deep",  file: "20-serving-engines.html",     title: "Serving Engines",                          blurb: "Continuous batching, paged attention, prefix caching and how vLLM and SGLang work." },
    { id: "21", part: 5, depth: "intro", file: "21-speculative-decoding.html", title: "Speculative Decoding & Other Speedups",   blurb: "Draft and verify, Medusa-style heads, and why the output is unchanged." },
    { id: "22", part: 5, depth: "core",  file: "22-token-economics.html",     title: "The Economics of a Token",                 blurb: "Throughput, latency, batch size and price: what a million tokens costs to serve." },
    { id: "23", part: 6, depth: "core",  file: "23-evaluating-models.html",   title: "Evaluating a Model You Trained",           blurb: "Held-out sets, evaluation harnesses, contamination checks and regressions on other skills." }
  ];
  var LLM_LABS = [
    { id: "L1", file: "lab-01-data-pipeline.html", title: "A Pretraining Data Pipeline",       afterPart: 1, related: ["01"],             blurb: "Extract, filter by quality heuristics and deduplicate with MinHash and locality-sensitive hashing." },
    { id: "L2", file: "lab-02-policy-gradient.html", title: "Policy Gradients & PPO",          afterPart: 2, related: ["06", "07", "08"], blurb: "REINFORCE with a baseline, then PPO's clipped objective with a KL penalty, on bandits and a gridworld." },
    { id: "L3", file: "lab-03-lora.html",           title: "LoRA from Scratch",                afterPart: 3, related: ["11"],             blurb: "Freeze a small model, train low-rank adapters, merge them back and compare parameter counts." },
    { id: "L4", file: "lab-04-dpo-grpo.html",       title: "DPO & GRPO on a Toy Policy",       afterPart: 3, related: ["12", "14"],       blurb: "Implement both losses on a policy over answers to arithmetic questions with a verifiable reward." },
    { id: "L5", file: "lab-05-evolutionary-merge.html", title: "Evolutionary Model Merging",   afterPart: 4, related: ["16"],             blurb: "Merge task-specialised small models and evolve merge coefficients against a held-out task." },
    { id: "L6", file: "lab-06-serving-sim.html",    title: "A Serving Simulator",              afterPart: 5, related: ["18", "20", "22"], blurb: "Simulate static and continuous batching with a paged KV cache, and measure throughput and latency." },
    { id: "L7", file: "lab-07-quantisation.html",   title: "Quantise a Model",                 afterPart: 5, related: ["19"],             blurb: "Symmetric and asymmetric int8 and int4, per-channel scales and outlier handling, with error measured." }
  ];
  var LLM_CASES = [
    { id: "C1", file: "case-01-instructgpt.html",   title: "InstructGPT: RLHF in Practice",     pattern: "Learning from human preferences", related: ["10", "12"], blurb: "A smaller model that labellers preferred to one a hundred times larger." },
    { id: "C2", file: "case-02-deepseek-r1.html",   title: "DeepSeek-R1",                       pattern: "RL with verifiable rewards",      related: ["14", "15"], blurb: "Reasoning that emerged from reinforcement learning on checkable problems, then distilled into small models." },
    { id: "C3", file: "case-03-llama3-training.html", title: "Training Llama 3 at Scale",       pattern: "Reliability of training clusters", related: ["03", "05"], blurb: "Thousands of GPUs, hundreds of interruptions and the engineering that kept the run on track." },
    { id: "C4", file: "case-04-vllm.html",          title: "vLLM and PagedAttention",           pattern: "Virtual memory for the KV cache", related: ["18", "20"], blurb: "Borrowing operating-system paging to stop wasting most of a GPU's cache memory." },
    { id: "C5", file: "case-05-evolutionary-merge.html", title: "Evolving Model Merges",        pattern: "Search over recipes",             related: ["16"],       blurb: "Evolutionary search that combined existing open models into new capabilities without gradient training." },
    { id: "C6", file: "case-06-sycophancy-rollback.html", title: "The Sycophancy Rollback",     pattern: "Reward signals with side effects", related: ["13"],      blurb: "A model update that became too eager to please, and what its developer said went wrong." },
    { id: "C7", file: "case-07-alpaca.html",        title: "Alpaca & Self-Instruct",            pattern: "Distillation from a stronger model", related: ["15", "10"], blurb: "Fifty-two thousand generated instructions, a few hundred dollars and a lesson about imitation." }
  ];
  var LLM_STUDIOS = [
    { id: "S1", file: "studio-01-domain-adaptation.html", title: "Adapt a Model for a Specialist Domain", afterPart: 3, related: ["10", "11", "23"], blurb: "Prompting, retrieval, fine-tuning or all three, under a fixed budget, with the evaluation that decides." },
    { id: "S2", file: "studio-02-reasoning-model.html",  title: "Post-train a Small Reasoning Model",    afterPart: 3, related: ["14", "15"], blurb: "Pick the base model, reward, data and compute, and plan how you will catch reward hacking." },
    { id: "S3", file: "studio-03-serving-platform.html", title: "Design an LLM Serving Platform",        afterPart: 5, related: ["18", "20", "22"], blurb: "Many models, many tenants, latency targets and a GPU bill: batching, routing, caching and autoscaling." }
  ];
  var LLM_TOOLS = [
    { id: "hf",      name: "Hugging Face transformers, TRL & PEFT", chapters: ["10", "11", "12", "14"], blurb: "Load models, fine-tune with LoRA and run SFT, DPO and GRPO trainers." },
    { id: "unsloth", name: "Unsloth",                        chapters: ["11", "14"],             blurb: "Memory-efficient fine-tuning and RL that fits on a single consumer or free GPU." },
    { id: "vllm",    name: "vLLM & SGLang",                  chapters: ["18", "20", "22"],       blurb: "High-throughput open-source serving engines." },
    { id: "llamacpp", name: "llama.cpp & Ollama",            chapters: ["19"],                   blurb: "Run quantised models locally on a laptop CPU or GPU." },
    { id: "lm-eval", name: "lm-evaluation-harness",          chapters: ["23"],                   blurb: "Run standard benchmarks on any model the same way every time." },
    { id: "nvidia-smi", name: "nvidia-smi & nvtop",          chapters: ["02", "05"],             blurb: "See GPU memory, utilisation and temperature while something runs." }
  ];

  /* ---------- A4: Agents, Tools & Protocols ---------- */
  var AGT_PARTS = [
    { title: "Orientation",            blurb: "What an agent is, what it is not, and the simplest thing that could work." },
    { title: "The Loop",               blurb: "Messages, structured output, tool calls and reasoning: the loop every agent runs." },
    { title: "Tools & Protocols",      blurb: "Designing tools, function calling across providers, MCP from the wire up and agent-to-agent protocols." },
    { title: "Context & Memory",       blurb: "What goes into the context window, what stays out, and how agents remember." },
    { title: "Workflows & Teams",      blurb: "Workflow patterns, multi-agent systems and durable execution for agents that run for hours." },
    { title: "Foundational Agents",    blurb: "How deep-research, computer-use and coding agents are built." },
    { title: "Security & Engineering", blurb: "Prompt injection, sandboxes, frameworks and working well with AI coding tools." }
  ];
  var AGT_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "Workflows versus agents, why agents fail, and the shape of this course." },
    { id: "01", part: 1, depth: "core",  file: "01-model-apis.html",          title: "Talking to a Model",                       blurb: "Messages and roles, system prompts, parameters, streaming and structured output." },
    { id: "02", part: 1, depth: "deep",  file: "02-tool-loop.html",           title: "Tool Calling: The Agent Loop",             blurb: "Tool definitions, tool_use and tool_result turns, stop conditions and iteration budgets." },
    { id: "03", part: 1, depth: "core",  file: "03-reasoning-planning.html",  title: "Reasoning, ReAct & Planning",              blurb: "Thought-action-observation, plan-then-execute, reflection and what reasoning models change." },
    { id: "04", part: 1, depth: "core",  file: "04-prompting.html",           title: "Prompting as Programming",                 blurb: "Clear instructions, examples, delimiters and prompts you can test, version and review." },
    { id: "05", part: 2, depth: "deep",  file: "05-tool-design.html",         title: "Designing Tools for Agents",               blurb: "The agent-computer interface: names, descriptions, arguments, errors and output size." },
    { id: "06", part: 2, depth: "core",  file: "06-function-calling.html",    title: "Function Calling Across Providers",        blurb: "JSON Schema contracts, parallel calls, forced tools and a provider-neutral adapter." },
    { id: "07", part: 2, depth: "deep",  file: "07-mcp.html",                 title: "MCP from the Wire Up",                     blurb: "JSON-RPC messages, tools, resources and prompts, and a server written by hand." },
    { id: "08", part: 2, depth: "core",  file: "08-mcp-production.html",      title: "MCP in Production",                        blurb: "Transports, authorisation, versions and the stateless redesign, and how to survive spec changes." },
    { id: "09", part: 2, depth: "core",  file: "09-agent-to-agent.html",      title: "Agent-to-Agent Protocols",                 blurb: "Agent cards, tasks and delegation with A2A, and when agents should talk to agents at all." },
    { id: "10", part: 3, depth: "deep",  file: "10-context-engineering.html", title: "Context Engineering",                      blurb: "Context as a budget: selection, compaction, just-in-time retrieval and context rot." },
    { id: "11", part: 3, depth: "core",  file: "11-memory.html",              title: "Memory: Notes, Retrieval & Skills",        blurb: "Scratchpads, notes files, episodic and semantic memory, and libraries of reusable skills." },
    { id: "12", part: 3, depth: "core",  file: "12-long-context.html",        title: "Long Context versus Retrieval",            blurb: "When to put everything in the window, when to retrieve, and how to measure the difference." },
    { id: "13", part: 4, depth: "deep",  file: "13-workflow-patterns.html",   title: "Workflow Patterns",                        blurb: "Chaining, routing, parallelising, orchestrator-workers and evaluator-optimiser loops as plain code." },
    { id: "14", part: 4, depth: "deep",  file: "14-multi-agent.html",         title: "Multi-Agent Systems",                      blurb: "Orchestrators and sub-agents, token costs, coordination failures and when one agent is better." },
    { id: "15", part: 4, depth: "deep",  file: "15-durable-execution.html",   title: "Durable Execution for Agents",             blurb: "Event logs, checkpoints, idempotent side effects, resumption and human approval gates." },
    { id: "16", part: 5, depth: "deep",  file: "16-deep-research.html",       title: "Deep Research Agents",                     blurb: "Planning, parallel search, reading, cross-checking, citing and synthesising a long report." },
    { id: "17", part: 5, depth: "deep",  file: "17-computer-use.html",        title: "Computer-Use & Browser Agents",            blurb: "Screenshots versus accessibility trees, coordinates, actions, verification and safety." },
    { id: "18", part: 5, depth: "core",  file: "18-coding-agents.html",       title: "Coding Agents",                            blurb: "How SWE-agent, OpenHands and terminal coding agents read, edit, run and test code." },
    { id: "19", part: 6, depth: "deep",  file: "19-agent-security.html",      title: "Agent Security",                           blurb: "Prompt injection, tool poisoning, data exfiltration and the lethal trifecta." },
    { id: "20", part: 6, depth: "core",  file: "20-sandboxing.html",          title: "Sandboxes & Permissions",                  blurb: "Containers, virtual machines, network allow-lists, least privilege and confirmation prompts." },
    { id: "21", part: 6, depth: "core",  file: "21-frameworks.html",          title: "Agent Frameworks",                         blurb: "What frameworks give you, what they hide, and how to choose one you can leave." },
    { id: "22", part: 6, depth: "deep",  file: "22-ai-coding-tools.html",     title: "Working with AI Coding Tools",             blurb: "Instruction files, plans, verification loops, review and measuring whether it actually helps." }
  ];
  var AGT_LABS = [
    { id: "L1", file: "lab-01-agent-loop.html",     title: "The Agent Loop from Scratch",       afterPart: 1, related: ["01", "02", "03"], blurb: "Messages, tool schemas and a tool-calling loop with budgets, logging and a scripted fake model." },
    { id: "L2", file: "lab-02-tool-design.html",    title: "Tool Design, Measured",             afterPart: 2, related: ["05", "06"],       blurb: "Two designs of the same toolset, a twenty-task evaluation and the numbers that pick the winner." },
    { id: "L3", file: "lab-03-mcp.html",            title: "An MCP Server & Client",            afterPart: 2, related: ["07", "08"],       blurb: "JSON-RPC over stdio: initialise, list and call tools, resources and errors, both sides by hand." },
    { id: "L4", file: "lab-04-workflows.html",      title: "Workflow Patterns & Budgets",       afterPart: 4, related: ["13", "14"],       blurb: "Chains, routers, parallel fan-out and orchestrator-workers, with token accounting for each." },
    { id: "L5", file: "lab-05-durable-agent.html",  title: "A Durable Agent",                   afterPart: 4, related: ["15"],  blurb: "An event-sourced agent that survives being killed mid-task without repeating side effects." },
    { id: "L6", file: "lab-06-deep-research.html",  title: "A Mini Deep-Research Agent",        afterPart: 5, related: ["16", "10"],       blurb: "Plan, search a local corpus, read, cite and verify every claim against its source." },
    { id: "L7", file: "lab-07-injection.html",      title: "Attack & Defend a Tool-Using Agent", afterPart: 6, related: ["19", "20"],      blurb: "Plant injections in documents and tool output, then measure which defences actually hold." }
  ];
  var AGT_CASES = [
    { id: "C1", file: "case-01-multi-agent-research.html", title: "A Multi-Agent Research System", pattern: "Orchestrator-workers",      related: ["14", "16"], blurb: "Anthropic's write-up of a lead agent spawning researchers, and what token usage explained." },
    { id: "C2", file: "case-02-swe-agent.html",     title: "SWE-agent and the Agent-Computer Interface", pattern: "Tools shaped for models", related: ["05", "18"], blurb: "Why a purpose-built file viewer and editor beat a raw shell for a coding agent." },
    { id: "C3", file: "case-03-metr-rct.html",      title: "Measuring AI Coding Productivity",  pattern: "Measure, don't assume",        related: ["22"],       blurb: "A randomised trial in which experienced developers were slower with AI and believed they were faster." },
    { id: "C4", file: "case-04-mcp-evolution.html", title: "How MCP Changed, 2024 to 2026",     pattern: "Protocols evolve",             related: ["07", "08"], blurb: "From a local stdio protocol to remote servers, OAuth and a stateless redesign." },
    { id: "C5", file: "case-05-injection-wild.html", title: "Prompt Injection in the Wild",     pattern: "Untrusted input as instructions", related: ["19"],    blurb: "Exfiltration through assistants and MCP servers: real incidents and the common thread." },
    { id: "C6", file: "case-06-replit-database.html", title: "The Agent That Deleted Production", pattern: "Least privilege for agents", related: ["20", "15"], blurb: "A coding agent with production access, a code freeze it ignored, and the safeguards added afterwards." },
    { id: "C7", file: "case-07-computer-use.html",  title: "Teaching Models to Use Computers",  pattern: "Pixels as an interface",      related: ["17"],       blurb: "Screenshot-driven agents, the OSWorld benchmark and why progress is measured in steps." }
  ];
  var AGT_STUDIOS = [
    { id: "S1", file: "studio-01-support-agent.html",  title: "Design a Customer-Support Agent", afterPart: 4, related: ["13", "15", "05"], blurb: "Answers, account lookups and refunds with limits, escalation to humans and an audit trail." },
    { id: "S2", file: "studio-02-research-product.html", title: "Design a Deep-Research Product", afterPart: 5, related: ["14", "16"],     blurb: "Long-running research jobs with citations, cost controls, progress updates and quality checks." },
    { id: "S3", file: "studio-03-regulated-agent.html", title: "Design an Agent for a Regulated Back Office", afterPart: 6, related: ["19", "20", "15"], blurb: "Documents in, decisions out, with a threat model, approvals and evidence an auditor accepts." }
  ];
  var AGT_TOOLS = [
    { id: "coding-agents", name: "Claude Code, Codex CLI & Cursor", chapters: ["18", "22"],       blurb: "Terminal and editor coding agents, and how to configure them for a repository." },
    { id: "mcp-inspector", name: "MCP Inspector",              chapters: ["07", "08"],             blurb: "Connect to any MCP server and call its tools by hand." },
    { id: "sdks",     name: "Provider SDKs & agent SDKs",      chapters: ["01", "02", "06", "21"], blurb: "Official client libraries and agent SDKs, and what they do for you." },
    { id: "llm-cli",  name: "The llm command-line tool",       chapters: ["01", "04"],             blurb: "Prompt many models from a terminal and log every response to SQLite." },
    { id: "playwright", name: "Playwright",                     chapters: ["17"],                   blurb: "Drive a real browser from code: the substrate of many browser agents." },
    { id: "containers", name: "Docker sandboxes",              chapters: ["20", "18"],             blurb: "Give an agent a disposable machine with only the access it needs." }
  ];

  /* ---------- A5: Retrieval, Search & Document AI ---------- */
  var RET_PARTS = [
    { title: "Orientation",            blurb: "Why getting the right evidence in front of a model is most of the work." },
    { title: "Lexical Search",         blurb: "Analysers, inverted indexes, BM25 and query understanding." },
    { title: "Measuring Retrieval",    blurb: "Relevance metrics, test collections and public benchmarks, before any model choice." },
    { title: "Dense Retrieval",        blurb: "Embeddings, rerankers, late interaction, learned sparse vectors and hybrid search." },
    { title: "Vector Indexes",         blurb: "Approximate nearest-neighbour search and retrieval with filters and permissions." },
    { title: "The RAG System",         blurb: "Retrieval-augmented generation end to end: chunking, rewriting, citations and failure modes." },
    { title: "Document AI",            blurb: "PDFs, layout, OCR, tables and forms, and retrieving pages as images." }
  ];
  var RET_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "Search, retrieval and RAG, and the documents they have to cope with." },
    { id: "01", part: 1, depth: "core",  file: "01-text-analysis.html",       title: "Text Analysis",                            blurb: "Tokenising, normalising, stemming and analysers, and why index and query must agree." },
    { id: "02", part: 1, depth: "deep",  file: "02-bm25.html",                title: "Inverted Indexes & BM25",                  blurb: "Postings, term frequency, document frequency and length normalisation, derived and tuned." },
    { id: "03", part: 1, depth: "core",  file: "03-query-understanding.html", title: "Query Understanding",                      blurb: "Spelling correction, synonyms, expansion, intent and the long tail of queries." },
    { id: "04", part: 2, depth: "deep",  file: "04-relevance-metrics.html",   title: "Relevance Metrics",                        blurb: "Precision, recall, MRR, MAP and nDCG: what each rewards and which question it answers." },
    { id: "05", part: 2, depth: "deep",  file: "05-test-collections.html",    title: "Building a Test Collection",               blurb: "Queries, judgements, pooling and guidelines: a gold set you can trust in a week." },
    { id: "06", part: 2, depth: "core",  file: "06-retrieval-benchmarks.html", title: "Public Benchmarks & Their Limits",        blurb: "BEIR, MTEB and domain benchmarks as shortlist filters, not decisions." },
    { id: "07", part: 3, depth: "deep",  file: "07-dense-retrieval.html",     title: "Dense Retrieval",                          blurb: "Bi-encoders, contrastive training, hard negatives and fine-tuning an embedder." },
    { id: "08", part: 3, depth: "core",  file: "08-rerankers.html",           title: "Rerankers",                                blurb: "Cross-encoders and LLM rerankers: precision at the top for a price." },
    { id: "09", part: 3, depth: "core",  file: "09-late-interaction-sparse.html", title: "Late Interaction & Learned Sparse",    blurb: "ColBERT's token-level matching and SPLADE's learned term weights." },
    { id: "10", part: 3, depth: "deep",  file: "10-hybrid-search.html",       title: "Hybrid Search & Rank Fusion",              blurb: "Combining lexical and dense results with reciprocal rank fusion and score normalisation." },
    { id: "11", part: 4, depth: "deep",  file: "11-ann-indexes.html",         title: "Approximate Nearest-Neighbour Search",     blurb: "HNSW, IVF and product quantisation, and the recall, latency and memory triangle." },
    { id: "12", part: 4, depth: "core",  file: "12-filters-permissions.html", title: "Filters, Metadata & Permissions",          blurb: "Pre- and post-filtering, tenant isolation and document-level access control in retrieval." },
    { id: "13", part: 5, depth: "deep",  file: "13-rag-end-to-end.html",      title: "RAG End to End",                           blurb: "Ingest, index, retrieve, assemble, generate and cite: the whole pipeline and its knobs." },
    { id: "14", part: 5, depth: "deep",  file: "14-chunking.html",            title: "Chunking & Contextual Retrieval",          blurb: "Fixed, structural and semantic chunks, chunk context, and parent-child retrieval." },
    { id: "15", part: 5, depth: "core",  file: "15-agentic-retrieval.html",   title: "Query Rewriting, Agentic Retrieval & GraphRAG", blurb: "Decomposing questions, iterative search, knowledge graphs and when each pays off." },
    { id: "16", part: 5, depth: "deep",  file: "16-grounded-citations.html",  title: "Grounded Answers & Citations",             blurb: "Making every claim traceable to a span, and checking that the span supports it." },
    { id: "17", part: 5, depth: "deep",  file: "17-rag-failures.html",        title: "How RAG Fails",                            blurb: "Missed retrieval, wrong chunk, ignored context, stale sources and confident synthesis." },
    { id: "18", part: 6, depth: "deep",  file: "18-pdf-layout.html",          title: "PDFs & Layout",                            blurb: "What a PDF really contains, born-digital versus scanned, reading order and layout analysis." },
    { id: "19", part: 6, depth: "deep",  file: "19-ocr.html",                 title: "OCR: Classical Engines to Vision-Language Models", blurb: "Detection and recognition, Tesseract to VLM-based OCR, error rates and hallucinated text." },
    { id: "20", part: 6, depth: "core",  file: "20-tables-forms.html",        title: "Tables, Forms & Key-Value Extraction",     blurb: "Table structure recognition, form fields, schemas and validating extracted values." },
    { id: "21", part: 6, depth: "core",  file: "21-visual-retrieval.html",    title: "Visual Document Retrieval",                blurb: "Embedding page images directly with ColPali-style models, and when that beats OCR." },
    { id: "22", part: 6, depth: "intro", file: "22-multilingual.html",        title: "Multilingual & Multi-Script Documents",    blurb: "Scripts without spaces, mixed languages, right-to-left text and cross-lingual retrieval." }
  ];
  var RET_LABS = [
    { id: "L1", file: "lab-01-bm25.html",           title: "A Search Engine with BM25",         afterPart: 1, related: ["01", "02"],       blurb: "An analyser, an inverted index, BM25 scoring and top-k retrieval, tested on a small corpus." },
    { id: "L2", file: "lab-02-retrieval-eval.html", title: "A Retrieval Evaluation Harness",    afterPart: 2, related: ["04", "05"],       blurb: "Precision, recall, MRR and nDCG from judgements, with confidence intervals and a paired comparison." },
    { id: "L3", file: "lab-03-hybrid.html",         title: "Hybrid Retrieval & Reranking",      afterPart: 3, related: ["07", "08", "10"], blurb: "Dense vectors, BM25, reciprocal rank fusion and a reranker, each measured with your harness." },
    { id: "L4", file: "lab-04-hnsw.html",           title: "HNSW from Scratch",                 afterPart: 4, related: ["11"],             blurb: "Build a hierarchical navigable small-world graph and chart recall against search effort." },
    { id: "L5", file: "lab-05-rag-citations.html",  title: "RAG with Verified Citations",       afterPart: 5, related: ["13", "14", "16"], blurb: "Chunk, retrieve, answer with citations and reject any answer whose quotes are not in the source." },
    { id: "L6", file: "lab-06-document-pipeline.html", title: "A Document Understanding Pipeline", afterPart: 6, related: ["18", "19", "20"], blurb: "From OCR boxes to reading order, sections and tables, with character error rate measured." }
  ];
  var RET_CASES = [
    { id: "C1", file: "case-01-contextual-retrieval.html", title: "Contextual Retrieval",     pattern: "Context before embedding",   related: ["14", "10"], blurb: "Prepending chunk context, hybrid search and reranking, and the failure rates each step removed." },
    { id: "C2", file: "case-02-bert-search.html",   title: "BERT Comes to Web Search",          pattern: "Understanding queries",      related: ["03", "07"], blurb: "When a search engine started reading the little words in queries." },
    { id: "C3", file: "case-03-lost-in-the-middle.html", title: "Lost in the Middle",           pattern: "Long context is not free",   related: ["13", "agt:12"], blurb: "Models that used evidence at the start and end of the context and missed it in the middle." },
    { id: "C4", file: "case-04-air-canada.html",    title: "The Chatbot's Promise: Air Canada", pattern: "Grounded answers are a liability question", related: ["16", "17"], blurb: "A tribunal held an airline to a refund policy its chatbot made up." },
    { id: "C5", file: "case-05-faiss.html",         title: "FAISS: Billion-Scale Similarity Search", pattern: "Compressed vectors",    related: ["11"],       blurb: "Product quantisation and GPU search that made nearest neighbours over billions of vectors practical." },
    { id: "C6", file: "case-06-colpali.html",       title: "ColPali: Retrieving Pages as Images", pattern: "Skip the OCR",            related: ["21", "09"], blurb: "Embedding page screenshots directly, and a benchmark built to test it." },
    { id: "C7", file: "case-07-open-document-parsers.html", title: "Open Document Conversion Pipelines", pattern: "Layout models + OCR", related: ["18", "19", "20"], blurb: "How Docling and olmOCR turn PDFs into structured text, and how they were evaluated." }
  ];
  var RET_STUDIOS = [
    { id: "S1", file: "studio-01-enterprise-search.html", title: "Design Enterprise Search with Permissions", afterPart: 4, related: ["10", "11", "12"], blurb: "Many sources, per-document access control, freshness and relevance across a whole company." },
    { id: "S2", file: "studio-02-policy-assistant.html",  title: "Design a Policy & Regulation Assistant",   afterPart: 5, related: ["13", "16", "17"], blurb: "Answers people will act on, from a corpus that changes, with citations a reviewer can check." },
    { id: "S3", file: "studio-03-document-processing.html", title: "Design a Document-Processing Pipeline", afterPart: 6, related: ["18", "19", "20"], blurb: "Millions of scanned forms and invoices a month, with extraction accuracy and human review." }
  ];
  var RET_TOOLS = [
    { id: "opensearch", name: "Elasticsearch & OpenSearch",   chapters: ["01", "02", "10"],       blurb: "The standard open-source search engines, with BM25, analysers and vector search." },
    { id: "vector-dbs", name: "pgvector, Qdrant & friends",   chapters: ["11", "12"],             blurb: "Vector indexes inside Postgres or as dedicated databases." },
    { id: "sbert",    name: "sentence-transformers",          chapters: ["07", "08"],             blurb: "Load, run and fine-tune embedding models and cross-encoders." },
    { id: "ir-eval",  name: "ranx & pytrec_eval",              chapters: ["04", "05"],             blurb: "Standard implementations of retrieval metrics to check your own against." },
    { id: "docling",  name: "Docling, Marker & MinerU",       chapters: ["18", "20"],             blurb: "Open-source PDF-to-structure converters." },
    { id: "ocr",      name: "Tesseract & PaddleOCR",          chapters: ["19", "22"],             blurb: "Classical and deep-learning OCR engines you can run locally." }
  ];

  /* ---------- A6: Evals, Guardrails & Safe Operation ---------- */
  var EVL_PARTS = [
    { title: "Orientation",            blurb: "Why 'it looked good when I tried it' is not evidence, and what is." },
    { title: "Measurement",            blurb: "Error analysis, assertions, LLM judges, statistics and human labels." },
    { title: "Benchmarks",             blurb: "Building benchmarks, keeping them honest, evaluating agents and reading leaderboards." },
    { title: "Truthfulness",           blurb: "Why models make things up, and grounding, abstention and fact-checking that reduce it." },
    { title: "Adversaries",            blurb: "Prompt injection, jailbreaks, architectural defences, classifiers and red teaming." },
    { title: "Operations",             blurb: "Tracing, the improvement flywheel, cost and latency trade-offs, and incidents." },
    { title: "Governance",             blurb: "Risk frameworks, regulation and privacy for systems that make decisions." }
  ];
  var EVL_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "Evaluation as the core skill of AI engineering, and the loop this course teaches." },
    { id: "01", part: 1, depth: "deep",  file: "01-error-analysis.html",      title: "Error Analysis",                           blurb: "Reading traces, open and axial coding, the first failure in each trace, and failure taxonomies." },
    { id: "02", part: 1, depth: "deep",  file: "02-eval-harnesses.html",      title: "Assertions & Eval Harnesses",              blurb: "Deterministic checks first, test cases as data, and a harness you can run on every change." },
    { id: "03", part: 1, depth: "deep",  file: "03-llm-judges.html",          title: "LLM-as-Judge",                             blurb: "Binary rubrics, pairwise comparisons, position and length bias, and calibrating judges against people." },
    { id: "04", part: 1, depth: "deep",  file: "04-eval-statistics.html",     title: "Statistics for Evals",                     blurb: "Error bars, paired comparisons, clustered questions, sample sizes and repeated runs." },
    { id: "05", part: 1, depth: "core",  file: "05-human-labels.html",        title: "Human Labels",                             blurb: "Guidelines, inter-annotator agreement, adjudication and running a labelling effort." },
    { id: "06", part: 2, depth: "deep",  file: "06-building-benchmarks.html", title: "Building a Domain Benchmark",              blurb: "Task definition, sourcing items, gold answers, difficulty, data cards and versioning." },
    { id: "07", part: 2, depth: "deep",  file: "07-contamination.html",       title: "Contamination, Saturation & Decay",        blurb: "How benchmarks leak into training data, saturate, and get audited and retired." },
    { id: "08", part: 2, depth: "deep",  file: "08-agent-evals.html",         title: "Evaluating Agents",                        blurb: "End-state checks, trajectory review, simulated users, pass@k versus pass^k, and cost per task." },
    { id: "09", part: 2, depth: "core",  file: "09-leaderboards.html",        title: "Reading Leaderboards Critically",          blurb: "Arena ratings, self-reported scores, scaffolds and the questions to ask of any number." },
    { id: "10", part: 3, depth: "core",  file: "10-hallucination.html",       title: "Why Models Hallucinate",                   blurb: "Kinds of hallucination, their causes in training and scoring, and how to measure them." },
    { id: "11", part: 3, depth: "deep",  file: "11-grounding-abstention.html", title: "Grounding, Abstention & Confidence",      blurb: "Answering only from evidence, saying 'I don't know', and risk-coverage curves." },
    { id: "12", part: 3, depth: "deep",  file: "12-fact-checking.html",       title: "Fact-Checking & Citation Verification",    blurb: "Claim extraction, evidence retrieval, entailment checks and verifying that citations support claims." },
    { id: "13", part: 4, depth: "deep",  file: "13-prompt-injection.html",    title: "Prompt Injection & Jailbreaks",            blurb: "Direct and indirect injection, jailbreak families, and why detection loses to adaptive attackers." },
    { id: "14", part: 4, depth: "deep",  file: "14-architectural-defences.html", title: "Architectural Defences",               blurb: "Capability limits, the rule of two, dual-model patterns and CaMeL-style data-flow control." },
    { id: "15", part: 4, depth: "core",  file: "15-guardrails.html",          title: "Guardrail Classifiers & Content Policy",   blurb: "Input and output classifiers, policy design, PII filters and measuring guardrail recall." },
    { id: "16", part: 4, depth: "core",  file: "16-red-teaming.html",         title: "Red Teaming",                              blurb: "Planning, manual and automated attacks, scoring findings and closing the loop." },
    { id: "17", part: 5, depth: "core",  file: "17-observability.html",       title: "Tracing & Observability for LLM Systems",  blurb: "Spans for model and tool calls, what to log, sampling, and OpenTelemetry's GenAI conventions." },
    { id: "18", part: 5, depth: "deep",  file: "18-improvement-flywheel.html", title: "The Improvement Flywheel",                blurb: "Production traces to labelled failures to regression suites to safer releases." },
    { id: "19", part: 5, depth: "core",  file: "19-cost-latency-quality.html", title: "Cost, Latency & Quality Trade-offs",      blurb: "Pareto fronts, model routing, caching and deciding what 'good enough' costs." },
    { id: "20", part: 5, depth: "intro", file: "20-ai-incidents.html",        title: "AI Incident Response",                     blurb: "Detecting, containing and learning from an AI system that misbehaves in production." },
    { id: "21", part: 6, depth: "core",  file: "21-governance.html",          title: "Governance Frameworks & Regulation",       blurb: "NIST AI RMF, ISO/IEC 42001 and the EU AI Act, read as engineering requirements." },
    { id: "22", part: 6, depth: "core",  file: "22-privacy-data.html",        title: "Privacy & Data Handling for AI",           blurb: "PII in prompts and logs, retention, training on customer data, and data residency." }
  ];
  var EVL_LABS = [
    { id: "L1", file: "lab-01-eval-harness.html",   title: "An Eval Harness with Error Bars",   afterPart: 1, related: ["02", "04"],       blurb: "Run cases, score them, bootstrap confidence intervals and compare two systems with a paired test." },
    { id: "L2", file: "lab-02-judge-calibration.html", title: "Calibrate an LLM Judge",         afterPart: 1, related: ["03", "05"],       blurb: "Measure a judge's agreement with human labels, probe position and length bias, and correct the estimate." },
    { id: "L3", file: "lab-03-benchmark.html",      title: "Build a Domain Benchmark",          afterPart: 2, related: ["06", "07"],       blurb: "Validate items, split them, version them and run a contamination probe." },
    { id: "L4", file: "lab-04-agent-eval.html",     title: "Evaluate an Agent",                 afterPart: 2, related: ["08"],             blurb: "A simulated shop with a database: grade end states, run each task k times and report pass^k." },
    { id: "L5", file: "lab-05-citations-abstention.html", title: "Citation Checking & Abstention", afterPart: 3, related: ["11", "12"],     blurb: "Verify quoted spans, score claim support, then sweep an abstention threshold on a risk-coverage curve." },
    { id: "L6", file: "lab-06-red-team.html",       title: "Red-Team a RAG Agent",              afterPart: 4, related: ["13", "14", "15"], blurb: "Forty injection payloads against four defences, with attack success rates and utility costs." },
    { id: "L7", file: "lab-07-regression-gate.html", title: "Traces & a Regression Gate",       afterPart: 5, related: ["17", "18"],       blurb: "Emit spans, turn failures into regression cases and block a release that gets worse." }
  ];
  var EVL_CASES = [
    { id: "C1", file: "case-01-swe-bench-verified.html", title: "Retiring SWE-bench Verified", pattern: "Benchmark lifecycle",         related: ["07", "08"], blurb: "A widely reported coding benchmark, an audit of its hardest tasks, and why its main sponsor stopped using it." },
    { id: "C2", file: "case-02-cuda-engineer.html",  title: "The AI CUDA Engineer",              pattern: "Evaluator hacking",           related: ["02", "07", "oe:15"], blurb: "Claimed kernel speedups that came from loopholes in the evaluation harness." },
    { id: "C3", file: "case-03-mata-avianca.html",   title: "Fake Citations in Court",           pattern: "Unverified generation",       related: ["10", "12"], blurb: "Lawyers who filed a brief citing cases a chatbot had invented, and the court's response." },
    { id: "C4", file: "case-04-attacker-moves-second.html", title: "The Attacker Moves Second",  pattern: "Adaptive attacks",            related: ["13", "14"], blurb: "Published prompt-injection defences re-tested against attackers who adapt, and what survived." },
    { id: "C5", file: "case-05-tau-bench.html",      title: "tau-bench: Agents with Simulated Users", pattern: "End-state grading",     related: ["08"],       blurb: "Grading an agent by the database it leaves behind, and reliability measured as pass^k." },
    { id: "C6", file: "case-06-leaderboard-illusion.html", title: "The Leaderboard Illusion",    pattern: "Rankings can be gamed",       related: ["09"],       blurb: "Private testing, selective disclosure and sampling rates behind a popular model arena." },
    { id: "C7", file: "case-07-ai-overviews.html",   title: "Glue on Pizza: Search Answers Go Wrong", pattern: "Bad sources, confident answers", related: ["11", "17", "ret:17"], blurb: "AI-generated search summaries that repeated jokes and satire as fact, and the fixes that followed." }
  ];
  var EVL_STUDIOS = [
    { id: "S1", file: "studio-01-eval-program.html", title: "Design the Eval Program for an Assistant", afterPart: 2, related: ["01", "03", "06"], blurb: "Who labels, what is measured, how often, which numbers block a release and who signs off." },
    { id: "S2", file: "studio-02-agent-guardrails.html", title: "Design Guardrails for an Agent with Tools", afterPart: 4, related: ["13", "14", "15"], blurb: "An agent that reads email and can send it: threat model, capability limits, classifiers and monitoring." },
    { id: "S3", file: "studio-03-llm-observability.html", title: "Design LLM Observability & Continuous Evaluation", afterPart: 5, related: ["17", "18", "19"], blurb: "Traces at scale, online evaluators, sampling, dashboards, alerts and the path from failure to fix." }
  ];
  var EVL_TOOLS = [
    { id: "inspect",  name: "Inspect",                       chapters: ["02", "06", "08"],       blurb: "The UK AI Security Institute's open-source evaluation framework." },
    { id: "promptfoo", name: "promptfoo",                    chapters: ["02", "16"],             blurb: "Declarative test cases, assertions and red-team scans for prompts and apps." },
    { id: "tracing",  name: "Langfuse & Phoenix",            chapters: ["17", "18"],             blurb: "Open-source tracing, datasets and online evaluation for LLM applications." },
    { id: "redteam",  name: "garak & PyRIT",                 chapters: ["13", "16"],             blurb: "Automated vulnerability scanners and red-teaming toolkits for language models." },
    { id: "labelling", name: "Annotation tools",             chapters: ["01", "05"],             blurb: "Spreadsheets, Label Studio and custom review apps for reading and labelling traces." },
    { id: "presidio", name: "Presidio",                      chapters: ["15", "22"],             blurb: "Detect and redact personal data in text before it reaches a model or a log." }
  ];

  /* ---------- A7: Search, Evolution & Self-Improving Agents ---------- */
  var OE_PARTS = [
    { title: "Orientation",            blurb: "Optimisation versus open-endedness, and why it matters for AI systems." },
    { title: "Search Foundations",     blurb: "Tree search, bandits, evolution, novelty and quality-diversity." },
    { title: "Open-Endedness",         blurb: "Algorithms that keep inventing new problems, judges of interestingness and lifelong agents." },
    { title: "LLMs as Search Operators", blurb: "Inference-time search, program evolution and evolving prompts and agents." },
    { title: "Meta Agents",            blurb: "Agents that design agents, improve their own code and run experiments." },
    { title: "Integrity",              blurb: "Evaluator hacking, held-out evaluation and safety for systems that change themselves." },
    { title: "Applied",                blurb: "When evolutionary search earns its place in a real product." }
  ];
  var OE_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "Objectives, search and open-ended discovery, and what this course builds." },
    { id: "19", part: 1, depth: "deep",  file: "19-evolution-for-builders.html", title: "Evolution for Builders",              blurb: "What biology actually does: variation, inheritance, selection, genotype and phenotype, landscapes, drift and evolvability." },
    { id: "01", part: 1, depth: "deep",  file: "01-tree-search.html",         title: "Tree Search, Bandits & MCTS",              blurb: "Exploration versus exploitation, UCB, Monte Carlo tree search and the AlphaZero idea." },
    { id: "02", part: 1, depth: "deep",  file: "02-evolutionary-algorithms.html", title: "Evolutionary Algorithms",              blurb: "Populations, mutation, crossover, selection pressure and evolution strategies." },
    { id: "20", part: 1, depth: "deep",  file: "20-gp-neuroevolution-cmaes.html", title: "Genetic Programming, Neuroevolution & CMA-ES", blurb: "Evolving program trees, evolving networks with NEAT, and the evolution strategy that learns its own step shape." },
    { id: "03", part: 1, depth: "core",  file: "03-novelty-search.html",      title: "Why Objectives Deceive",                   blurb: "Deceptive fitness landscapes, novelty search and the value of stepping stones." },
    { id: "04", part: 1, depth: "deep",  file: "04-quality-diversity.html",   title: "Quality-Diversity & MAP-Elites",           blurb: "Archives of diverse high performers, behaviour descriptors and illumination." },
    { id: "05", part: 2, depth: "core",  file: "05-open-ended-algorithms.html", title: "Open-Ended Algorithms",                  blurb: "POET and co-evolving problems with solutions, and what 'open-ended' means." },
    { id: "06", part: 2, depth: "core",  file: "06-interestingness.html",     title: "Models of Interestingness",                blurb: "Using foundation models to judge what is new and worth learning: OMNI and successors." },
    { id: "07", part: 2, depth: "core",  file: "07-lifelong-agents.html",     title: "Lifelong Agents & Skill Libraries",        blurb: "Voyager's curriculum, skills as code and agents that accumulate abilities." },
    { id: "08", part: 3, depth: "deep",  file: "08-inference-time-search.html", title: "Inference-Time Search",                  blurb: "Best-of-n, self-consistency, tree search over answers, verifiers and adaptive branching." },
    { id: "09", part: 3, depth: "deep",  file: "09-program-evolution.html",   title: "LLM-Guided Program Evolution",             blurb: "FunSearch and AlphaEvolve: language models as mutation operators with automatic evaluators." },
    { id: "10", part: 3, depth: "core",  file: "10-evolution-frameworks.html", title: "Open Evolution Frameworks",               blurb: "Inside OpenEvolve and ShinkaEvolve: islands, archives, novelty rejection and sample efficiency." },
    { id: "11", part: 3, depth: "core",  file: "11-evolving-prompts.html",    title: "Evolving Prompts & Pipelines",             blurb: "Prompt evolution, self-referential improvement and optimising LLM programs with DSPy." },
    { id: "12", part: 4, depth: "deep",  file: "12-meta-agent-search.html",   title: "Automated Design of Agentic Systems",      blurb: "A meta agent that writes agents as code, keeps an archive and searches for better designs." },
    { id: "13", part: 4, depth: "deep",  file: "13-self-improving-agents.html", title: "Self-Improving Coding Agents",           blurb: "The Darwin Gödel Machine: an agent that edits its own scaffold, validated empirically." },
    { id: "21", part: 4, depth: "deep",  file: "21-self-referential-improvers.html", title: "Self-Referential Improvers",        blurb: "From the Gödel machine to STOP and the Darwin Gödel Machine: improvers that improve the improver, and what stops them." },
    { id: "14", part: 4, depth: "core",  file: "14-automated-science.html",   title: "Automated Science",                        blurb: "The AI Scientist: ideas, experiments, papers and automated review, and their limits." },
    { id: "15", part: 5, depth: "deep",  file: "15-evaluator-hacking.html",   title: "Evaluator Hacking & Reward Hacking",       blurb: "Search finds every loophole in the scorer: famous examples and how to harden evaluators." },
    { id: "16", part: 5, depth: "deep",  file: "16-held-out-evaluation.html", title: "Held-Out Evaluation for Self-Improvers",   blurb: "Separate search, selection and test sets, and the statistics of picking the best of many." },
    { id: "17", part: 5, depth: "core",  file: "17-self-modification-safety.html", title: "Safety of Self-Modifying Systems",     blurb: "Sandboxes, lineage tracking, human oversight and objectives that resist gaming." },
    { id: "18", part: 6, depth: "core",  file: "18-search-in-products.html",  title: "Search Inside Real Products",              blurb: "Evolving prompts, rules and heuristics for a business, and when simpler methods win." }
  ];
  var OE_LABS = [
    { id: "L1", file: "lab-01-mcts.html",           title: "Bandits & Monte Carlo Tree Search", afterPart: 1, related: ["01"],             blurb: "Epsilon-greedy, UCB and Thompson sampling, then MCTS that plays a small game well." },
    { id: "L2", file: "lab-02-map-elites.html",     title: "Novelty Search & MAP-Elites",       afterPart: 1, related: ["02", "03", "04"], blurb: "A deceptive maze where objective search fails, novelty search succeeds and MAP-Elites illuminates." },
    { id: "L3", file: "lab-03-program-evolution.html", title: "A Mini FunSearch",               afterPart: 3, related: ["09", "10"],       blurb: "Evolve bin-packing heuristics as code with an island archive and a pluggable mutation operator." },
    { id: "L4", file: "lab-04-ab-mcts.html",        title: "Adaptive Branching over Many Models", afterPart: 3, related: ["08"],           blurb: "Decide when to sample a new answer, refine an old one or switch models, under a call budget." },
    { id: "L5", file: "lab-05-meta-agent.html",     title: "A Mini Meta-Agent Search",          afterPart: 4, related: ["12", "16"],       blurb: "Search over agent designs on a small benchmark, with separate search and held-out splits." },
    { id: "L6", file: "lab-06-gameable-evaluator.html", title: "The Gameable Evaluator",        afterPart: 5, related: ["15", "16"],       blurb: "Watch a search loop exploit a leaky scorer, then harden the harness until the exploits stop." },
    { id: "L7", file: "lab-07-improve-the-improver.html", title: "Improve the Improver",        afterPart: 5, related: ["21", "16", "09"], blurb: "A STOP-style loop: the bin-packing evolver searches over its own settings, judged on held-out instances it never sees." }
  ];
  var OE_CASES = [
    { id: "C1", file: "case-01-alphazero.html",     title: "AlphaGo to AlphaZero",              pattern: "Search plus learning",        related: ["01"],       blurb: "Tree search guided by a learned policy and value, and what self-play removed." },
    { id: "C2", file: "case-02-picbreeder.html",    title: "Picbreeder & Why Greatness Cannot Be Planned", pattern: "Stepping stones",  related: ["03", "05"], blurb: "Images nobody aimed for, found by people following what was interesting." },
    { id: "C3", file: "case-03-funsearch.html",     title: "FunSearch and the Cap Set",         pattern: "Evolving programs, not answers", related: ["09"],    blurb: "A language model in an evolutionary loop that found new constructions in mathematics." },
    { id: "C4", file: "case-04-alphaevolve.html",   title: "AlphaEvolve",                       pattern: "Evolution with evaluators",   related: ["09", "10"], blurb: "Evolving whole codebases against automatic evaluators, from matrix multiplication to data-centre scheduling." },
    { id: "C5", file: "case-05-voyager.html",       title: "Voyager in Minecraft",              pattern: "Skill libraries",             related: ["07"],       blurb: "A lifelong agent that wrote its own curriculum and kept its skills as code." },
    { id: "C6", file: "case-06-darwin-godel-machine.html", title: "The Darwin Gödel Machine",   pattern: "Open-ended self-improvement", related: ["13", "17"], blurb: "A coding agent that rewrote its own tools, and the objective hacking its authors reported." },
    { id: "C7", file: "case-07-ai-scientist.html",  title: "The AI Scientist and Peer Review",  pattern: "Automating the research loop", related: ["14", "15"], blurb: "Generated papers, an automated reviewer and a workshop submission, read with care." }
  ];
  var OE_STUDIOS = [
    { id: "S1", file: "studio-01-optimisation-loop.html", title: "Design an Automated Optimisation Loop", afterPart: 3, related: ["09", "10", "16"], blurb: "Evolve a scheduling heuristic for a business: evaluator, budget, archive, safety and rollout." },
    { id: "S2", file: "studio-02-review-claim.html",      title: "Review a Self-Improvement Claim",       afterPart: 5, related: ["15", "16", "17"], blurb: "A team says its agent improved itself by 30%. Decide what you need to see before you believe it." },
    { id: "S3", file: "studio-03-build-a-self-improver.html", title: "Capstone: Build and Audit Your Own Self-Improver", afterPart: 5, related: ["19", "21", "16", "17"], blurb: "Choose a problem with an honest evaluator, build an evolving loop that improves its own search, and write the audit that proves it." }
  ];
  var OE_TOOLS = [
    { id: "openevolve", name: "OpenEvolve",                  chapters: ["09", "10"],             blurb: "An open-source implementation of AlphaEvolve-style program evolution." },
    { id: "shinka",   name: "ShinkaEvolve",                  chapters: ["10"],                   blurb: "Sakana AI's sample-efficient open-source evolution framework." },
    { id: "pyribs",   name: "pyribs",                        chapters: ["04"],                   blurb: "A quality-diversity library with MAP-Elites and its descendants." },
    { id: "dspy",     name: "DSPy",                          chapters: ["11"],                   blurb: "Write LLM pipelines as modules and let optimisers tune prompts and examples." },
    { id: "evotorch", name: "Evolution-strategy libraries",  chapters: ["02"],                   blurb: "CMA-ES and friends for black-box optimisation." }
  ];

  /* ---------- A8: Applied AI Delivery Studio (capstone) ---------- */
  var AID_PARTS = [
    { title: "Orientation",            blurb: "What applied and forward-deployed AI engineers actually do all day." },
    { title: "Discovery",              blurb: "Interviews, requirements under ambiguity, expert knowledge and whether AI is the right tool." },
    { title: "Building the Proof",     blurb: "Prototypes that test the riskiest assumption, evaluation plans and model choices." },
    { title: "Domains",                blurb: "Finance, healthcare, law and government: what each one cares about and forbids." },
    { title: "Delivery",               blurb: "From proof of concept to production, restricted environments, cost and security review." },
    { title: "Productisation & Communication", blurb: "Turning research into products, writing for customers, and getting hired." }
  ];
  var AID_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "The applied AI engineer's job, and how the studios in this capstone work." },
    { id: "01", part: 1, depth: "deep",  file: "01-discovery-interviews.html", title: "Discovery Interviews",                    blurb: "Asking about past behaviour, not opinions; finding the real problem behind the requested feature." },
    { id: "02", part: 1, depth: "deep",  file: "02-requirements-ambiguity.html", title: "Requirements Under Ambiguity",          blurb: "Turning a vague goal into decisions, constraints and success metrics both sides sign." },
    { id: "03", part: 1, depth: "deep",  file: "03-expert-knowledge.html",    title: "Capturing Expert Knowledge",               blurb: "Shadowing, think-aloud sessions and worked examples: turning tacit judgement into rubrics and data." },
    { id: "04", part: 1, depth: "core",  file: "04-feasibility.html",         title: "Is AI the Right Tool?",                    blurb: "Feasibility, error tolerance, data availability and risk: a triage before anyone builds." },
    { id: "05", part: 2, depth: "deep",  file: "05-riskiest-assumption.html", title: "Prototype the Riskiest Assumption",        blurb: "Build the smallest thing that could prove you wrong, in days, not months." },
    { id: "06", part: 2, depth: "deep",  file: "06-evaluation-plans.html",    title: "Evaluation Plans Customers Trust",         blurb: "Gold sets from the customer's own work, agreed metrics and comparison with the current process." },
    { id: "07", part: 2, depth: "core",  file: "07-choosing-models.html",     title: "Choosing Models",                          blurb: "Frontier APIs, open-weight models and on-premises deployment, chosen by evidence and constraints." },
    { id: "08", part: 3, depth: "core",  file: "08-finance.html",             title: "Finance",                                  blurb: "Lending, research, compliance and wealth management, with model risk management and audit." },
    { id: "09", part: 3, depth: "core",  file: "09-healthcare.html",          title: "Healthcare & Life Sciences",               blurb: "Clinical documentation, patient safety, medical-device rules and protected health data." },
    { id: "10", part: 3, depth: "core",  file: "10-legal.html",               title: "Legal & Compliance",                       blurb: "Contracts, discovery and research, privilege and confidentiality, and verifying every citation." },
    { id: "11", part: 3, depth: "core",  file: "11-public-sector.html",       title: "Public Sector & Government",               blurb: "Citizen services, analysts and caseworkers, procurement, transparency and accountability." },
    { id: "12", part: 4, depth: "deep",  file: "12-poc-to-production.html",   title: "From Proof of Concept to Production",      blurb: "Why most pilots stall, production gates, integration, support and change management." },
    { id: "13", part: 4, depth: "core",  file: "13-restricted-environments.html", title: "Restricted Environments",              blurb: "On-premises and air-gapped deployment, data residency and a limited menu of approved models." },
    { id: "14", part: 4, depth: "core",  file: "14-cost-roi.html",            title: "Cost Models & Return on Investment",       blurb: "Unit economics per task, total cost of ownership and an honest return-on-investment case." },
    { id: "15", part: 4, depth: "core",  file: "15-security-review.html",     title: "Security Reviews for AI Systems",          blurb: "The questions a customer's security team will ask, and the evidence pack that answers them." },
    { id: "16", part: 5, depth: "core",  file: "16-research-to-product.html", title: "Turning Research into Products",           blurb: "From a paper and a repository to an interface, SLOs, documentation and support." },
    { id: "17", part: 5, depth: "deep",  file: "17-writing-for-customers.html", title: "Writing for Customers",                  blurb: "Status reports, analysis memos and presenting a failure honestly to the people paying." },
    { id: "18", part: 5, depth: "deep",  file: "18-getting-hired.html",       title: "Take-Homes, Portfolios & Interviews",      blurb: "What applied AI teams test, how to scope a take-home, and a portfolio that proves judgement." },
    { id: "19", part: 5, depth: "intro", file: "19-where-next.html",          title: "Where Next",                               blurb: "Keeping up without drowning, and the next steps after this path." }
  ];
  var AID_LABS = [
    { id: "L1", file: "lab-01-brief-to-eval.html",  title: "From Brief to Evaluation Kit",      afterPart: 2, related: ["02", "06"],       blurb: "Turn a customer brief and sample documents into a validated gold set, rubric and acceptance thresholds." },
    { id: "L2", file: "lab-02-cost-model.html",     title: "A Cost & Latency Model",            afterPart: 4, related: ["14", "07"],       blurb: "Price a workload across models, caching and batching, and find the cheapest option that meets the bar." },
    { id: "L3", file: "lab-03-pii-pipeline.html",   title: "A PII Redaction & Audit Pipeline",  afterPart: 4, related: ["13", "15"],       blurb: "Detect and redact personal data, keep reversible tokens for authorised users and log every access." },
    { id: "L4", file: "lab-04-take-home.html",      title: "A Take-Home, End to End",           afterPart: 5, related: ["05", "06", "18"], blurb: "A timed document-QA system graded by hidden tests, with the memo that goes with it." }
  ];
  var AID_CASES = [
    { id: "C1", file: "case-01-klarna.html",        title: "Klarna's AI Assistant",             pattern: "Automation claims meet customers", related: ["06", "12"], blurb: "An assistant said to do the work of hundreds of agents, and the later decision to bring humans back." },
    { id: "C2", file: "case-02-morgan-stanley.html", title: "A Research Assistant for Financial Advisers", pattern: "Evals before rollout", related: ["06", "08"], blurb: "An assistant over a firm's own research library, gated by an evaluation framework built with experts." },
    { id: "C3", file: "case-03-nyc-mycity.html",    title: "A City's Chatbot Gives Illegal Advice", pattern: "Public-sector accountability", related: ["11", "04"], blurb: "A government business-advice chatbot that told owners they could break the law." },
    { id: "C4", file: "case-04-forward-deployed.html", title: "The Forward-Deployed Engineer",  pattern: "Engineers embedded with customers", related: ["01", "12"], blurb: "How embedding engineers with customers became a model for AI companies." },
    { id: "C5", file: "case-05-legal-ai-rollout.html", title: "Rolling Out AI in a Law Firm",   pattern: "Expert users, verification culture", related: ["10", "03"], blurb: "Pilots, verification rules and adoption when every answer must be checked by a professional." },
    { id: "C6", file: "case-06-bank-lending-workflow.html", title: "An Expert Workflow for Bank Lending", pattern: "Decompose expert reasoning", related: ["03", "08"], blurb: "A loan-document assistant built by structuring expert judgement, with feedback loops calibrated to reviewers." }
  ];
  var AID_STUDIOS = [
    { id: "S1", file: "studio-01-contract-review.html",  title: "Take-Home: Contract Clause Review",   afterPart: 2, related: ["05", "06", "10"], blurb: "A legal team wants risky clauses flagged in supplier contracts. Scope it, build the proof, report." },
    { id: "S2", file: "studio-02-analyst-assistant.html", title: "Take-Home: An Analyst's Research Assistant", afterPart: 2, related: ["05", "06", "08"], blurb: "Answer questions over annual reports with numbers that tie to the page they came from." },
    { id: "S3", file: "studio-03-claims-triage.html",    title: "Take-Home: Insurance Claims Triage", afterPart: 3, related: ["04", "06"],       blurb: "Route incoming claims with attachments, and decide what never goes to a model." },
    { id: "S4", file: "studio-04-citizen-services.html", title: "Take-Home: Citizen Services Q&A",    afterPart: 3, related: ["11", "06"],       blurb: "A government help service that must be accurate, accessible and accountable." },
    { id: "S5", file: "studio-05-clinical-notes.html",   title: "Take-Home: Clinical Note Summaries", afterPart: 3, related: ["09", "06"],       blurb: "Summaries clinicians can trust, with omissions measured as carefully as errors." },
    { id: "S6", file: "studio-06-support-automation.html", title: "Take-Home: Support Automation with Refunds", afterPart: 4, related: ["12", "14", "15"], blurb: "Automate part of a support queue with money at stake, and prove the savings." },
    { id: "S7", file: "studio-07-coding-assistant-rollout.html", title: "Take-Home: Rolling Out a Coding Assistant", afterPart: 4, related: ["12", "14"], blurb: "A 300-engineer company wants AI coding tools. Plan the rollout and measure the effect honestly." },
    { id: "S8", file: "studio-08-productise-research.html", title: "Take-Home: Productise a Research Prototype", afterPart: 5, related: ["16", "17"], blurb: "A promising research repository, a customer who wants it next quarter, and everything in between." }
  ];
  var AID_TOOLS = [
    { id: "demo-uis", name: "Gradio & Streamlit",            chapters: ["05"],                   blurb: "A usable demo in an afternoon, so customers react to something real." },
    { id: "fastapi",  name: "FastAPI",                       chapters: ["12", "16"],             blurb: "Typed Python web APIs with generated documentation." },
    { id: "compose",  name: "Docker Compose",                chapters: ["13", "12"],             blurb: "Package a whole system so a customer can run it inside their own network." },
    { id: "pii-tools", name: "Presidio for redaction",       chapters: ["15", "09"],             blurb: "Detect and anonymise personal data before it leaves a boundary." },
    { id: "writing",  name: "Writing & diagram tools",       chapters: ["17", "18"],             blurb: "Markdown, Mermaid and a memo template for status reports and analysis write-ups." }
  ];


  window.CS_DEPTH_LABEL = { deep: "Deep dive", core: "Core", intro: "Quick intro" };

  /* status: "done" | "building" | "planned". Planned courses appear on the hub only. */
  window.CS_COURSES = [
    { id: "mlf", dir: "ml-foundations", track: "ai", num: "A0", mark: "MF", title: "Math & Code for Machine Learning", subtitle: "the toolkit at the point of need",
      tagline: "Arrays, linear algebra, derivatives and autodiff, probability, information theory and the statistics of experiments, taught as each later course needs them.",
      status: "done", parts: MLF_PARTS, chapters: MLF_CHAPTERS, labs: MLF_LABS, cases: MLF_CASES, studios: MLF_STUDIOS, tools: MLF_TOOLS,
      spine: ["00", "01", "02", "04", "20", "21", "22", "05", "06", "08", "09", "10", "12", "13", "14", "15"] },
    { id: "ml", dir: "ml", track: "ai", num: "A1", mark: "ML", title: "Machine Learning & Data Science", subtitle: "models you can trust",
      tagline: "Framing, metrics, linear models, trees and boosting, unsupervised learning, validation, leakage, calibration, features and proving value.",
      status: "done", parts: ML_PARTS, chapters: ML_CHAPTERS, labs: ML_LABS, cases: ML_CASES, studios: ML_STUDIOS, tools: ML_TOOLS,
      spine: ["01", "02", "04", "05", "06", "07", "13", "14"] },
    { id: "dl", dir: "deep-learning", track: "ai", num: "A2", mark: "DL", title: "Deep Learning & Transformers", subtitle: "from a neuron to a GPT",
      tagline: "Backpropagation, training dynamics, embeddings, attention, the Transformer, tokenisation, decoding, scaling laws and modern architectures.",
      status: "done", parts: DL_PARTS, chapters: DL_CHAPTERS, labs: DL_LABS, cases: DL_CASES, studios: DL_STUDIOS, tools: DL_TOOLS,
      spine: ["01", "02", "03", "04", "05", "06", "09", "10", "11", "12", "13", "14", "15", "16"] },
    { id: "llm", dir: "llm-training", track: "ai", num: "A3", mark: "LT", title: "Training, Post-training & Serving LLMs", subtitle: "the life of a model",
      tagline: "Pretraining data and parallelism, RL foundations, fine-tuning, LoRA, RLHF, DPO and GRPO, merging, quantisation and serving engines.",
      status: "done", parts: LLM_PARTS, chapters: LLM_CHAPTERS, labs: LLM_LABS, cases: LLM_CASES, studios: LLM_STUDIOS, tools: LLM_TOOLS,
      spine: ["06", "07", "08", "09", "10", "11", "12", "13", "14", "16"] },
    { id: "agt", dir: "agents", track: "ai", num: "A4", mark: "AG", title: "Agents, Tools & Protocols", subtitle: "models that act",
      tagline: "The tool loop, tool design, function calling, MCP and A2A, context engineering, workflows, multi-agent systems, deep research, computer use and agent security.",
      status: "done", parts: AGT_PARTS, chapters: AGT_CHAPTERS, labs: AGT_LABS, cases: AGT_CASES, studios: AGT_STUDIOS, tools: AGT_TOOLS,
      spine: ["01", "02", "03", "04", "05", "10", "11", "13", "18", "19", "20"] },
    { id: "ret", dir: "retrieval", track: "ai", num: "A5", mark: "RS", title: "Retrieval, Search & Document AI", subtitle: "the right evidence, with a source",
      tagline: "BM25, relevance metrics, dense and hybrid retrieval, vector indexes, RAG with citations, and PDFs, OCR, tables and visual retrieval.",
      status: "done", parts: RET_PARTS, chapters: RET_CHAPTERS, labs: RET_LABS, cases: RET_CASES, studios: RET_STUDIOS, tools: RET_TOOLS,
      spine: ["07", "11"] },
    { id: "evl", dir: "evals", track: "ai", num: "A6", mark: "EV", title: "Evals, Guardrails & Safe Operation", subtitle: "knowing that it works",
      tagline: "Error analysis, LLM judges, eval statistics, domain benchmarks, agent evals, hallucination, prompt injection, guardrails, observability and governance.",
      status: "done", parts: EVL_PARTS, chapters: EVL_CHAPTERS, labs: EVL_LABS, cases: EVL_CASES, studios: EVL_STUDIOS, tools: EVL_TOOLS,
      spine: ["01", "02", "03", "04", "06", "07", "08"] },
    { id: "oe", dir: "open-ended", track: "ai", num: "A7", mark: "OE", title: "Search, Evolution & Self-Improving Agents", subtitle: "systems that keep discovering",
      tagline: "MCTS, evolution, novelty and quality-diversity, open-ended algorithms, LLM-guided program evolution, meta agents and the integrity of self-improvement.",
      status: "done", parts: OE_PARTS, chapters: OE_CHAPTERS, labs: OE_LABS, cases: OE_CASES, studios: OE_STUDIOS, tools: OE_TOOLS,
      spine: ["00", "19", "01", "02", "20", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "21", "14", "15", "16", "17", "18"] },
    { id: "aid", dir: "ai-delivery", track: "ai", num: "A8", mark: "AD", title: "Applied AI Delivery Studio", subtitle: "capstone: from brief to production",
      tagline: "Discovery, requirements under ambiguity, prototypes, evaluation plans, domains, production delivery, security reviews, writing for customers and getting hired.",
      status: "done", parts: AID_PARTS, chapters: AID_CHAPTERS, labs: AID_LABS, cases: AID_CASES, studios: AID_STUDIOS, tools: AID_TOOLS,
      spine: [] }
  ];

  /* Workbench: the chapters' ideas with real tools on a real machine (page
     kind "workbench", <course>/workbench/). Each predicts a number from the
     chapters it measures, then measures it. machine: laptop | linux | gpu
     (the least the page needs); cost is for the GPU part at rented prices. */
  /* Planned, not yet written (add the entry back with its page): llm W4 DPO on a Small Preference Set; llm W5 GRPO on a Verifiable Task; llm W7 Serve with vLLM and Load-Test It; llm W8 Speculative Decoding, Timed; dl W3 Real Tokenisers; ml W1 The Same Models in scikit-learn; ret W1 Real Embedders and a Reranker; agt W1 Your Agent Loop on a Local Model; evl W1 A Real Judge, Calibrated; oe W1 Program Evolution with a Real Model; oe W2 Evolution at Scale on a GPU; aid W1 Deploy a Model as a Serverless Endpoint. */
  var WORKBENCHES = {
    llm: [
      { id: "W1", file: "w01-kv-cache.html", title: "The KV Cache, Measured", machine: "laptop", chapters: ["18"], time: "20 min, +1 h on a GPU", cost: "GPU part: about an hour of a 24 GB card",
        blurb: "Predict the cache from config.json, read the real tensors, then find how many 4k conversations fit on one GPU." },
      { id: "W2", file: "w02-training-memory.html", title: "Where Training Memory Goes", machine: "gpu", chapters: ["02"], time: "1 h", cost: "about an hour of a 24 GB card",
        blurb: "Weights, gradients, optimiser state and activations: predict each, then watch max_memory_allocated step by step." },
      { id: "W3", file: "w03-lora-qlora.html", title: "LoRA, then QLoRA, on a Real Model", machine: "gpu", chapters: ["11"], time: "2 h", cost: "about two hours of a 24 GB card",
        blurb: "Fine-tune a 0.5B to 3B model with LoRA, then in 4 bits; predict trainable parameters and memory, measure both." },
      { id: "W6", file: "w06-quantisation.html", title: "Quantise and Measure Perplexity", machine: "gpu", chapters: ["19"], time: "1.5 h", cost: "about 90 minutes of a 24 GB card",
        blurb: "16, 8 and 4 bits: predict the memory, measure it, and measure what perplexity pays for it." }
    ],
    dl: [
      { id: "W1", file: "w01-pytorch.html", title: "PyTorch by Hand", machine: "laptop", chapters: ["05"], time: "1 h",
        blurb: "Tensors, autograd and a training loop, checked against the micrograd-style engine you built." },
      { id: "W2", file: "w02-char-gpt.html", title: "Train a Character GPT", machine: "laptop", chapters: ["12", "16"], time: "1 h, +1 h on a GPU", cost: "GPU part: about an hour",
        blurb: "Chapter 12's GPT in PyTorch on Tiny Shakespeare; predict FLOPs and time, then scale it on a GPU." },
      { id: "W4", file: "w04-attention-kernels.html", title: "Attention Kernels, Benchmarked", machine: "gpu", chapters: ["19", "09"], time: "1 h", cost: "about an hour of a GPU",
        blurb: "Naive attention against PyTorch's fused kernel: predict memory traffic, measure time and peak memory as length grows." },
      { id: "W5", file: "w05-word-vectors.html", title: "Word Vectors from Real Text", machine: "laptop", chapters: ["06"], time: "1 h",
        blurb: "Skip-gram with negative sampling in PyTorch on text8; analogies, neighbours and what the loss curve says." }
    ]
  };
  window.CS_COURSES.forEach(function (co) { co.workbenches = WORKBENCHES[co.id] || []; });
})();
