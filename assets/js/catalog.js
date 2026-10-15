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
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "What AI systems engineers build, the courses and the four artifacts they lead to, and how to use them without drowning." },
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
    { title: "Framing Problems",       blurb: "Generalisation and metrics: deciding what to predict and how to judge it." },
    { title: "Validation",             blurb: "Cross-validation and leakage: whether to believe the number." }
  ];
  var ML_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                               blurb: "Learning from examples, the data-science loop, and where this course fits." },
    { id: "01", part: 1, depth: "deep",  file: "01-generalisation.html",      title: "What Learning Is: Generalisation",         blurb: "Training, validation and test sets, overfitting, underfitting and the no-free-lunch idea." },
    { id: "02", part: 1, depth: "deep",  file: "02-framing-metrics.html",     title: "Framing Problems & Choosing Metrics",      blurb: "Turning a business question into a prediction task with a metric that matches the cost of errors." },
    { id: "13", part: 2, depth: "deep",  file: "13-cross-validation.html",    title: "Cross-Validation Done Right",              blurb: "k-fold, grouped, stratified and time-based splits that mirror how the model will be used." },
    { id: "14", part: 2, depth: "deep",  file: "14-leakage.html",             title: "Leakage: The Silent Killer",               blurb: "Target leakage, train-test contamination and preprocessing leaks, and how to hunt them." }
  ];
  var ML_LABS = [
    { id: "L4", file: "lab-04-leakage-hunt.html",   title: "The Leakage Hunt",                         afterPart: 2, related: ["13", "14"], blurb: "Build a validation harness that catches four planted leaks, including one in preprocessing." }
  ];
  var ML_CASES = [
    { id: "C2", file: "case-02-google-flu-trends.html", title: "Google Flu Trends",                     pattern: "Drift and spurious features", related: ["14"],       blurb: "Search queries that predicted flu, until they did not, and what the post-mortems found." },
    { id: "C6", file: "case-06-competition-leaks.html", title: "Leaks That Won Competitions",           pattern: "Leakage",                     related: ["14"],       blurb: "Row orders, IDs and timestamps that gave away the answer, and how organisers learned to prevent them." }
  ];
  var ML_STUDIOS = [

  ];
  var ML_TOOLS = [

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
    { id: "22", part: 6, depth: "intro", file: "22-beyond-attention.html",    title: "Beyond Attention",                         blurb: "State-space models, linear attention and hybrids, and what they trade away." },
    { id: "23", part: 6, depth: "intro", file: "23-interpretability-basics.html", title: "Interpretability Basics", blurb: "Reading what a network computes: probes, the residual stream, attention patterns and sparse features, as reading." },
    { id: "24", part: 6, depth: "intro", file: "24-learned-optimisers.html", title: "Learned Optimisers & In-Context Learning", blurb: "Optimisers that are themselves trained, and in-context learning read as a learned learning algorithm." }
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
    { title: "Inference Cost",         blurb: "What a token costs to produce, and how to meter a loop that spends them." },
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
    { id: "22", part: 5, depth: "core",  file: "22-token-economics.html",     title: "The Economics of a Token",                 blurb: "Throughput, latency, batch size and price: what a million tokens costs to serve." },
    { id: "23", part: 6, depth: "core",  file: "23-evaluating-models.html",   title: "Evaluating a Model You Trained",           blurb: "Held-out sets, evaluation harnesses, contamination checks and regressions on other skills." }
  ];
  var LLM_LABS = [
    { id: "L1", file: "lab-01-data-pipeline.html", title: "A Pretraining Data Pipeline",       afterPart: 1, related: ["01"],             blurb: "Extract, filter by quality heuristics and deduplicate with MinHash and locality-sensitive hashing." },
    { id: "L2", file: "lab-02-policy-gradient.html", title: "Policy Gradients & PPO",          afterPart: 2, related: ["06", "07", "08"], blurb: "REINFORCE with a baseline, then PPO's clipped objective with a KL penalty, on bandits and a gridworld." },
    { id: "L3", file: "lab-03-lora.html",           title: "LoRA from Scratch",                afterPart: 3, related: ["11"],             blurb: "Freeze a small model, train low-rank adapters, merge them back and compare parameter counts." },
    { id: "L4", file: "lab-04-dpo-grpo.html",       title: "DPO & GRPO on a Toy Policy",       afterPart: 3, related: ["12", "14"],       blurb: "Implement both losses on a policy over answers to arithmetic questions with a verifiable reward." },
    { id: "L5", file: "lab-05-evolutionary-merge.html", title: "Evolutionary Model Merging",   afterPart: 4, related: ["16"],             blurb: "Merge task-specialised small models and evolve merge coefficients against a held-out task." }
  ];
  var LLM_CASES = [
    { id: "C1", file: "case-01-instructgpt.html",   title: "InstructGPT: RLHF in Practice",     pattern: "Learning from human preferences", related: ["10", "12"], blurb: "A smaller model that labellers preferred to one a hundred times larger." },
    { id: "C2", file: "case-02-deepseek-r1.html",   title: "DeepSeek-R1",                       pattern: "RL with verifiable rewards",      related: ["14", "15"], blurb: "Reasoning that emerged from reinforcement learning on checkable problems, then distilled into small models." },
    { id: "C3", file: "case-03-llama3-training.html", title: "Training Llama 3 at Scale",       pattern: "Reliability of training clusters", related: ["03", "05"], blurb: "Thousands of GPUs, hundreds of interruptions and the engineering that kept the run on track." },
    { id: "C5", file: "case-05-evolutionary-merge.html", title: "Evolving Model Merges",        pattern: "Search over recipes",             related: ["16"],       blurb: "Evolutionary search that combined existing open models into new capabilities without gradient training." },
    { id: "C6", file: "case-06-sycophancy-rollback.html", title: "The Sycophancy Rollback",     pattern: "Reward signals with side effects", related: ["13"],      blurb: "A model update that became too eager to please, and what its developer said went wrong." },
    { id: "C7", file: "case-07-alpaca.html",        title: "Alpaca & Self-Instruct",            pattern: "Distillation from a stronger model", related: ["15", "10"], blurb: "Fifty-two thousand generated instructions, a few hundred dollars and a lesson about imitation." }
  ];
  var LLM_STUDIOS = [
    { id: "S1", file: "studio-01-domain-adaptation.html", title: "Adapt a Model for a Specialist Domain", afterPart: 3, related: ["10", "11", "23"], blurb: "Prompting, retrieval, fine-tuning or all three, under a fixed budget, with the evaluation that decides." },
    { id: "S2", file: "studio-02-reasoning-model.html",  title: "Post-train a Small Reasoning Model",    afterPart: 3, related: ["14", "15"], blurb: "Pick the base model, reward, data and compute, and plan how you will catch reward hacking." }
  ];
  var LLM_TOOLS = [
    { id: "hf",      name: "Hugging Face transformers, TRL & PEFT", chapters: ["10", "11", "12", "14"], blurb: "Load models, fine-tune with LoRA and run SFT, DPO and GRPO trainers." },
    { id: "unsloth", name: "Unsloth",                        chapters: ["11", "14"],             blurb: "Memory-efficient fine-tuning and RL that fits on a single consumer or free GPU." },
    { id: "vllm",    name: "vLLM & SGLang",                  chapters: ["22"],       blurb: "High-throughput open-source serving engines." },
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
    { id: "23", part: 3, depth: "deep",  file: "23-dense-retrieval.html",    title: "Dense Retrieval",                 blurb: "Embeddings for search, contrastive training with in-batch negatives, and when a vector index beats keywords." },
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
    { id: "C7", file: "case-07-ai-overviews.html",   title: "Glue on Pizza: Search Answers Go Wrong", pattern: "Bad sources, confident answers", related: ["11", "17"], blurb: "AI-generated search summaries that repeated jokes and satire as fact, and the fixes that followed." }
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
    { title: "Integrity",              blurb: "Evaluator hacking, held-out evaluation and safety for systems that change themselves." }
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
    { id: "22", part: 2, depth: "intro", file: "22-coevolution-pbt.html",     title: "Co-evolution & Population-Based Training", blurb: "Populations that train each other: co-evolution, POET-style curricula and population-based training." },
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
    { id: "17", part: 5, depth: "core",  file: "17-self-modification-safety.html", title: "Safety of Self-Modifying Systems",     blurb: "Sandboxes, lineage tracking, human oversight and objectives that resist gaming." }
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

  /* ---------- A9: Research Engineering on Small Proxies ---------- */
  var RE_PARTS = [
    { title: "Orientation",            blurb: "What an artifact is, what Artifact 1 must show, and how to use this course while building it." },
    { title: "The Loop",               blurb: "A research loop as a program: propose, run under a budget, keep or revert, and the runner that makes it safe." },
    { title: "Measurement",            blurb: "Noise floors, seeds, proxies that transfer and ablations that isolate one change." },
    { title: "Shipping",               blurb: "The write-up a reviewer reads first, and the one command that reproduces it." }
  ];
  var RE_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",        title: "Start Here",                              blurb: "Four artifacts instead of a finished curriculum, Artifact 1's gate, and which chapters to open when." },
    { id: "01", part: 1, depth: "deep",  file: "01-research-loop.html",     title: "The Research Loop as a Program",          blurb: "autoresearch's program.md, train.py and run store, and keep-or-revert as a state machine under a fixed time budget." },
    { id: "02", part: 2, depth: "deep",  file: "02-proxies-noise.html",     title: "Proxies, Noise Floors & Seeds",           blurb: "How much a five-minute score moves on its own, paired tests over seeds, and the gap between the proxy and held-out data." },
    { id: "03", part: 2, depth: "core",  file: "03-scaling-mup.html",       title: "Scaling Laws & μP Transfer for Proxies",  blurb: "What a tiny run predicts about a big one, compute-optimal sizing, and why μP lets hyperparameters transfer." },
    { id: "04", part: 2, depth: "core",  file: "04-ablations-tracking.html", title: "Ablation Design & Run Tracking",         blurb: "One change at a time, factorial designs, a run-store schema and deterministic replay." },
    { id: "05", part: 1, depth: "core",  file: "05-rust-runner.html",       title: "A Runner in Rust, Read from Python",      blurb: "Why the runner, sandbox and run store move to Rust, and enough Rust to read and change them." },
    { id: "06", part: 3, depth: "core",  file: "06-write-up.html",          title: "The Write-Up",                            blurb: "A two-to-six-page report with one claim, its number and its budget, negative results and a one-command reproduction." }
  ];
  var RE_LABS = [
    { id: "L1", file: "lab-01-keep-or-revert.html", title: "A Keep-or-Revert Research Loop", afterPart: 2, related: ["01", "02", "04"], blurb: "A run store, a noise floor, paired keep-or-revert decisions and a proxy-versus-held-out gap that warns before the loop overfits." }
  ];
  var RE_CASES = [
    { id: "C1", file: "case-01-modded-nanogpt.html", title: "modded-nanogpt: a Speedrun as a Research Record", pattern: "A public record with full provenance", related: ["02", "03", "04"], blurb: "How a community turned 'train GPT-2 faster' into a ledger of verified, reproducible gains." }
  ];
  var RE_TOOLS = [
    { id: "autoresearch", name: "autoresearch",   chapters: ["01", "02"], blurb: "Karpathy's single-file research loop: an agent edits train.py, runs it for five minutes and keeps what helps." },
    { id: "nanochat",     name: "nanochat",       chapters: ["01", "03"], blurb: "A small, complete chat-model training stack; autoresearch's single-file train.py is cut from its training run." },
    { id: "modded-nanogpt", name: "modded-nanogpt", chapters: ["03", "04"], blurb: "The GPT-2 speedrun: records, logs and the tricks that survived scrutiny." },
    { id: "cargo",        name: "Rust and cargo", chapters: ["05"],       blurb: "The Rust toolchain, for building and testing the runner." }
  ];

  /* ---------- A10: Harness & Evaluator Engineering ---------- */
  var HE_PARTS = [
    { title: "Orientation",            blurb: "Why the harness around a model is now a research object of its own." },
    { title: "Harnesses",              blurb: "From context to workflow to a harness that improves itself, and tree search over experiments." },
    { title: "Evaluators",             blurb: "Public and private splits, attested results, hacking rate, and verifying a kernel speed-up end to end." },
    { title: "Benchmarks",             blurb: "The benchmarks research agents are judged on, and how to run them under a budget." }
  ];
  var HE_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                         blurb: "Artifacts 2 and 3, what they need from this course, and what it borrows from A6." },
    { id: "01", part: 1, depth: "deep",  file: "01-harness-engineering.html", title: "Harness Engineering as Research",    blurb: "The ladder from context engineering to workflows to self-improving harnesses, with the systems on each rung." },
    { id: "02", part: 1, depth: "deep",  file: "02-aide-tree-search.html",    title: "Tree Search over Experiments: AIDE", blurb: "Draft, debug and improve nodes, a selection rule, and when tree search beats greedy hill-climbing." },
    { id: "03", part: 2, depth: "deep",  file: "03-splits-attestation.html",  title: "Public & Private Splits",            blurb: "An evaluator outside the agent's reach, hidden splits, typed and attested results, and hacking rate as a metric." },
    { id: "04", part: 2, depth: "core",  file: "04-kernels-for-agents.html",  title: "Kernel Engineering for Agents",      blurb: "Triton first and CUDA at reading level, and how to check that an agent's claimed speed-up is real." },
    { id: "05", part: 3, depth: "core",  file: "05-research-benchmarks.html", title: "Benchmarks for Research Agents",     blurb: "MLE-bench, PaperBench, RE-Bench, FML-Bench and KernelBench: what each measures and its Lite subset." }
  ];
  var HE_LABS = [
    { id: "L1", file: "lab-01-greedy-vs-tree.html", title: "Greedy versus Tree Search", afterPart: 2, related: ["02", "03"], blurb: "A toy task with public and private splits, a greedy climber and an AIDE-style tree, compared over seeds, plus a hacking probe." }
  ];
  var HE_CASES = [
    { id: "C1", file: "case-01-fml-bench-aide.html", title: "FML-Bench and AIDE²: When Search Beats Greedy", pattern: "A null result worth extending", related: ["01", "02", "05"], blurb: "A benchmark that found greedy as good as tree search, and the improver built on top of it." }
  ];
  var HE_TOOLS = [
    { id: "aideml",      name: "AIDE (aideml)",   chapters: ["02"],       blurb: "Weco's open tree-search agent for machine-learning engineering tasks." },
    { id: "fml-bench",   name: "FML-Bench",       chapters: ["02", "05"], blurb: "A benchmark of machine-learning research tasks for automated research agents." },
    { id: "kernelbench", name: "KernelBench",     chapters: ["04", "05"], blurb: "GPU kernel-writing tasks scored on correctness and speed-up." },
    { id: "triton",      name: "Triton",          chapters: ["04"],       blurb: "A Python language for GPU kernels; the first thing to read in an agent-written kernel." }
  ];

  /* ---------- A11: AI Control & Sandbox Security ---------- */
  var CTL_PARTS = [
    { title: "Orientation",            blurb: "Why a research loop needs a security model of its own." },
    { title: "Boundaries",             blurb: "Who may write what, what the box may reach, and results the agent cannot forge." },
    { title: "Monitoring",             blurb: "Reading transcripts for misbehaviour, and what to do when the loop does something it should not." }
  ];
  var CTL_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",       title: "Start Here",                             blurb: "Artifact 3's evaluator-hardening kit, and the control ideas it rests on." },
    { id: "01", part: 1, depth: "core",  file: "01-threat-model.html",     title: "The Threat Model of a Research Loop",    blurb: "Proposer against evaluator, the write boundary, and everything an agent with a key and a box can reach." },
    { id: "02", part: 1, depth: "deep",  file: "02-egress-sandbox.html",   title: "Deny-by-Default Egress & Sandboxes",     blurb: "Allowlists, an egress proxy, filesystem and resource limits, applied to a loop that runs for days." },
    { id: "03", part: 1, depth: "deep",  file: "03-attested-results.html", title: "Attested Tool Results",                  blurb: "Typed result envelopes, hashes and signatures, the evaluator as a separate principal, and tamper-evident logs." },
    { id: "04", part: 2, depth: "deep",  file: "04-transcript-monitor.html", title: "Monitoring Transcripts Offline",       blurb: "Trusted and untrusted monitors, audit budgets, and the edits to flag: tests, logs and timeouts." },
    { id: "05", part: 2, depth: "core",  file: "05-incident-playbook.html", title: "Incident Playbooks for Autonomous Loops", blurb: "Kill switches, budget caps, rollback and disclosure, written before you need them." }
  ];
  var CTL_LABS = [
    { id: "L1", file: "lab-01-attest-and-monitor.html", title: "Attest and Monitor a Research Loop", afterPart: 2, related: ["03", "04"], blurb: "Signed result envelopes, an evaluator behind a process boundary, a hash-chained log and an offline monitor, scored by hacking rate." }
  ];
  var CTL_CASES = [
    { id: "C1", file: "case-01-hugging-face-incident.html", title: "The OpenAI and Hugging Face Incident", pattern: "A sandbox that leaked", related: ["01", "02", "05"], blurb: "What an agent reached that it should not have, and the controls the post-mortem recommends." }
  ];
  var CTL_TOOLS = [
    { id: "bubblewrap", name: "bubblewrap",              chapters: ["02"], blurb: "Unprivileged Linux sandboxes built from namespaces." },
    { id: "docker",     name: "Docker (rootless)",       chapters: ["02"], blurb: "Containers without a root daemon, for running untrusted candidates." },
    { id: "mitmproxy",  name: "mitmproxy",               chapters: ["02", "04"], blurb: "An inspecting HTTP proxy, used here as an allowlisting egress gate and a traffic log." },
    { id: "sigstore",   name: "Sigstore and minisign",   chapters: ["03"], blurb: "Signing tools for results and artefacts, read for their design." }
  ];

  /* ---------- A12: Measuring Recursive Self-Improvement ---------- */
  var RSI_PARTS = [
    { title: "Orientation",            blurb: "What a claim of self-improvement must show, and why measurement is the last artifact." },
    { title: "Criteria",               blurb: "The conditions a self-improvement claim must meet, automation levels, and how to read published claims." },
    { title: "Economics",              blurb: "What a loop costs, what it returns, and when it pays for itself." }
  ];
  var RSI_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",       title: "Start Here",                          blurb: "Artifact 4, the ignition test, and the standards every artifact is held to." },
    { id: "01", part: 1, depth: "deep",  file: "01-level-one.html",        title: "What Counts as Self-Improvement",     blurb: "A fair baseline, a sustained trend, generalisation and a fixed budget: four conditions and how to test each." },
    { id: "02", part: 1, depth: "core",  file: "02-automation-levels.html", title: "Automation Levels for AI Research",  blurb: "Taxonomies of how much of AI research is automated, the published estimates, and how to score your own loop." },
    { id: "03", part: 2, depth: "deep",  file: "03-loop-economics.html",   title: "The Economics of a Loop",             blurb: "Cost per accepted improvement, returns that diminish or compound, and the elasticities that decide which." },
    { id: "04", part: 1, depth: "core",  file: "04-reading-claims.html",   title: "Reading Self-Improvement Claims",     blurb: "An audit checklist for papers and posts, applied to the systems of 2025 and 2026." },
    { id: "05", part: 2, depth: "intro", file: "05-reading-pack.html",     title: "Reading Pack: Meta-Learning & Beyond", blurb: "Learned optimisers, in-context learning as meta-learning, interpretability and co-evolution, as reading." }
  ];
  var RSI_LABS = [
    { id: "L1", file: "lab-01-level-one-checker.html", title: "The Level-1 Checker", afterPart: 2, related: ["01", "03"], blurb: "Read a loop's run log and decide, condition by condition, whether it shows self-improvement within its budget." }
  ];
  var RSI_CASES = [
    { id: "C1", file: "case-01-weco-aide2.html", title: "Weco's Claim of Recursive Self-Improvement", pattern: "Reading a self-improvement claim", related: ["01", "04"], blurb: "An outer agent that rewrote its own research agent, and what the evidence does and does not show." }
  ];
  var RSI_TOOLS = [];



  window.CS_DEPTH_LABEL = { deep: "Deep dive", core: "Core", intro: "Quick intro" };

  /* status: "done" | "building" | "planned". Planned courses appear on the hub only. */
  window.CS_COURSES = [
    { id: "mlf", dir: "ml-foundations", track: "ai", num: "A0", mark: "MF", title: "Math & Code for Machine Learning", subtitle: "the toolkit at the point of need",
      tagline: "Arrays, linear algebra, derivatives and autodiff, probability, information theory and the statistics of experiments, taught as each later course needs them.",
      status: "done", parts: MLF_PARTS, chapters: MLF_CHAPTERS, labs: MLF_LABS, cases: MLF_CASES, studios: MLF_STUDIOS, tools: MLF_TOOLS },
    { id: "ml", dir: "ml", track: "ai", num: "A1", mark: "ML", title: "Machine Learning & Data Science", subtitle: "models you can trust",
      tagline: "Framing, metrics, linear models, trees and boosting, unsupervised learning, validation, leakage, calibration, features and proving value.",
      status: "done", parts: ML_PARTS, chapters: ML_CHAPTERS, labs: ML_LABS, cases: ML_CASES, studios: ML_STUDIOS, tools: ML_TOOLS },
    { id: "dl", dir: "deep-learning", track: "ai", num: "A2", mark: "DL", title: "Deep Learning & Transformers", subtitle: "from a neuron to a GPT",
      tagline: "Backpropagation, training dynamics, embeddings, attention, the Transformer, tokenisation, decoding, scaling laws and modern architectures.",
      status: "done", parts: DL_PARTS, chapters: DL_CHAPTERS, labs: DL_LABS, cases: DL_CASES, studios: DL_STUDIOS, tools: DL_TOOLS },
    { id: "llm", dir: "llm-training", track: "ai", num: "A3", mark: "LT", title: "Training, Post-training & Serving LLMs", subtitle: "the life of a model",
      tagline: "Pretraining data and parallelism, RL foundations, fine-tuning, LoRA, RLHF, DPO and GRPO, merging, quantisation and serving engines.",
      status: "done", parts: LLM_PARTS, chapters: LLM_CHAPTERS, labs: LLM_LABS, cases: LLM_CASES, studios: LLM_STUDIOS, tools: LLM_TOOLS },
    { id: "agt", dir: "agents", track: "ai", num: "A4", mark: "AG", title: "Agents, Tools & Protocols", subtitle: "models that act",
      tagline: "The tool loop, tool design, function calling, MCP and A2A, context engineering, workflows, multi-agent systems, deep research, computer use and agent security.",
      status: "done", parts: AGT_PARTS, chapters: AGT_CHAPTERS, labs: AGT_LABS, cases: AGT_CASES, studios: AGT_STUDIOS, tools: AGT_TOOLS },
    { id: "evl", dir: "evals", track: "ai", num: "A6", mark: "EV", title: "Evals, Guardrails & Safe Operation", subtitle: "knowing that it works",
      tagline: "Error analysis, LLM judges, eval statistics, domain benchmarks, agent evals, hallucination, prompt injection, guardrails, observability and governance.",
      status: "done", parts: EVL_PARTS, chapters: EVL_CHAPTERS, labs: EVL_LABS, cases: EVL_CASES, studios: EVL_STUDIOS, tools: EVL_TOOLS },
    { id: "oe", dir: "open-ended", track: "ai", num: "A7", mark: "OE", title: "Search, Evolution & Self-Improving Agents", subtitle: "systems that keep discovering",
      tagline: "MCTS, evolution, novelty and quality-diversity, open-ended algorithms, LLM-guided program evolution, meta agents and the integrity of self-improvement.",
      status: "done", parts: OE_PARTS, chapters: OE_CHAPTERS, labs: OE_LABS, cases: OE_CASES, studios: OE_STUDIOS, tools: OE_TOOLS },
    { id: "re", dir: "research-eng", track: "ai", num: "A9", mark: "RE", title: "Research Engineering on Small Proxies", subtitle: "the loop behind Artifact 1",
      tagline: "Research loops as programs, noise floors and seeds, proxies that transfer, ablations, a Rust runner and the write-up a reviewer reads first.",
      status: "building", parts: RE_PARTS, chapters: RE_CHAPTERS, labs: RE_LABS, cases: RE_CASES, studios: [], tools: RE_TOOLS },
    { id: "he", dir: "harness-eng", track: "ai", num: "A10", mark: "HE", title: "Harness & Evaluator Engineering", subtitle: "Artifacts 2 and 3",
      tagline: "Harness engineering as research, tree search over experiments, public and private splits, kernels for agents and the benchmarks research agents face.",
      status: "building", parts: HE_PARTS, chapters: HE_CHAPTERS, labs: HE_LABS, cases: HE_CASES, studios: [], tools: HE_TOOLS },
    { id: "ctl", dir: "control", track: "ai", num: "A11", mark: "CT", title: "AI Control & Sandbox Security", subtitle: "the walls of Artifact 3",
      tagline: "The threat model of a research loop, deny-by-default egress, attested results, transcript monitoring and incident playbooks.",
      status: "building", parts: CTL_PARTS, chapters: CTL_CHAPTERS, labs: CTL_LABS, cases: CTL_CASES, studios: [], tools: CTL_TOOLS },
    { id: "rsi", dir: "rsi-measurement", track: "ai", num: "A12", mark: "RS", title: "Measuring Recursive Self-Improvement", subtitle: "the case Artifact 4 makes",
      tagline: "What counts as self-improvement, automation levels for AI research, the economics of a loop and how to read the claims.",
      status: "building", parts: RSI_PARTS, chapters: RSI_CHAPTERS, labs: RSI_LABS, cases: RSI_CASES, studios: [], tools: RSI_TOOLS }
  ];

  /* Workbench: the chapters' ideas with real tools on a real machine (page
     kind "workbench", <course>/workbench/). Each predicts a number from the
     chapters it measures, then measures it. machine: laptop | linux | gpu
     (the least the page needs); cost is for the GPU part at rented prices. */
  var WORKBENCHES = {
    llm: [
      { id: "W2", file: "w02-training-memory.html", title: "Where Training Memory Goes", machine: "gpu", chapters: ["02"], time: "1 h", cost: "about an hour of a 24 GB card",
        blurb: "Weights, gradients, optimiser state and activations: predict each, then watch max_memory_allocated step by step." },
      { id: "W3", file: "w03-lora-qlora.html", title: "LoRA, then QLoRA, on a Real Model", machine: "gpu", chapters: ["11"], time: "2 h", cost: "about two hours of a 24 GB card",
        blurb: "Fine-tune a 0.5B to 3B model with LoRA, then in 4 bits; predict trainable parameters and memory, measure both." },
      { id: "W4", file: "w04-dpo.html", title: "DPO on a Small Preference Set", machine: "gpu", chapters: ["12"], time: "2 h", cost: "about two hours of a 24 GB card",
        blurb: "Train with TRL's DPO on a few thousand pairs and watch the implicit reward margin chapter 12 derives." },
      { id: "W5", file: "w05-grpo.html", title: "GRPO on a Verifiable Task", machine: "gpu", chapters: ["14"], time: "3 h", cost: "about three hours of a 24 GB card",
        blurb: "Group-relative advantages on arithmetic with a checkable answer: reward curves, response length and a reward hack." }
    ],
    dl: [
      { id: "W1", file: "w01-pytorch.html", title: "PyTorch by Hand", machine: "vm", chapters: ["05"], time: "1 h",
        blurb: "Tensors, autograd and a training loop, checked against the micrograd-style engine you built." },
      { id: "W2", file: "w02-char-gpt.html", title: "Train a Character GPT", machine: "vm", chapters: ["12", "16"], time: "1 h",
        blurb: "Chapter 12's GPT in PyTorch on Tiny Shakespeare; predict FLOPs and time, then scale it on a GPU." },
      { id: "W3", file: "w03-tiktoken.html", title: "Real Tokenisers", machine: "vm", chapters: ["13"], time: "45 min",
        blurb: "tiktoken and a Hugging Face tokenizer on the same texts: tokens per word, languages, numbers and code." },
      { id: "W4", file: "w04-attention-kernels.html", title: "Attention Kernels, Benchmarked", machine: "gpu", chapters: ["19", "09"], time: "1 h", cost: "about an hour of a GPU",
        blurb: "Naive attention against PyTorch's fused kernel: predict memory traffic, measure time and peak memory as length grows." },
      { id: "W5", file: "w05-word-vectors.html", title: "Word Vectors from Real Text", machine: "vm", chapters: ["06"], time: "1 h",
        blurb: "Skip-gram with negative sampling in PyTorch on text8; analogies, neighbours and what the loss curve says." }
    ],
    agt: [
      { id: "W1", file: "w01-local-model-agent.html", title: "Your Agent Loop on a Local Model", machine: "vm", chapters: ["01", "02"], time: "1 h",
        blurb: "Lab 1's loop against a model running in Ollama: what changes when the scripted model becomes a real one." },
      { id: "W2", file: "w02-real-embedders.html", title: "Real Embedders and a Reranker", machine: "vm", chapters: ["23"], time: "1 h",
        blurb: "sentence-transformers and a cross-encoder on a small corpus: recall and nDCG against the stand-in embedder." }
    ],
    evl: [
      { id: "W1", file: "w01-real-judge.html", title: "A Real Judge, Calibrated", machine: "vm", chapters: ["03", "04"], time: "1.5 h",
        blurb: "A local model as LLM judge: measure position bias and agreement with labels, with confidence intervals." }
    ],
    oe: [
      { id: "W1", file: "w01-funsearch-local.html", title: "Program Evolution with a Real Model", machine: "vm", chapters: ["09", "16"], time: "2 h",
        blurb: "Lab 3's bin-packing evolver with a local model writing the mutations, scored on held-out instances." },
      { id: "W2", file: "w02-funsearch-gpu.html", title: "Evolution at Scale on a GPU", machine: "gpu", chapters: ["09", "15"], time: "3 h", cost: "about three hours of a 24 GB card",
        blurb: "The same evolver served by vLLM: hundreds of samples a minute, islands, and the evaluator hacks that appear at scale." }
    ],
    re: [
      { id: "W1", file: "w01-autoresearch-cpu.html", title: "autoresearch on a CPU Proxy", machine: "vm", chapters: ["01", "02"], time: "3 h",
        blurb: "Run the real autoresearch loop with a CPU-sized nanochat on the lab VM: seconds per experiment, the noise floor, and what the GPU budget would buy." }
    ],
    he: [
      { id: "W1", file: "w01-aide-one-task.html", title: "AIDE on One Task, CPU-Sized", machine: "vm", chapters: ["02", "05"], time: "2 h", cost: "a few dollars of API calls",
        blurb: "The real aideml agent on a small tabular task: nodes per hour, cost per node, and greedy against tree on the same budget." }
    ],
    ctl: [
      { id: "W1", file: "w01-locked-down-sandbox.html", title: "A Locked-Down Research Sandbox", machine: "vm", chapters: ["02", "03"], time: "2 h",
        blurb: "A separate user, an allowlisting egress proxy and A9's loop inside it: one blocked exfiltration, and the overhead measured." }
    ],
    rsi: [
      { id: "W1", file: "w01-improver-elasticity.html", title: "An Improver's Elasticity, Measured", machine: "vm", chapters: ["03"], time: "20 min", cost: "under a dollar of API calls",
        blurb: "A small bin-packing improver with a real model as proposer, at several budgets: gain against cost, fitted, and what the elasticity says about returns to spending." }
    ]
  };
  window.CS_COURSES.forEach(function (co) { co.workbenches = WORKBENCHES[co.id] || []; });

  /* ---------- The artifact track ----------
     Four public artifacts replace the builder spine. Each lists, in order,
     the chapters to read before starting ("before"), the chapters to open
     while stuck ("while"), and the labs, workbenches, cases and studios that
     build it ("build"). Ids are "course:chapter" or "course:L1/W1/C1/S1".
     A chapter in no list is reading: kept, never required. */
  window.CS_ARTIFACTS = [
    { id: "A1", num: 1, title: "autoresearch-rs", short: "A research loop",
      replicates: { text: "karpathy/autoresearch", href: "https://github.com/karpathy/autoresearch" },
      what: "Karpathy's autoresearch loop with the runner, sandbox and run store rewritten in Rust; the inner task is autoresearch's single-file train.py, a small nanochat-style training run, under a fixed five-minute budget.",
      extension: "A keep-or-revert loop that also logs the gap between proxy and held-out gain for every experiment, so overfitting to the five-minute proxy is measured, not assumed.",
      gate: ["100 or more overnight experiments on one GPU", "A chart of proxy gain against held-out gain", "A two-to-three-page write-up with seeds and the noise floor"],
      cost: "$150 to $300", months: "1 to 3",
      warmup: ["mlf:20", "mlf:21", "mlf:22", "oe:19", "oe:02"],
      before: ["mlf:04", "mlf:15", "mlf:17", "dl:12", "dl:14", "dl:16", "dl:17", "dl:18", "re:00", "re:01", "re:02", "re:03", "re:04", "re:05", "re:06"],
      while: ["mlf:16", "mlf:18", "dl:03", "dl:13", "llm:02", "llm:05", "llm:22", "evl:04"],
      build: ["mlf:L6", "mlf:L5", "dl:L4", "re:L1", "dl:W2", "re:W1", "dl:C4", "dl:C7", "re:C1"],
      read: [["autoresearch README and program.md", "https://github.com/karpathy/autoresearch"], ["modded-nanogpt record log", "https://github.com/KellerJordan/modded-nanogpt"], ["Hoffmann et al., Training Compute-Optimal Large Language Models (Chinchilla)", "https://arxiv.org/abs/2203.15556"], ["Yang et al., Tensor Programs V (μTransfer)", "https://arxiv.org/abs/2203.03466"]],
      open: [["METR's RE-Bench tasks, including the scaling-law task", "https://github.com/METR/ai-rd-tasks"]] },
    { id: "A2", num: 2, title: "mini-FML search study", short: "Search versus greedy",
      replicates: { text: "FML-Bench's finding that greedy search matches tree search", href: "https://github.com/qrzou/FML-bench" },
      what: "An AIDE-style tree-search agent run on three FML-Bench tasks, compared head to head with greedy hill-climbing.",
      extension: "Reproduce the greedy-versus-tree result on three tasks with three seeds, then test one hypothesis the paper leaves open, such as whether a gap appears when good ideas are rare.",
      gate: ["Paired results with confidence intervals", "A pull request to FML-Bench adding your agent or metric"],
      cost: "$300 to $600", months: "4 to 7",
      before: ["oe:01", "agt:02", "agt:04", "agt:10", "agt:18", "agt:20", "he:00", "he:01", "he:02", "he:05", "evl:04", "evl:06", "oe:08", "oe:11", "oe:16"],
      while: ["agt:05", "agt:11", "agt:23", "oe:12", "evl:03", "evl:07", "llm:14", "dl:23", "dl:24"],
      build: ["oe:L1", "agt:L1", "oe:L4", "he:L1", "evl:L1", "agt:W1", "he:W1", "agt:C2", "he:C1", "oe:C4", "evl:C6", "oe:S1"],
      read: [["FML-Bench repository and paper", "https://github.com/qrzou/FML-bench"], ["Jiang et al., AIDE: AI-Driven Exploration in the Space of Code", "https://arxiv.org/abs/2502.13138"], ["Lilian Weng, Harness Engineering for Self-Improvement (2026)", "https://lilianweng.github.io/posts/2026-07-04-harness/"]],
      open: [["Agentic Context Engineering (ACE), Meta-Harness and STOP; see A10 chapter 1", ""]] },
    { id: "A3", num: 3, title: "evaluator-hardening kit", short: "Hardened evaluators",
      replicates: { text: "visible-versus-held-out test gaps and hidden-test hardening on kernel benchmarks", href: "https://scalingintelligence.stanford.edu/pubs/kernelbench.pdf" },
      what: "A KernelBench subset where you first break the grader, then harden it, and measure the hacking rate before and after.",
      extension: "A reusable Python library (typed, attested tool results; hidden splits; end-to-end timing) that drops into Artifact 2's agent, with hacking rate as a first-class metric.",
      gate: ["Hacking rate measured on 20 or more kernels, before and after hardening", "One upstream pull request to a kernel benchmark or to ShinkaEvolve"],
      cost: "$200 to $400", months: "7 to 10",
      before: ["oe:15", "oe:16", "oe:17", "llm:13", "llm:04", "he:03", "he:04", "evl:07", "agt:19", "ctl:00", "ctl:01", "ctl:02", "ctl:03", "ctl:04", "ctl:05"],
      while: ["evl:03", "evl:04", "evl:02", "evl:08", "evl:16", "dl:19"],
      build: ["oe:L6", "agt:L7", "ctl:L1", "evl:L2", "ctl:W1", "evl:W1", "oe:W2", "ctl:C1", "evl:C2", "evl:C4", "dl:C5"],
      read: [["Ouyang et al., KernelBench", "https://scalingintelligence.stanford.edu/pubs/kernelbench.pdf"], ["OpenAI, the Hugging Face incident and the road ahead", "https://openai.com/index/hugging-face-incident-and-the-road-ahead/"]],
      open: [["Redwood Research's AI-control papers", "https://www.redwoodresearch.org/research"], ["GPU MODE lectures on Triton", "https://github.com/gpu-mode/lectures"]] },
    { id: "A4", num: 4, title: "AIDE²-in-miniature", short: "An improver of improvers",
      replicates: { text: "Weco's AIDE² outer loop", href: "https://www.weco.ai/blog/first-evidence-of-recursive-self-improvement" },
      what: "An outer agent rewrites your Artifact 2 agent on a six-task mix (three FML-Bench tasks, two autoresearch configurations, one KernelBench pair), scored on private splits under a fixed dollar budget.",
      extension: "Apply the four Level-1 conditions to your own loop, then an ignition test: swap the discovered agent into the outer loop and report whether it is a better improver.",
      gate: ["A paper-style write-up with ablations and negative results", "Released code", "A result someone else can reproduce for under $500"],
      cost: "$800 to $1,500", months: "11 to 17",
      before: ["oe:02", "oe:04", "oe:09", "oe:10", "oe:12", "oe:13", "oe:21", "oe:14", "rsi:00", "rsi:01", "rsi:02", "rsi:03", "rsi:04"],
      while: ["oe:05", "oe:07", "oe:22", "llm:14", "llm:16", "dl:24", "mlf:18", "rsi:05"],
      build: ["oe:L3", "oe:L5", "oe:L7", "rsi:L1", "oe:W1", "rsi:W1", "oe:C3", "oe:C6", "oe:C7", "rsi:C1", "oe:S2", "oe:S3"],
      read: [["Weco, first evidence of recursive self-improvement", "https://www.weco.ai/blog/first-evidence-of-recursive-self-improvement"], ["Zhang et al., Darwin Gödel Machine", "https://arxiv.org/abs/2505.22954"], ["Lange et al., ShinkaEvolve", "https://arxiv.org/abs/2509.19349"]],
      open: [["Epoch AI, toward an O*NET for AI R&D", "https://epoch.ai/gradient-updates/toward-an-onet-for-ai-rnd"], ["Anthropic, measuring the pace of AI development", "https://www.anthropic.com/institute/measuring-pace-of-ai-development"]] }
  ];
})();
