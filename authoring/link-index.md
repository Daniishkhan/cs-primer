# Link index (generated from assets/js/catalog.js)

Every page on the site, by course. Link with a path relative to the page you are writing, e.g. from evals/chapters/x.html to ../../reliability/chapters/06-tracing.html, or within a course ../chapters/02-tool-loop.html. Cross-course ids for catalog `related` fields are written course-id:chapter-id (only the coordinator edits the catalog).

## A0 · Math & Code for Machine Learning  (id "mlf", folder ml-foundations/)

Part 0: Orientation
- ml-foundations/chapters/00-start-here.html · ch 00 · intro · Start Here: What AI systems engineers build, the nine courses, and how to use them without drowning.
Part 1: Python for ML Work
- ml-foundations/chapters/01-python-numerics.html · ch 01 · core · Python for Numerical Work: Numbers, lists and loops, why pure Python is slow for maths, and the idea of vectorising.
- ml-foundations/chapters/02-numpy-arrays.html · ch 02 · deep · NumPy, Arrays & Broadcasting: Shapes, strides, axes and broadcasting: the mental model behind every tensor library.
- ml-foundations/chapters/03-data-wrangling.html · ch 03 · core · Data Wrangling: pandas, SQL & Tidy Data: Loading, joining, grouping and cleaning tables, and the questions to ask any dataset.
- ml-foundations/chapters/04-reproducible-experiments.html · ch 04 · core · Reproducible Experiments: Environments, pinned versions, seeds, notebooks versus scripts and experiment logs.
Part 2: Linear Algebra
- ml-foundations/chapters/05-vectors-similarity.html · ch 05 · deep · Vectors, Dot Products & Similarity: Vectors as arrows and as lists, length, angle, cosine similarity and projections.
- ml-foundations/chapters/06-matrices.html · ch 06 · deep · Matrices as Functions: Matrix multiplication as composing transformations, shapes as contracts, and inverses.
- ml-foundations/chapters/07-decompositions.html · ch 07 · deep · Eigenvectors, SVD & Low Rank: Eigenvectors, the singular value decomposition and why low-rank structure is everywhere.
Part 3: Calculus & Optimisation
- ml-foundations/chapters/08-derivatives.html · ch 08 · deep · Derivatives & the Chain Rule: Slopes, partial derivatives, gradients and the one rule that makes deep learning possible.
- ml-foundations/chapters/09-autodiff.html · ch 09 · deep · Automatic Differentiation: Computation graphs, forward and reverse mode, and a tiny autograd engine built by hand.
- ml-foundations/chapters/10-optimisers.html · ch 10 · deep · Gradient Descent & Optimisers: Learning rates, SGD, momentum, Adam and AdamW, schedules and what can go wrong.
- ml-foundations/chapters/11-numerics.html · ch 11 · core · Floating Point & Numerical Stability: How floats work, overflow and underflow, stable softmax, and fp16, bf16 and fp8.
Part 4: Probability & Information
- ml-foundations/chapters/12-probability.html · ch 12 · deep · Probability, Distributions & Sampling: Random variables, common distributions, expectation, Bayes' rule and sampling.
- ml-foundations/chapters/13-likelihood-losses.html · ch 13 · deep · Maximum Likelihood & Loss Functions: Why squared error and cross-entropy are not arbitrary: they are likelihoods in disguise.
- ml-foundations/chapters/14-information-theory.html · ch 14 · deep · Entropy, Cross-Entropy & KL Divergence: Surprise, bits, perplexity and the divergence that appears in every post-training method.
- ml-foundations/chapters/15-statistics.html · ch 15 · deep · Statistics for Experiments: Confidence intervals, the bootstrap, hypothesis tests, power and the peeking trap.
Part 5: Working Practice
- ml-foundations/chapters/16-reading-papers.html · ch 16 · core · Reading Papers Efficiently: A three-pass method, what to skip, how to check claims and how to reproduce a result.
- ml-foundations/chapters/17-compute-costs.html · ch 17 · core · GPUs, Clouds & What Compute Costs: What a GPU is good at, memory versus FLOPs, renting hardware and estimating a bill.
- ml-foundations/chapters/18-technical-writing.html · ch 18 · core · Writing for Engineers: Design docs, experiment reports and error-analysis memos that people actually read.
- ml-foundations/chapters/19-ai-assistants.html · ch 19 · intro · Learning with AI Assistants: Using coding assistants to go faster without outsourcing the understanding.
Labs:
- ml-foundations/labs/lab-01-linalg.html · L1 (after Part 2) · A Small Linear Algebra Library: Vectors, matrix multiply, transpose, Gram-Schmidt and power iteration, tested against hand values.
- ml-foundations/labs/lab-02-autograd.html · L2 (after Part 3) · Build an Autograd Engine: A scalar Value class with reverse-mode autodiff, checked against numerical gradients.
- ml-foundations/labs/lab-03-optimisers.html · L3 (after Part 3) · The Optimiser Race: SGD, momentum, RMSProp, Adam and AdamW on classic test surfaces, with schedules and clipping.
- ml-foundations/labs/lab-04-likelihood.html · L4 (after Part 4) · Sampling, Likelihood & Entropy: Samplers, maximum-likelihood fits, stable log-softmax, temperature, entropy and KL.
- ml-foundations/labs/lab-05-statistics.html · L5 (after Part 4) · A Statistics Toolkit for Experiments: Bootstrap intervals, permutation tests, power by simulation and a demonstration of peeking.
Cases:
- ml-foundations/cases/case-01-reinhart-rogoff.html · C1 · A Spreadsheet Error That Shaped Policy [Reproducible analysis]: An influential economics result that a student could not reproduce, and what the spreadsheet hid.
- ml-foundations/cases/case-02-patriot-missile.html · C2 · The Patriot Missile Clock [Floating-point drift]: A tiny rounding error, accumulated over 100 hours of uptime, and a missed interception.
- ml-foundations/cases/case-03-adamw.html · C3 · AdamW: Weight Decay Done Right [Optimiser details matter]: Why L2 regularisation and weight decay stop being the same thing inside Adam.
- ml-foundations/cases/case-04-mixed-precision.html · C4 · Mixed-Precision Training [Fewer bits, same model]: Half-precision arithmetic, loss scaling and master weights: how training got twice as cheap.
- ml-foundations/cases/case-05-peeking.html · C5 · Peeking at A/B Tests [Valid stopping rules]: Why checking a running experiment every day inflates false positives, and how sequential tests fix it.
Studios:
- ml-foundations/studios/studio-01-experiment-design.html · S1 (after Part 4) · Design an Experiment That Can Fail: Decide whether a change really helped: metric, sample size, stopping rule and what would change your mind.
- ml-foundations/studios/studio-02-compute-budget.html · S2 (after Part 5) · Budget the Compute for a Project: Turn a research plan into GPU-hours, memory, storage and a bill, with the risky assumptions named.
Toolbox (ml-foundations/toolbox.html#id):
- #jupyter · Jupyter & notebooks · chapters 01,03,04: Interactive exploration, and the discipline that keeps notebooks reproducible.
- #numpy · NumPy · chapters 02,05,06,07: The array library underneath almost every numerical Python tool.
- #pandas · pandas & DuckDB · chapters 03: Tables in memory, and SQL over files without a server.
- #uv · uv & virtual environments · chapters 04: Fast, pinned, reproducible Python environments.
- #plotting · matplotlib · chapters 03,12,15: Plots that answer a question, and the habit of looking at your data.
- #free-gpus · Colab & Kaggle notebooks · chapters 17: Free and cheap GPUs for learning, and their limits.
- #papers · arXiv, Semantic Scholar & Papers with Code · chapters 16: Finding, tracking and checking papers and their code.

## A1 · Machine Learning & Data Science  (id "ml", folder ml/)

Part 0: Orientation
- ml/chapters/00-start-here.html · ch 00 · intro · Start Here: Learning from examples, the data-science loop, and where this course fits.
Part 1: Framing Problems
- ml/chapters/01-generalisation.html · ch 01 · deep · What Learning Is: Generalisation: Training, validation and test sets, overfitting, underfitting and the no-free-lunch idea.
- ml/chapters/02-framing-metrics.html · ch 02 · deep · Framing Problems & Choosing Metrics: Turning a business question into a prediction task with a metric that matches the cost of errors.
- ml/chapters/03-eda.html · ch 03 · core · Exploratory Data Analysis: Distributions, missingness, duplicates, shifts between train and test, and the questions to ask first.
- ml/chapters/04-baselines.html · ch 04 · core · Baselines First: Majority class, simple rules and linear models: the numbers every fancy model must beat.
Part 2: Core Models
- ml/chapters/05-linear-models.html · ch 05 · deep · Linear & Logistic Regression: Fitting lines and probabilities, gradient descent, and reading coefficients carefully.
- ml/chapters/06-regularisation.html · ch 06 · deep · Regularisation & the Bias-Variance Trade-off: Why simpler models generalise, L1 and L2 penalties, and learning curves.
- ml/chapters/07-neighbours-bayes.html · ch 07 · core · Nearest Neighbours, Naive Bayes & Kernels: Similarity-based and probabilistic classifiers, and the kernel trick in one picture.
- ml/chapters/08-decision-trees.html · ch 08 · deep · Decision Trees: Splits, impurity, depth, and why a single tree is both readable and unstable.
- ml/chapters/09-ensembles-boosting.html · ch 09 · deep · Random Forests & Gradient Boosting: Bagging, boosting, XGBoost, LightGBM and CatBoost: why boosted trees rule tabular data.
Part 3: Unsupervised Learning
- ml/chapters/10-clustering.html · ch 10 · core · Clustering: k-means, hierarchical clustering and DBSCAN, and how to tell whether clusters are real.
- ml/chapters/11-dimensionality-reduction.html · ch 11 · core · Dimensionality Reduction: PCA, t-SNE and UMAP: compressing and visualising high-dimensional data honestly.
- ml/chapters/12-anomaly-detection.html · ch 12 · core · Anomaly Detection: Statistical, distance-based and isolation methods for finding the rare and the strange.
Part 4: Validation & Trust
- ml/chapters/13-cross-validation.html · ch 13 · deep · Cross-Validation Done Right: k-fold, grouped, stratified and time-based splits that mirror how the model will be used.
- ml/chapters/14-leakage.html · ch 14 · deep · Leakage: The Silent Killer: Target leakage, train-test contamination and preprocessing leaks, and how to hunt them.
- ml/chapters/15-imbalance-calibration.html · ch 15 · deep · Imbalance, Thresholds & Calibration: Rare positives, precision-recall trade-offs, choosing thresholds by cost, and calibrated probabilities.
- ml/chapters/16-interpretability.html · ch 16 · core · Interpreting Models: Permutation importance, partial dependence and SHAP, and what explanations cannot tell you.
Part 5: Features & Competitions
- ml/chapters/17-feature-engineering.html · ch 17 · deep · Feature Engineering: Encodings, aggregates, interactions, target encoding done safely, and features from domain knowledge.
- ml/chapters/18-time-series.html · ch 18 · core · Time Series Forecasting: Trend, seasonality, lag features, backtesting and the forecasting baselines that are hard to beat.
- ml/chapters/19-tabular-deep-learning.html · ch 19 · intro · Tabular Deep Learning & Foundation Models: Neural nets for tables, TabPFN-style foundation models, and when they beat boosted trees.
- ml/chapters/20-competitions.html · ch 20 · core · How Competitions Are Won: Validation strategy, diverse models, stacking and the habits competition winners describe.
Part 6: From Model to Value
- ml/chapters/21-model-to-value.html · ch 21 · core · From Model to Value: Offline metrics versus business outcomes, A/B tests, monitoring, drift and retraining.
Labs:
- ml/labs/lab-01-linear-models.html · L1 (after Part 2) · Linear & Logistic Regression from Scratch: Closed form and gradient descent, L1 and L2 penalties, and log-loss, all checked against hand values.
- ml/labs/lab-02-trees-boosting.html · L2 (after Part 2) · Trees & Gradient Boosting from Scratch: A CART tree, a random forest and a gradient-boosting regressor in plain Python.
- ml/labs/lab-03-unsupervised.html · L3 (after Part 3) · k-means, PCA & Anomalies: k-means++ with restarts, PCA by power iteration, and an isolation-style anomaly score.
- ml/labs/lab-04-leakage-hunt.html · L4 (after Part 4) · The Leakage Hunt: Build a validation harness that catches four planted leaks, including one in preprocessing.
- ml/labs/lab-05-calibration.html · L5 (after Part 4) · Thresholds & Calibration: PR curves, cost-based thresholds, reliability diagrams, Platt scaling and isotonic regression.
- ml/labs/lab-06-features-stacking.html · L6 (after Part 5) · Feature Pipelines & Stacking: Leak-safe target encoding, out-of-fold predictions and a stacked ensemble that beats its parts.
Cases:
- ml/cases/case-01-netflix-prize.html · C1 · The Netflix Prize [Ensembles vs deployability]: A million-dollar ensemble that won the competition and was never fully deployed.
- ml/cases/case-02-google-flu-trends.html · C2 · Google Flu Trends [Drift and spurious features]: Search queries that predicted flu, until they did not, and what the post-mortems found.
- ml/cases/case-03-zillow-offers.html · C3 · Zillow Offers [Model risk in a business]: An algorithmic home-buying business that shut down after its price forecasts met a turning market.
- ml/cases/case-04-amazon-recruiting.html · C4 · A Recruiting Model That Learned Bias [Biased labels]: A CV-screening model trained on past hiring decisions, and why removing words did not fix it.
- ml/cases/case-05-xgboost.html · C5 · XGBoost: A System, Not Just an Algorithm [Engineering wins benchmarks]: Sparsity-aware splits, cache-aware blocks and out-of-core training behind a competition favourite.
- ml/cases/case-06-competition-leaks.html · C6 · Leaks That Won Competitions [Leakage]: Row orders, IDs and timestamps that gave away the answer, and how organisers learned to prevent them.
- ml/cases/case-07-compas.html · C7 · COMPAS and Competing Definitions of Fair [Calibration vs error balance]: A risk score that was calibrated and still unequal in its errors, and why both sides were right.
Studios:
- ml/studios/studio-01-churn.html · S1 (after Part 1) · Frame a Churn Prediction Problem: From 'reduce churn' to a target, a prediction window, a metric, a baseline and an action.
- ml/studios/studio-02-fraud.html · S2 (after Part 4) · Design a Fraud Detection Model: Rare positives, delayed labels, adversaries and a review queue with limited capacity.
- ml/studios/studio-03-forecasting.html · S3 (after Part 5) · Design Demand Forecasting for a Retailer: Thousands of products, promotions, stockouts and the decision the forecast feeds.
Toolbox (ml/toolbox.html#id):
- #sklearn · scikit-learn · chapters 04,05,06,07,10,11,13: The reference library for classical ML, with a consistent fit/predict interface.
- #gbdt · XGBoost, LightGBM & CatBoost · chapters 09,17,20: The three boosted-tree libraries that dominate tabular problems.
- #shap · SHAP · chapters 16: Per-prediction feature attributions, and plots to read them with care.
- #tracking · MLflow & Weights & Biases · chapters 13,21: Log every run's parameters, metrics and artefacts so results can be compared and reproduced.
- #kaggle · Kaggle · chapters 20: Competitions, datasets, notebooks with free GPUs, and the forums where winners explain themselves.
- #evidently · Drift monitoring tools · chapters 21: Compare live data with training data and alert on shifts.

## A2 · Deep Learning & Transformers  (id "dl", folder deep-learning/)

Part 0: Orientation
- deep-learning/chapters/00-start-here.html · ch 00 · intro · Start Here: What deep learning is, what changed in 2012 and 2017, and the road to building a GPT.
Part 1: Neural Networks
- deep-learning/chapters/01-neurons-layers.html · ch 01 · deep · Neurons, Layers & Activations: Weighted sums, non-linearities, layers and why depth helps.
- deep-learning/chapters/02-backpropagation.html · ch 02 · deep · Backpropagation Through a Network: The chain rule applied to whole layers: matrix gradients, by hand and in code.
- deep-learning/chapters/03-training-dynamics.html · ch 03 · deep · Initialisation, Normalisation & Residuals: Vanishing and exploding signals, careful initialisation, LayerNorm and skip connections.
- deep-learning/chapters/04-deep-regularisation.html · ch 04 · core · Regularising Deep Networks: Weight decay, dropout, data augmentation, early stopping and the strange case of double descent.
- deep-learning/chapters/05-pytorch.html · ch 05 · core · PyTorch as an Autodiff Engine: Tensors, autograd, modules, optimisers and the standard training loop.
Part 2: Representation
- deep-learning/chapters/06-embeddings.html · ch 06 · deep · Embeddings: Words as Vectors: One-hot to dense vectors, word2vec, and why meaning becomes geometry.
- deep-learning/chapters/07-convolutions.html · ch 07 · core · Convolutions & Images: Filters, weight sharing, pooling and the ideas from vision that carried over.
- deep-learning/chapters/08-sequences-rnns.html · ch 08 · core · Sequences & Recurrent Networks: RNNs and LSTMs, the bottleneck of a single hidden state, and why they gave way to attention.
Part 3: Attention & the Transformer
- deep-learning/chapters/09-attention.html · ch 09 · deep · Attention from First Principles: Queries, keys and values, scaled dot products, softmax weights, masking and multiple heads.
- deep-learning/chapters/10-transformer-block.html · ch 10 · deep · The Transformer Block: Attention, MLPs, residual streams and normalisation, assembled and explained.
- deep-learning/chapters/11-positions.html · ch 11 · core · Positional Information: Why attention needs positions: learned, sinusoidal, relative and rotary (RoPE) encodings.
- deep-learning/chapters/12-building-gpt.html · ch 12 · deep · Building a GPT: A decoder-only Transformer, end to end, trained on characters and read line by line.
Part 4: Tokens & Language Modelling
- deep-learning/chapters/13-tokenisation.html · ch 13 · deep · Tokenisation: Characters, bytes and byte-pair encoding, vocabulary size, and the bugs tokenisers cause.
- deep-learning/chapters/14-language-modelling.html · ch 14 · deep · The Language-Modelling Objective: Next-token prediction, cross-entropy, perplexity and what a model learns from it.
- deep-learning/chapters/15-decoding.html · ch 15 · core · Decoding Strategies: Greedy, temperature, top-k, top-p, beam search and constrained decoding.
Part 5: Training at Scale
- deep-learning/chapters/16-resource-accounting.html · ch 16 · deep · Parameters, FLOPs & Memory: Counting a model's parameters, the 6ND rule, activation memory and what fits on a GPU.
- deep-learning/chapters/17-training-stability.html · ch 17 · core · Mixed Precision & Training Stability: bf16 training, loss spikes, gradient clipping, learning-rate warmup and what logs to watch.
- deep-learning/chapters/18-scaling-laws.html · ch 18 · core · Scaling Laws: Loss as a power law of compute, data and parameters, and the compute-optimal recipe.
Part 6: Modern Architectures
- deep-learning/chapters/19-efficient-attention.html · ch 19 · core · Efficient Attention: Multi-query and grouped-query attention, sliding windows and FlashAttention's memory trick.
- deep-learning/chapters/20-mixture-of-experts.html · ch 20 · intro · Mixture of Experts: Routing tokens to a few of many experts: more parameters for the same compute, and the catches.
- deep-learning/chapters/21-vision-language.html · ch 21 · core · Vision-Language Models: Patches, image encoders, projectors and how a language model learns to read a picture.
- deep-learning/chapters/22-beyond-attention.html · ch 22 · intro · Beyond Attention: State-space models, linear attention and hybrids, and what they trade away.
Labs:
- deep-learning/labs/lab-01-mlp.html · L1 (after Part 1) · A Neural Network from Scratch: Matrix ops, a two-layer network, backprop by hand and a training loop on a toy dataset.
- deep-learning/labs/lab-02-embeddings.html · L2 (after Part 2) · Word Embeddings: Skip-gram with negative sampling on a small corpus, then nearest neighbours and analogies.
- deep-learning/labs/lab-03-attention.html · L3 (after Part 3) · Attention & a Transformer Block: Scaled dot-product attention, causal masks, multi-head attention and a block, checked shape by shape.
- deep-learning/labs/lab-04-tiny-gpt.html · L4 (after Part 3) · Train a Tiny GPT: A character-level GPT in pure Python, trained until it invents plausible names.
- deep-learning/labs/lab-05-tokeniser.html · L5 (after Part 4) · A BPE Tokeniser & Decoders: Train byte-pair encoding, round-trip any text, then implement greedy, top-k and top-p sampling.
- deep-learning/labs/lab-06-resources.html · L6 (after Part 5) · The Model Resource Calculator: Parameters, FLOPs, memory and compute-optimal sizes for real published models.
Cases:
- deep-learning/cases/case-01-alexnet.html · C1 · AlexNet and ImageNet, 2012 [Data + compute + method]: Two GPUs, a big labelled dataset and ReLUs: the result that restarted neural networks.
- deep-learning/cases/case-02-transformer.html · C2 · Attention Is All You Need [Parallel sequence models]: The 2017 translation paper whose architecture now runs nearly every frontier model.
- deep-learning/cases/case-03-gpt-scaling.html · C3 · From GPT-2 to GPT-3 [Scale changes behaviour]: A language model that learned tasks nobody trained it for, and the in-context learning surprise.
- deep-learning/cases/case-04-chinchilla.html · C4 · Chinchilla: Compute-Optimal Training [Balance data and size]: Why a smaller model trained on more tokens beat a model four times its size.
- deep-learning/cases/case-05-flashattention.html · C5 · FlashAttention [IO-aware algorithms]: Same maths, far less memory traffic: an exact attention kernel that changed context lengths.
- deep-learning/cases/case-06-glitch-tokens.html · C6 · SolidGoldMagikarp: Glitch Tokens [Tokeniser-model mismatch]: Tokens that existed in the vocabulary but almost never in training, and the odd behaviour they caused.
- deep-learning/cases/case-07-opt-logbook.html · C7 · Training OPT-175B: The Logbook [Operating a training run]: A public diary of restarts, loss spikes and hardware failures in a large training run.
Studios:
- deep-learning/studios/studio-01-debug-training.html · S1 (after Part 5) · Debug a Training Run That Will Not Learn: Flat loss, then a spike, then NaNs: find the causes in order, with the evidence for each.
- deep-learning/studios/studio-02-small-model-plan.html · S2 (after Part 6) · Plan a Small Model on a Budget: Pick size, tokens, context length and architecture for a domain model with a fixed GPU budget.
Toolbox (deep-learning/toolbox.html#id):
- #pytorch · PyTorch · chapters 05,12: The deep-learning framework this course's chapters use, from tensors to training loops.
- #nanogpt · nanoGPT, nanochat & minGPT · chapters 12,14,16: Karpathy's small, readable GPT implementations to train and modify.
- #tokenisers · Tokeniser playgrounds · chapters 13: See exactly how text becomes tokens, and compare tokenisers side by side.
- #tensorboard · TensorBoard & W&B · chapters 03,17: Watch loss, gradients and activations while a model trains.
- #profiler · PyTorch profiler · chapters 16,19: Find where the time and memory of a training step actually go.
- #colab · Free GPU notebooks · chapters 05,12: Run the chapters' PyTorch code on a free GPU when your laptop is too slow.

## A3 · Training, Post-training & Serving LLMs  (id "llm", folder llm-training/)

Part 0: Orientation
- llm-training/chapters/00-start-here.html · ch 00 · intro · Start Here: Base models, chat models and reasoning models, and the stages that make each.
Part 1: Pretraining Systems
- llm-training/chapters/01-pretraining-data.html · ch 01 · deep · Pretraining Data: Crawling, extracting, filtering, deduplicating and mixing trillions of tokens.
- llm-training/chapters/02-gpu-memory.html · ch 02 · deep · GPU Memory & Why Training Runs Out of It: Weights, gradients, optimiser state and activations, and the tricks that trade compute for memory.
- llm-training/chapters/03-parallelism.html · ch 03 · core · Parallel Training: Data, tensor, pipeline and sequence parallelism, ZeRO and FSDP, and the communication each costs.
- llm-training/chapters/04-kernels.html · ch 04 · intro · Kernels & Performance: Why a fused kernel beats three small ones, and a first look at Triton.
- llm-training/chapters/05-long-runs.html · ch 05 · core · Checkpoints, Failures & Long Runs: Hardware failures, checkpointing, restarts and monitoring a run that lasts for weeks.
Part 2: Reinforcement Learning Foundations
- llm-training/chapters/06-bandits-mdps.html · ch 06 · core · Bandits & Markov Decision Processes: Rewards, exploration versus exploitation, states, actions, returns and discounting.
- llm-training/chapters/07-policy-gradients.html · ch 07 · deep · Policy Gradients: REINFORCE derived step by step, baselines and why variance is the enemy.
- llm-training/chapters/08-ppo.html · ch 08 · deep · PPO & KL Penalties: Clipped objectives, trust regions and the KL leash that keeps a fine-tuned model sane.
- llm-training/chapters/09-value-functions.html · ch 09 · core · Value Functions & Advantage: Critics, temporal-difference learning and generalised advantage estimation.
Part 3: Post-training
- llm-training/chapters/10-sft.html · ch 10 · deep · Supervised Fine-Tuning: Instruction data, chat templates, loss masking, data quality and catastrophic forgetting.
- llm-training/chapters/11-lora.html · ch 11 · deep · LoRA, QLoRA & Parameter-Efficient Tuning: Low-rank updates, why they work, rank and alpha, and fine-tuning in 4-bit.
- llm-training/chapters/12-preference-optimisation.html · ch 12 · deep · Preference Optimisation: RLHF & DPO: Learning from comparisons: the RLHF pipeline, the DPO derivation and their relatives.
- llm-training/chapters/13-reward-models.html · ch 13 · core · Reward Models & Reward Hacking: Training reward models, over-optimisation, sycophancy and Goodhart's law in practice.
- llm-training/chapters/14-rlvr-grpo.html · ch 14 · deep · RL with Verifiable Rewards & GRPO: Checkable rewards, group-relative advantages and how reasoning models are trained.
- llm-training/chapters/15-distillation.html · ch 15 · core · Distillation & Synthetic Data: Teaching small models with big ones, logit distillation, synthetic data and model collapse.
Part 4: Cheap Adaptation
- llm-training/chapters/16-model-merging.html · ch 16 · core · Model Merging & Evolutionary Merging: Averaging weights, task vectors, TIES and DARE, and searching for merge recipes by evolution.
- llm-training/chapters/17-adapters-on-demand.html · ch 17 · intro · Adapters on Demand: Self-adaptive models and hypernetworks that generate adapters from a task description.
Part 5: Inference
- llm-training/chapters/18-kv-cache.html · ch 18 · deep · The KV Cache & the Cost of Decoding: Prefill versus decode, why generation is memory-bound, and what the cache costs.
- llm-training/chapters/19-quantisation.html · ch 19 · core · Quantisation: int8, int4 and fp8, per-channel scales, outliers, GPTQ and AWQ, and measuring the damage.
- llm-training/chapters/20-serving-engines.html · ch 20 · deep · Serving Engines: Continuous batching, paged attention, prefix caching and how vLLM and SGLang work.
- llm-training/chapters/21-speculative-decoding.html · ch 21 · intro · Speculative Decoding & Other Speedups: Draft and verify, Medusa-style heads, and why the output is unchanged.
- llm-training/chapters/22-token-economics.html · ch 22 · core · The Economics of a Token: Throughput, latency, batch size and price: what a million tokens costs to serve.
Part 6: Judging Models
- llm-training/chapters/23-evaluating-models.html · ch 23 · core · Evaluating a Model You Trained: Held-out sets, evaluation harnesses, contamination checks and regressions on other skills.
Labs:
- llm-training/labs/lab-01-data-pipeline.html · L1 (after Part 1) · A Pretraining Data Pipeline: Extract, filter by quality heuristics and deduplicate with MinHash and locality-sensitive hashing.
- llm-training/labs/lab-02-policy-gradient.html · L2 (after Part 2) · Policy Gradients & PPO: REINFORCE with a baseline, then PPO's clipped objective with a KL penalty, on bandits and a gridworld.
- llm-training/labs/lab-03-lora.html · L3 (after Part 3) · LoRA from Scratch: Freeze a small model, train low-rank adapters, merge them back and compare parameter counts.
- llm-training/labs/lab-04-dpo-grpo.html · L4 (after Part 3) · DPO & GRPO on a Toy Policy: Implement both losses on a policy over answers to arithmetic questions with a verifiable reward.
- llm-training/labs/lab-05-evolutionary-merge.html · L5 (after Part 4) · Evolutionary Model Merging: Merge task-specialised small models and evolve merge coefficients against a held-out task.
- llm-training/labs/lab-06-serving-sim.html · L6 (after Part 5) · A Serving Simulator: Simulate static and continuous batching with a paged KV cache, and measure throughput and latency.
- llm-training/labs/lab-07-quantisation.html · L7 (after Part 5) · Quantise a Model: Symmetric and asymmetric int8 and int4, per-channel scales and outlier handling, with error measured.
Cases:
- llm-training/cases/case-01-instructgpt.html · C1 · InstructGPT: RLHF in Practice [Learning from human preferences]: A smaller model that labellers preferred to one a hundred times larger.
- llm-training/cases/case-02-deepseek-r1.html · C2 · DeepSeek-R1 [RL with verifiable rewards]: Reasoning that emerged from reinforcement learning on checkable problems, then distilled into small models.
- llm-training/cases/case-03-llama3-training.html · C3 · Training Llama 3 at Scale [Reliability of training clusters]: Thousands of GPUs, hundreds of interruptions and the engineering that kept the run on track.
- llm-training/cases/case-04-vllm.html · C4 · vLLM and PagedAttention [Virtual memory for the KV cache]: Borrowing operating-system paging to stop wasting most of a GPU's cache memory.
- llm-training/cases/case-05-evolutionary-merge.html · C5 · Evolving Model Merges [Search over recipes]: Evolutionary search that combined existing open models into new capabilities without gradient training.
- llm-training/cases/case-06-sycophancy-rollback.html · C6 · The Sycophancy Rollback [Reward signals with side effects]: A model update that became too eager to please, and what its developer said went wrong.
- llm-training/cases/case-07-alpaca.html · C7 · Alpaca & Self-Instruct [Distillation from a stronger model]: Fifty-two thousand generated instructions, a few hundred dollars and a lesson about imitation.
Studios:
- llm-training/studios/studio-01-domain-adaptation.html · S1 (after Part 3) · Adapt a Model for a Specialist Domain: Prompting, retrieval, fine-tuning or all three, under a fixed budget, with the evaluation that decides.
- llm-training/studios/studio-02-reasoning-model.html · S2 (after Part 3) · Post-train a Small Reasoning Model: Pick the base model, reward, data and compute, and plan how you will catch reward hacking.
- llm-training/studios/studio-03-serving-platform.html · S3 (after Part 5) · Design an LLM Serving Platform: Many models, many tenants, latency targets and a GPU bill: batching, routing, caching and autoscaling.
Toolbox (llm-training/toolbox.html#id):
- #hf · Hugging Face transformers, TRL & PEFT · chapters 10,11,12,14: Load models, fine-tune with LoRA and run SFT, DPO and GRPO trainers.
- #unsloth · Unsloth · chapters 11,14: Memory-efficient fine-tuning and RL that fits on a single consumer or free GPU.
- #vllm · vLLM & SGLang · chapters 18,20,22: High-throughput open-source serving engines.
- #llamacpp · llama.cpp & Ollama · chapters 19: Run quantised models locally on a laptop CPU or GPU.
- #lm-eval · lm-evaluation-harness · chapters 23: Run standard benchmarks on any model the same way every time.
- #nvidia-smi · nvidia-smi & nvtop · chapters 02,05: See GPU memory, utilisation and temperature while something runs.

## A4 · Agents, Tools & Protocols  (id "agt", folder agents/)

Part 0: Orientation
- agents/chapters/00-start-here.html · ch 00 · intro · Start Here: Workflows versus agents, why agents fail, and the shape of this course.
Part 1: The Loop
- agents/chapters/01-model-apis.html · ch 01 · core · Talking to a Model: Messages and roles, system prompts, parameters, streaming and structured output.
- agents/chapters/02-tool-loop.html · ch 02 · deep · Tool Calling: The Agent Loop: Tool definitions, tool_use and tool_result turns, stop conditions and iteration budgets.
- agents/chapters/03-reasoning-planning.html · ch 03 · core · Reasoning, ReAct & Planning: Thought-action-observation, plan-then-execute, reflection and what reasoning models change.
- agents/chapters/04-prompting.html · ch 04 · core · Prompting as Programming: Clear instructions, examples, delimiters and prompts you can test, version and review.
Part 2: Tools & Protocols
- agents/chapters/05-tool-design.html · ch 05 · deep · Designing Tools for Agents: The agent-computer interface: names, descriptions, arguments, errors and output size.
- agents/chapters/06-function-calling.html · ch 06 · core · Function Calling Across Providers: JSON Schema contracts, parallel calls, forced tools and a provider-neutral adapter.
- agents/chapters/07-mcp.html · ch 07 · deep · MCP from the Wire Up: JSON-RPC messages, tools, resources and prompts, and a server written by hand.
- agents/chapters/08-mcp-production.html · ch 08 · core · MCP in Production: Transports, authorisation, versions and the stateless redesign, and how to survive spec changes.
- agents/chapters/09-agent-to-agent.html · ch 09 · core · Agent-to-Agent Protocols: Agent cards, tasks and delegation with A2A, and when agents should talk to agents at all.
Part 3: Context & Memory
- agents/chapters/10-context-engineering.html · ch 10 · deep · Context Engineering: Context as a budget: selection, compaction, just-in-time retrieval and context rot.
- agents/chapters/11-memory.html · ch 11 · core · Memory: Notes, Retrieval & Skills: Scratchpads, notes files, episodic and semantic memory, and libraries of reusable skills.
- agents/chapters/12-long-context.html · ch 12 · core · Long Context versus Retrieval: When to put everything in the window, when to retrieve, and how to measure the difference.
Part 4: Workflows & Teams
- agents/chapters/13-workflow-patterns.html · ch 13 · deep · Workflow Patterns: Chaining, routing, parallelising, orchestrator-workers and evaluator-optimiser loops as plain code.
- agents/chapters/14-multi-agent.html · ch 14 · deep · Multi-Agent Systems: Orchestrators and sub-agents, token costs, coordination failures and when one agent is better.
- agents/chapters/15-durable-execution.html · ch 15 · deep · Durable Execution for Agents: Event logs, checkpoints, idempotent side effects, resumption and human approval gates.
Part 5: Foundational Agents
- agents/chapters/16-deep-research.html · ch 16 · deep · Deep Research Agents: Planning, parallel search, reading, cross-checking, citing and synthesising a long report.
- agents/chapters/17-computer-use.html · ch 17 · deep · Computer-Use & Browser Agents: Screenshots versus accessibility trees, coordinates, actions, verification and safety.
- agents/chapters/18-coding-agents.html · ch 18 · core · Coding Agents: How SWE-agent, OpenHands and terminal coding agents read, edit, run and test code.
Part 6: Security & Engineering
- agents/chapters/19-agent-security.html · ch 19 · deep · Agent Security: Prompt injection, tool poisoning, data exfiltration and the lethal trifecta.
- agents/chapters/20-sandboxing.html · ch 20 · core · Sandboxes & Permissions: Containers, virtual machines, network allow-lists, least privilege and confirmation prompts.
- agents/chapters/21-frameworks.html · ch 21 · core · Agent Frameworks: What frameworks give you, what they hide, and how to choose one you can leave.
- agents/chapters/22-ai-coding-tools.html · ch 22 · deep · Working with AI Coding Tools: Instruction files, plans, verification loops, review and measuring whether it actually helps.
Labs:
- agents/labs/lab-01-agent-loop.html · L1 (after Part 1) · The Agent Loop from Scratch: Messages, tool schemas and a tool-calling loop with budgets, logging and a scripted fake model.
- agents/labs/lab-02-tool-design.html · L2 (after Part 2) · Tool Design, Measured: Two designs of the same toolset, a twenty-task evaluation and the numbers that pick the winner.
- agents/labs/lab-03-mcp.html · L3 (after Part 2) · An MCP Server & Client: JSON-RPC over stdio: initialise, list and call tools, resources and errors, both sides by hand.
- agents/labs/lab-04-workflows.html · L4 (after Part 4) · Workflow Patterns & Budgets: Chains, routers, parallel fan-out and orchestrator-workers, with token accounting for each.
- agents/labs/lab-05-durable-agent.html · L5 (after Part 4) · A Durable Agent: An event-sourced agent that survives being killed mid-task without repeating side effects.
- agents/labs/lab-06-deep-research.html · L6 (after Part 5) · A Mini Deep-Research Agent: Plan, search a local corpus, read, cite and verify every claim against its source.
- agents/labs/lab-07-injection.html · L7 (after Part 6) · Attack & Defend a Tool-Using Agent: Plant injections in documents and tool output, then measure which defences actually hold.
Cases:
- agents/cases/case-01-multi-agent-research.html · C1 · A Multi-Agent Research System [Orchestrator-workers]: Anthropic's write-up of a lead agent spawning researchers, and what token usage explained.
- agents/cases/case-02-swe-agent.html · C2 · SWE-agent and the Agent-Computer Interface [Tools shaped for models]: Why a purpose-built file viewer and editor beat a raw shell for a coding agent.
- agents/cases/case-03-metr-rct.html · C3 · Measuring AI Coding Productivity [Measure, don't assume]: A randomised trial in which experienced developers were slower with AI and believed they were faster.
- agents/cases/case-04-mcp-evolution.html · C4 · How MCP Changed, 2024 to 2026 [Protocols evolve]: From a local stdio protocol to remote servers, OAuth and a stateless redesign.
- agents/cases/case-05-injection-wild.html · C5 · Prompt Injection in the Wild [Untrusted input as instructions]: Exfiltration through assistants and MCP servers: real incidents and the common thread.
- agents/cases/case-06-replit-database.html · C6 · The Agent That Deleted Production [Least privilege for agents]: A coding agent with production access, a code freeze it ignored, and the safeguards added afterwards.
- agents/cases/case-07-computer-use.html · C7 · Teaching Models to Use Computers [Pixels as an interface]: Screenshot-driven agents, the OSWorld benchmark and why progress is measured in steps.
Studios:
- agents/studios/studio-01-support-agent.html · S1 (after Part 4) · Design a Customer-Support Agent: Answers, account lookups and refunds with limits, escalation to humans and an audit trail.
- agents/studios/studio-02-research-product.html · S2 (after Part 5) · Design a Deep-Research Product: Long-running research jobs with citations, cost controls, progress updates and quality checks.
- agents/studios/studio-03-regulated-agent.html · S3 (after Part 6) · Design an Agent for a Regulated Back Office: Documents in, decisions out, with a threat model, approvals and evidence an auditor accepts.
Toolbox (agents/toolbox.html#id):
- #coding-agents · Claude Code, Codex CLI & Cursor · chapters 18,22: Terminal and editor coding agents, and how to configure them for a repository.
- #mcp-inspector · MCP Inspector · chapters 07,08: Connect to any MCP server and call its tools by hand.
- #sdks · Provider SDKs & agent SDKs · chapters 01,02,06,21: Official client libraries and agent SDKs, and what they do for you.
- #llm-cli · The llm command-line tool · chapters 01,04: Prompt many models from a terminal and log every response to SQLite.
- #playwright · Playwright · chapters 17: Drive a real browser from code: the substrate of many browser agents.
- #containers · Docker sandboxes · chapters 20,18: Give an agent a disposable machine with only the access it needs.

## A5 · Retrieval, Search & Document AI  (id "ret", folder retrieval/)

Part 0: Orientation
- retrieval/chapters/00-start-here.html · ch 00 · intro · Start Here: Search, retrieval and RAG, and the documents they have to cope with.
Part 1: Lexical Search
- retrieval/chapters/01-text-analysis.html · ch 01 · core · Text Analysis: Tokenising, normalising, stemming and analysers, and why index and query must agree.
- retrieval/chapters/02-bm25.html · ch 02 · deep · Inverted Indexes & BM25: Postings, term frequency, document frequency and length normalisation, derived and tuned.
- retrieval/chapters/03-query-understanding.html · ch 03 · core · Query Understanding: Spelling correction, synonyms, expansion, intent and the long tail of queries.
Part 2: Measuring Retrieval
- retrieval/chapters/04-relevance-metrics.html · ch 04 · deep · Relevance Metrics: Precision, recall, MRR, MAP and nDCG: what each rewards and which question it answers.
- retrieval/chapters/05-test-collections.html · ch 05 · deep · Building a Test Collection: Queries, judgements, pooling and guidelines: a gold set you can trust in a week.
- retrieval/chapters/06-retrieval-benchmarks.html · ch 06 · core · Public Benchmarks & Their Limits: BEIR, MTEB and domain benchmarks as shortlist filters, not decisions.
Part 3: Dense Retrieval
- retrieval/chapters/07-dense-retrieval.html · ch 07 · deep · Dense Retrieval: Bi-encoders, contrastive training, hard negatives and fine-tuning an embedder.
- retrieval/chapters/08-rerankers.html · ch 08 · core · Rerankers: Cross-encoders and LLM rerankers: precision at the top for a price.
- retrieval/chapters/09-late-interaction-sparse.html · ch 09 · core · Late Interaction & Learned Sparse: ColBERT's token-level matching and SPLADE's learned term weights.
- retrieval/chapters/10-hybrid-search.html · ch 10 · deep · Hybrid Search & Rank Fusion: Combining lexical and dense results with reciprocal rank fusion and score normalisation.
Part 4: Vector Indexes
- retrieval/chapters/11-ann-indexes.html · ch 11 · deep · Approximate Nearest-Neighbour Search: HNSW, IVF and product quantisation, and the recall, latency and memory triangle.
- retrieval/chapters/12-filters-permissions.html · ch 12 · core · Filters, Metadata & Permissions: Pre- and post-filtering, tenant isolation and document-level access control in retrieval.
Part 5: The RAG System
- retrieval/chapters/13-rag-end-to-end.html · ch 13 · deep · RAG End to End: Ingest, index, retrieve, assemble, generate and cite: the whole pipeline and its knobs.
- retrieval/chapters/14-chunking.html · ch 14 · deep · Chunking & Contextual Retrieval: Fixed, structural and semantic chunks, chunk context, and parent-child retrieval.
- retrieval/chapters/15-agentic-retrieval.html · ch 15 · core · Query Rewriting, Agentic Retrieval & GraphRAG: Decomposing questions, iterative search, knowledge graphs and when each pays off.
- retrieval/chapters/16-grounded-citations.html · ch 16 · deep · Grounded Answers & Citations: Making every claim traceable to a span, and checking that the span supports it.
- retrieval/chapters/17-rag-failures.html · ch 17 · deep · How RAG Fails: Missed retrieval, wrong chunk, ignored context, stale sources and confident synthesis.
Part 6: Document AI
- retrieval/chapters/18-pdf-layout.html · ch 18 · deep · PDFs & Layout: What a PDF really contains, born-digital versus scanned, reading order and layout analysis.
- retrieval/chapters/19-ocr.html · ch 19 · deep · OCR: Classical Engines to Vision-Language Models: Detection and recognition, Tesseract to VLM-based OCR, error rates and hallucinated text.
- retrieval/chapters/20-tables-forms.html · ch 20 · core · Tables, Forms & Key-Value Extraction: Table structure recognition, form fields, schemas and validating extracted values.
- retrieval/chapters/21-visual-retrieval.html · ch 21 · core · Visual Document Retrieval: Embedding page images directly with ColPali-style models, and when that beats OCR.
- retrieval/chapters/22-multilingual.html · ch 22 · intro · Multilingual & Multi-Script Documents: Scripts without spaces, mixed languages, right-to-left text and cross-lingual retrieval.
Labs:
- retrieval/labs/lab-01-bm25.html · L1 (after Part 1) · A Search Engine with BM25: An analyser, an inverted index, BM25 scoring and top-k retrieval, tested on a small corpus.
- retrieval/labs/lab-02-retrieval-eval.html · L2 (after Part 2) · A Retrieval Evaluation Harness: Precision, recall, MRR and nDCG from judgements, with confidence intervals and a paired comparison.
- retrieval/labs/lab-03-hybrid.html · L3 (after Part 3) · Hybrid Retrieval & Reranking: Dense vectors, BM25, reciprocal rank fusion and a reranker, each measured with your harness.
- retrieval/labs/lab-04-hnsw.html · L4 (after Part 4) · HNSW from Scratch: Build a hierarchical navigable small-world graph and chart recall against search effort.
- retrieval/labs/lab-05-rag-citations.html · L5 (after Part 5) · RAG with Verified Citations: Chunk, retrieve, answer with citations and reject any answer whose quotes are not in the source.
- retrieval/labs/lab-06-document-pipeline.html · L6 (after Part 6) · A Document Understanding Pipeline: From OCR boxes to reading order, sections and tables, with character error rate measured.
Cases:
- retrieval/cases/case-01-contextual-retrieval.html · C1 · Contextual Retrieval [Context before embedding]: Prepending chunk context, hybrid search and reranking, and the failure rates each step removed.
- retrieval/cases/case-02-bert-search.html · C2 · BERT Comes to Web Search [Understanding queries]: When a search engine started reading the little words in queries.
- retrieval/cases/case-03-lost-in-the-middle.html · C3 · Lost in the Middle [Long context is not free]: Models that used evidence at the start and end of the context and missed it in the middle.
- retrieval/cases/case-04-air-canada.html · C4 · The Chatbot's Promise: Air Canada [Grounded answers are a liability question]: A tribunal held an airline to a refund policy its chatbot made up.
- retrieval/cases/case-05-faiss.html · C5 · FAISS: Billion-Scale Similarity Search [Compressed vectors]: Product quantisation and GPU search that made nearest neighbours over billions of vectors practical.
- retrieval/cases/case-06-colpali.html · C6 · ColPali: Retrieving Pages as Images [Skip the OCR]: Embedding page screenshots directly, and a benchmark built to test it.
- retrieval/cases/case-07-open-document-parsers.html · C7 · Open Document Conversion Pipelines [Layout models + OCR]: How Docling and olmOCR turn PDFs into structured text, and how they were evaluated.
Studios:
- retrieval/studios/studio-01-enterprise-search.html · S1 (after Part 4) · Design Enterprise Search with Permissions: Many sources, per-document access control, freshness and relevance across a whole company.
- retrieval/studios/studio-02-policy-assistant.html · S2 (after Part 5) · Design a Policy & Regulation Assistant: Answers people will act on, from a corpus that changes, with citations a reviewer can check.
- retrieval/studios/studio-03-document-processing.html · S3 (after Part 6) · Design a Document-Processing Pipeline: Millions of scanned forms and invoices a month, with extraction accuracy and human review.
Toolbox (retrieval/toolbox.html#id):
- #opensearch · Elasticsearch & OpenSearch · chapters 01,02,10: The standard open-source search engines, with BM25, analysers and vector search.
- #vector-dbs · pgvector, Qdrant & friends · chapters 11,12: Vector indexes inside Postgres or as dedicated databases.
- #sbert · sentence-transformers · chapters 07,08: Load, run and fine-tune embedding models and cross-encoders.
- #ir-eval · ranx & pytrec_eval · chapters 04,05: Standard implementations of retrieval metrics to check your own against.
- #docling · Docling, Marker & MinerU · chapters 18,20: Open-source PDF-to-structure converters.
- #ocr · Tesseract & PaddleOCR · chapters 19,22: Classical and deep-learning OCR engines you can run locally.

## A6 · Evals, Guardrails & Safe Operation  (id "evl", folder evals/)

Part 0: Orientation
- evals/chapters/00-start-here.html · ch 00 · intro · Start Here: Evaluation as the core skill of AI engineering, and the loop this course teaches.
Part 1: Measurement
- evals/chapters/01-error-analysis.html · ch 01 · deep · Error Analysis: Reading traces, open and axial coding, the first failure in each trace, and failure taxonomies.
- evals/chapters/02-eval-harnesses.html · ch 02 · deep · Assertions & Eval Harnesses: Deterministic checks first, test cases as data, and a harness you can run on every change.
- evals/chapters/03-llm-judges.html · ch 03 · deep · LLM-as-Judge: Binary rubrics, pairwise comparisons, position and length bias, and calibrating judges against people.
- evals/chapters/04-eval-statistics.html · ch 04 · deep · Statistics for Evals: Error bars, paired comparisons, clustered questions, sample sizes and repeated runs.
- evals/chapters/05-human-labels.html · ch 05 · core · Human Labels: Guidelines, inter-annotator agreement, adjudication and running a labelling effort.
Part 2: Benchmarks
- evals/chapters/06-building-benchmarks.html · ch 06 · deep · Building a Domain Benchmark: Task definition, sourcing items, gold answers, difficulty, data cards and versioning.
- evals/chapters/07-contamination.html · ch 07 · deep · Contamination, Saturation & Decay: How benchmarks leak into training data, saturate, and get audited and retired.
- evals/chapters/08-agent-evals.html · ch 08 · deep · Evaluating Agents: End-state checks, trajectory review, simulated users, pass@k versus pass^k, and cost per task.
- evals/chapters/09-leaderboards.html · ch 09 · core · Reading Leaderboards Critically: Arena ratings, self-reported scores, scaffolds and the questions to ask of any number.
Part 3: Truthfulness
- evals/chapters/10-hallucination.html · ch 10 · core · Why Models Hallucinate: Kinds of hallucination, their causes in training and scoring, and how to measure them.
- evals/chapters/11-grounding-abstention.html · ch 11 · deep · Grounding, Abstention & Confidence: Answering only from evidence, saying 'I don't know', and risk-coverage curves.
- evals/chapters/12-fact-checking.html · ch 12 · deep · Fact-Checking & Citation Verification: Claim extraction, evidence retrieval, entailment checks and verifying that citations support claims.
Part 4: Adversaries
- evals/chapters/13-prompt-injection.html · ch 13 · deep · Prompt Injection & Jailbreaks: Direct and indirect injection, jailbreak families, and why detection loses to adaptive attackers.
- evals/chapters/14-architectural-defences.html · ch 14 · deep · Architectural Defences: Capability limits, the rule of two, dual-model patterns and CaMeL-style data-flow control.
- evals/chapters/15-guardrails.html · ch 15 · core · Guardrail Classifiers & Content Policy: Input and output classifiers, policy design, PII filters and measuring guardrail recall.
- evals/chapters/16-red-teaming.html · ch 16 · core · Red Teaming: Planning, manual and automated attacks, scoring findings and closing the loop.
Part 5: Operations
- evals/chapters/17-observability.html · ch 17 · core · Tracing & Observability for LLM Systems: Spans for model and tool calls, what to log, sampling, and OpenTelemetry's GenAI conventions.
- evals/chapters/18-improvement-flywheel.html · ch 18 · deep · The Improvement Flywheel: Production traces to labelled failures to regression suites to safer releases.
- evals/chapters/19-cost-latency-quality.html · ch 19 · core · Cost, Latency & Quality Trade-offs: Pareto fronts, model routing, caching and deciding what 'good enough' costs.
- evals/chapters/20-ai-incidents.html · ch 20 · intro · AI Incident Response: Detecting, containing and learning from an AI system that misbehaves in production.
Part 6: Governance
- evals/chapters/21-governance.html · ch 21 · core · Governance Frameworks & Regulation: NIST AI RMF, ISO/IEC 42001 and the EU AI Act, read as engineering requirements.
- evals/chapters/22-privacy-data.html · ch 22 · core · Privacy & Data Handling for AI: PII in prompts and logs, retention, training on customer data, and data residency.
Labs:
- evals/labs/lab-01-eval-harness.html · L1 (after Part 1) · An Eval Harness with Error Bars: Run cases, score them, bootstrap confidence intervals and compare two systems with a paired test.
- evals/labs/lab-02-judge-calibration.html · L2 (after Part 1) · Calibrate an LLM Judge: Measure a judge's agreement with human labels, probe position and length bias, and correct the estimate.
- evals/labs/lab-03-benchmark.html · L3 (after Part 2) · Build a Domain Benchmark: Validate items, split them, version them and run a contamination probe.
- evals/labs/lab-04-agent-eval.html · L4 (after Part 2) · Evaluate an Agent: A simulated shop with a database: grade end states, run each task k times and report pass^k.
- evals/labs/lab-05-citations-abstention.html · L5 (after Part 3) · Citation Checking & Abstention: Verify quoted spans, score claim support, then sweep an abstention threshold on a risk-coverage curve.
- evals/labs/lab-06-red-team.html · L6 (after Part 4) · Red-Team a RAG Agent: Forty injection payloads against four defences, with attack success rates and utility costs.
- evals/labs/lab-07-regression-gate.html · L7 (after Part 5) · Traces & a Regression Gate: Emit spans, turn failures into regression cases and block a release that gets worse.
Cases:
- evals/cases/case-01-swe-bench-verified.html · C1 · Retiring SWE-bench Verified [Benchmark lifecycle]: A widely reported coding benchmark, an audit of its hardest tasks, and why its main sponsor stopped using it.
- evals/cases/case-02-cuda-engineer.html · C2 · The AI CUDA Engineer [Evaluator hacking]: Claimed kernel speedups that came from loopholes in the evaluation harness.
- evals/cases/case-03-mata-avianca.html · C3 · Fake Citations in Court [Unverified generation]: Lawyers who filed a brief citing cases a chatbot had invented, and the court's response.
- evals/cases/case-04-attacker-moves-second.html · C4 · The Attacker Moves Second [Adaptive attacks]: Published prompt-injection defences re-tested against attackers who adapt, and what survived.
- evals/cases/case-05-tau-bench.html · C5 · tau-bench: Agents with Simulated Users [End-state grading]: Grading an agent by the database it leaves behind, and reliability measured as pass^k.
- evals/cases/case-06-leaderboard-illusion.html · C6 · The Leaderboard Illusion [Rankings can be gamed]: Private testing, selective disclosure and sampling rates behind a popular model arena.
- evals/cases/case-07-ai-overviews.html · C7 · Glue on Pizza: Search Answers Go Wrong [Bad sources, confident answers]: AI-generated search summaries that repeated jokes and satire as fact, and the fixes that followed.
Studios:
- evals/studios/studio-01-eval-program.html · S1 (after Part 2) · Design the Eval Program for an Assistant: Who labels, what is measured, how often, which numbers block a release and who signs off.
- evals/studios/studio-02-agent-guardrails.html · S2 (after Part 4) · Design Guardrails for an Agent with Tools: An agent that reads email and can send it: threat model, capability limits, classifiers and monitoring.
- evals/studios/studio-03-llm-observability.html · S3 (after Part 5) · Design LLM Observability & Continuous Evaluation: Traces at scale, online evaluators, sampling, dashboards, alerts and the path from failure to fix.
Toolbox (evals/toolbox.html#id):
- #inspect · Inspect · chapters 02,06,08: The UK AI Security Institute's open-source evaluation framework.
- #promptfoo · promptfoo · chapters 02,16: Declarative test cases, assertions and red-team scans for prompts and apps.
- #tracing · Langfuse & Phoenix · chapters 17,18: Open-source tracing, datasets and online evaluation for LLM applications.
- #redteam · garak & PyRIT · chapters 13,16: Automated vulnerability scanners and red-teaming toolkits for language models.
- #labelling · Annotation tools · chapters 01,05: Spreadsheets, Label Studio and custom review apps for reading and labelling traces.
- #presidio · Presidio · chapters 15,22: Detect and redact personal data in text before it reaches a model or a log.

## A7 · Search, Evolution & Self-Improving Agents  (id "oe", folder open-ended/)

Part 0: Orientation
- open-ended/chapters/00-start-here.html · ch 00 · intro · Start Here: Objectives, search and open-ended discovery, and what this course builds.
Part 1: Search Foundations
- open-ended/chapters/01-tree-search.html · ch 01 · deep · Tree Search, Bandits & MCTS: Exploration versus exploitation, UCB, Monte Carlo tree search and the AlphaZero idea.
- open-ended/chapters/02-evolutionary-algorithms.html · ch 02 · deep · Evolutionary Algorithms: Populations, mutation, crossover, selection pressure and evolution strategies.
- open-ended/chapters/03-novelty-search.html · ch 03 · core · Why Objectives Deceive: Deceptive fitness landscapes, novelty search and the value of stepping stones.
- open-ended/chapters/04-quality-diversity.html · ch 04 · deep · Quality-Diversity & MAP-Elites: Archives of diverse high performers, behaviour descriptors and illumination.
Part 2: Open-Endedness
- open-ended/chapters/05-open-ended-algorithms.html · ch 05 · core · Open-Ended Algorithms: POET and co-evolving problems with solutions, and what 'open-ended' means.
- open-ended/chapters/06-interestingness.html · ch 06 · core · Models of Interestingness: Using foundation models to judge what is new and worth learning: OMNI and successors.
- open-ended/chapters/07-lifelong-agents.html · ch 07 · core · Lifelong Agents & Skill Libraries: Voyager's curriculum, skills as code and agents that accumulate abilities.
Part 3: LLMs as Search Operators
- open-ended/chapters/08-inference-time-search.html · ch 08 · deep · Inference-Time Search: Best-of-n, self-consistency, tree search over answers, verifiers and adaptive branching.
- open-ended/chapters/09-program-evolution.html · ch 09 · deep · LLM-Guided Program Evolution: FunSearch and AlphaEvolve: language models as mutation operators with automatic evaluators.
- open-ended/chapters/10-evolution-frameworks.html · ch 10 · core · Open Evolution Frameworks: Inside OpenEvolve and ShinkaEvolve: islands, archives, novelty rejection and sample efficiency.
- open-ended/chapters/11-evolving-prompts.html · ch 11 · core · Evolving Prompts & Pipelines: Prompt evolution, self-referential improvement and optimising LLM programs with DSPy.
Part 4: Meta Agents
- open-ended/chapters/12-meta-agent-search.html · ch 12 · deep · Automated Design of Agentic Systems: A meta agent that writes agents as code, keeps an archive and searches for better designs.
- open-ended/chapters/13-self-improving-agents.html · ch 13 · deep · Self-Improving Coding Agents: The Darwin Gödel Machine: an agent that edits its own scaffold, validated empirically.
- open-ended/chapters/14-automated-science.html · ch 14 · core · Automated Science: The AI Scientist: ideas, experiments, papers and automated review, and their limits.
Part 5: Integrity
- open-ended/chapters/15-evaluator-hacking.html · ch 15 · deep · Evaluator Hacking & Reward Hacking: Search finds every loophole in the scorer: famous examples and how to harden evaluators.
- open-ended/chapters/16-held-out-evaluation.html · ch 16 · deep · Held-Out Evaluation for Self-Improvers: Separate search, selection and test sets, and the statistics of picking the best of many.
- open-ended/chapters/17-self-modification-safety.html · ch 17 · core · Safety of Self-Modifying Systems: Sandboxes, lineage tracking, human oversight and objectives that resist gaming.
Part 6: Applied
- open-ended/chapters/18-search-in-products.html · ch 18 · core · Search Inside Real Products: Evolving prompts, rules and heuristics for a business, and when simpler methods win.
Labs:
- open-ended/labs/lab-01-mcts.html · L1 (after Part 1) · Bandits & Monte Carlo Tree Search: Epsilon-greedy, UCB and Thompson sampling, then MCTS that plays a small game well.
- open-ended/labs/lab-02-map-elites.html · L2 (after Part 1) · Novelty Search & MAP-Elites: A deceptive maze where objective search fails, novelty search succeeds and MAP-Elites illuminates.
- open-ended/labs/lab-03-program-evolution.html · L3 (after Part 3) · A Mini FunSearch: Evolve bin-packing heuristics as code with an island archive and a pluggable mutation operator.
- open-ended/labs/lab-04-ab-mcts.html · L4 (after Part 3) · Adaptive Branching over Many Models: Decide when to sample a new answer, refine an old one or switch models, under a call budget.
- open-ended/labs/lab-05-meta-agent.html · L5 (after Part 4) · A Mini Meta-Agent Search: Search over agent designs on a small benchmark, with separate search and held-out splits.
- open-ended/labs/lab-06-gameable-evaluator.html · L6 (after Part 5) · The Gameable Evaluator: Watch a search loop exploit a leaky scorer, then harden the harness until the exploits stop.
Cases:
- open-ended/cases/case-01-alphazero.html · C1 · AlphaGo to AlphaZero [Search plus learning]: Tree search guided by a learned policy and value, and what self-play removed.
- open-ended/cases/case-02-picbreeder.html · C2 · Picbreeder & Why Greatness Cannot Be Planned [Stepping stones]: Images nobody aimed for, found by people following what was interesting.
- open-ended/cases/case-03-funsearch.html · C3 · FunSearch and the Cap Set [Evolving programs, not answers]: A language model in an evolutionary loop that found new constructions in mathematics.
- open-ended/cases/case-04-alphaevolve.html · C4 · AlphaEvolve [Evolution with evaluators]: Evolving whole codebases against automatic evaluators, from matrix multiplication to data-centre scheduling.
- open-ended/cases/case-05-voyager.html · C5 · Voyager in Minecraft [Skill libraries]: A lifelong agent that wrote its own curriculum and kept its skills as code.
- open-ended/cases/case-06-darwin-godel-machine.html · C6 · The Darwin Gödel Machine [Open-ended self-improvement]: A coding agent that rewrote its own tools, and the objective hacking its authors reported.
- open-ended/cases/case-07-ai-scientist.html · C7 · The AI Scientist and Peer Review [Automating the research loop]: Generated papers, an automated reviewer and a workshop submission, read with care.
Studios:
- open-ended/studios/studio-01-optimisation-loop.html · S1 (after Part 3) · Design an Automated Optimisation Loop: Evolve a scheduling heuristic for a business: evaluator, budget, archive, safety and rollout.
- open-ended/studios/studio-02-review-claim.html · S2 (after Part 5) · Review a Self-Improvement Claim: A team says its agent improved itself by 30%. Decide what you need to see before you believe it.
Toolbox (open-ended/toolbox.html#id):
- #openevolve · OpenEvolve · chapters 09,10: An open-source implementation of AlphaEvolve-style program evolution.
- #shinka · ShinkaEvolve · chapters 10: Sakana AI's sample-efficient open-source evolution framework.
- #pyribs · pyribs · chapters 04: A quality-diversity library with MAP-Elites and its descendants.
- #dspy · DSPy · chapters 11: Write LLM pipelines as modules and let optimisers tune prompts and examples.
- #evotorch · Evolution-strategy libraries · chapters 02: CMA-ES and friends for black-box optimisation.

## A8 · Applied AI Delivery Studio  (id "aid", folder ai-delivery/)

Part 0: Orientation
- ai-delivery/chapters/00-start-here.html · ch 00 · intro · Start Here: The applied AI engineer's job, and how the studios in this capstone work.
Part 1: Discovery
- ai-delivery/chapters/01-discovery-interviews.html · ch 01 · deep · Discovery Interviews: Asking about past behaviour, not opinions; finding the real problem behind the requested feature.
- ai-delivery/chapters/02-requirements-ambiguity.html · ch 02 · deep · Requirements Under Ambiguity: Turning a vague goal into decisions, constraints and success metrics both sides sign.
- ai-delivery/chapters/03-expert-knowledge.html · ch 03 · deep · Capturing Expert Knowledge: Shadowing, think-aloud sessions and worked examples: turning tacit judgement into rubrics and data.
- ai-delivery/chapters/04-feasibility.html · ch 04 · core · Is AI the Right Tool?: Feasibility, error tolerance, data availability and risk: a triage before anyone builds.
Part 2: Building the Proof
- ai-delivery/chapters/05-riskiest-assumption.html · ch 05 · deep · Prototype the Riskiest Assumption: Build the smallest thing that could prove you wrong, in days, not months.
- ai-delivery/chapters/06-evaluation-plans.html · ch 06 · deep · Evaluation Plans Customers Trust: Gold sets from the customer's own work, agreed metrics and comparison with the current process.
- ai-delivery/chapters/07-choosing-models.html · ch 07 · core · Choosing Models: Frontier APIs, open-weight models and on-premises deployment, chosen by evidence and constraints.
Part 3: Domains
- ai-delivery/chapters/08-finance.html · ch 08 · core · Finance: Lending, research, compliance and wealth management, with model risk management and audit.
- ai-delivery/chapters/09-healthcare.html · ch 09 · core · Healthcare & Life Sciences: Clinical documentation, patient safety, medical-device rules and protected health data.
- ai-delivery/chapters/10-legal.html · ch 10 · core · Legal & Compliance: Contracts, discovery and research, privilege and confidentiality, and verifying every citation.
- ai-delivery/chapters/11-public-sector.html · ch 11 · core · Public Sector & Government: Citizen services, analysts and caseworkers, procurement, transparency and accountability.
Part 4: Delivery
- ai-delivery/chapters/12-poc-to-production.html · ch 12 · deep · From Proof of Concept to Production: Why most pilots stall, production gates, integration, support and change management.
- ai-delivery/chapters/13-restricted-environments.html · ch 13 · core · Restricted Environments: On-premises and air-gapped deployment, data residency and a limited menu of approved models.
- ai-delivery/chapters/14-cost-roi.html · ch 14 · core · Cost Models & Return on Investment: Unit economics per task, total cost of ownership and an honest return-on-investment case.
- ai-delivery/chapters/15-security-review.html · ch 15 · core · Security Reviews for AI Systems: The questions a customer's security team will ask, and the evidence pack that answers them.
Part 5: Productisation & Communication
- ai-delivery/chapters/16-research-to-product.html · ch 16 · core · Turning Research into Products: From a paper and a repository to an interface, SLOs, documentation and support.
- ai-delivery/chapters/17-writing-for-customers.html · ch 17 · deep · Writing for Customers: Status reports, analysis memos and presenting a failure honestly to the people paying.
- ai-delivery/chapters/18-getting-hired.html · ch 18 · deep · Take-Homes, Portfolios & Interviews: What applied AI teams test, how to scope a take-home, and a portfolio that proves judgement.
- ai-delivery/chapters/19-where-next.html · ch 19 · intro · Where Next: Keeping up without drowning, and the next steps after this path.
Labs:
- ai-delivery/labs/lab-01-brief-to-eval.html · L1 (after Part 2) · From Brief to Evaluation Kit: Turn a customer brief and sample documents into a validated gold set, rubric and acceptance thresholds.
- ai-delivery/labs/lab-02-cost-model.html · L2 (after Part 4) · A Cost & Latency Model: Price a workload across models, caching and batching, and find the cheapest option that meets the bar.
- ai-delivery/labs/lab-03-pii-pipeline.html · L3 (after Part 4) · A PII Redaction & Audit Pipeline: Detect and redact personal data, keep reversible tokens for authorised users and log every access.
- ai-delivery/labs/lab-04-take-home.html · L4 (after Part 5) · A Take-Home, End to End: A timed document-QA system graded by hidden tests, with the memo that goes with it.
Cases:
- ai-delivery/cases/case-01-klarna.html · C1 · Klarna's AI Assistant [Automation claims meet customers]: An assistant said to do the work of hundreds of agents, and the later decision to bring humans back.
- ai-delivery/cases/case-02-morgan-stanley.html · C2 · A Research Assistant for Financial Advisers [Evals before rollout]: An assistant over a firm's own research library, gated by an evaluation framework built with experts.
- ai-delivery/cases/case-03-nyc-mycity.html · C3 · A City's Chatbot Gives Illegal Advice [Public-sector accountability]: A government business-advice chatbot that told owners they could break the law.
- ai-delivery/cases/case-04-forward-deployed.html · C4 · The Forward-Deployed Engineer [Engineers embedded with customers]: How embedding engineers with customers became a model for AI companies.
- ai-delivery/cases/case-05-legal-ai-rollout.html · C5 · Rolling Out AI in a Law Firm [Expert users, verification culture]: Pilots, verification rules and adoption when every answer must be checked by a professional.
- ai-delivery/cases/case-06-bank-lending-workflow.html · C6 · An Expert Workflow for Bank Lending [Decompose expert reasoning]: A loan-document assistant built by structuring expert judgement, with feedback loops calibrated to reviewers.
Studios:
- ai-delivery/studios/studio-01-contract-review.html · S1 (after Part 2) · Take-Home: Contract Clause Review: A legal team wants risky clauses flagged in supplier contracts. Scope it, build the proof, report.
- ai-delivery/studios/studio-02-analyst-assistant.html · S2 (after Part 2) · Take-Home: An Analyst's Research Assistant: Answer questions over annual reports with numbers that tie to the page they came from.
- ai-delivery/studios/studio-03-claims-triage.html · S3 (after Part 3) · Take-Home: Insurance Claims Triage: Route incoming claims with attachments, and decide what never goes to a model.
- ai-delivery/studios/studio-04-citizen-services.html · S4 (after Part 3) · Take-Home: Citizen Services Q&A: A government help service that must be accurate, accessible and accountable.
- ai-delivery/studios/studio-05-clinical-notes.html · S5 (after Part 3) · Take-Home: Clinical Note Summaries: Summaries clinicians can trust, with omissions measured as carefully as errors.
- ai-delivery/studios/studio-06-support-automation.html · S6 (after Part 4) · Take-Home: Support Automation with Refunds: Automate part of a support queue with money at stake, and prove the savings.
- ai-delivery/studios/studio-07-coding-assistant-rollout.html · S7 (after Part 4) · Take-Home: Rolling Out a Coding Assistant: A 300-engineer company wants AI coding tools. Plan the rollout and measure the effect honestly.
- ai-delivery/studios/studio-08-productise-research.html · S8 (after Part 5) · Take-Home: Productise a Research Prototype: A promising research repository, a customer who wants it next quarter, and everything in between.
Toolbox (ai-delivery/toolbox.html#id):
- #demo-uis · Gradio & Streamlit · chapters 05: A usable demo in an afternoon, so customers react to something real.
- #fastapi · FastAPI · chapters 12,16: Typed Python web APIs with generated documentation.
- #compose · Docker Compose · chapters 13,12: Package a whole system so a customer can run it inside their own network.
- #pii-tools · Presidio for redaction · chapters 15,09: Detect and anonymise personal data before it leaves a boundary.
- #writing · Writing & diagram tools · chapters 17,18: Markdown, Mermaid and a memo template for status reports and analysis write-ups.
