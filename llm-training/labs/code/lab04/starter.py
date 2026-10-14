"""Lab 4: DPO and GRPO on a toy policy that answers arithmetic questions.

Chapter 12 derived the DPO loss from the KL-regularised reward objective. Chapter 14 replaced the
learned reward and the critic with a verifier and a group of sampled answers. This lab implements
both losses on a policy small enough to differentiate by hand:

    for each question q the policy is a softmax over K candidate ANSWER STRINGS, and its
    parameters are the K logits z[q][k] (a "one-token answer": log pi(answer) = log_softmax(z)[k]).

    verifier + sampling + KL --> DPO loss and its gradient --> preference pairs, DPO training
        --> group-relative advantages --> GRPO clipped objective + KL penalty --> GRPO training

Standard-library Python only; every random draw comes from a seeded random.Random.

Notation follows chapters 12 and 14: pi_theta is the policy being trained, pi_ref the frozen
reference (the "SFT model"), y_w / y_l the chosen / rejected answers, beta the KL weight (DPO's
beta and GRPO's beta play the same role), r_i the verifier reward of sample i, A_i its advantage,
rho = pi_theta / pi_old the probability ratio, eps the clip range and G the group size.

What is GIVEN: the task (questions, candidates, the reference policy), softmax / log_softmax /
sigmoid, evaluation helpers.
What YOU write is marked TODO.

    1  parse_number, reward, sample_index, kl_divergence
    2  implicit_rewards, dpo_margin, dpo_loss, dpo_grads
    3  make_pairs, train_dpo
    4  group_advantages, zero_signal
    5  ratio, clipped_objective, k3, grpo_loss_and_grad
    6  train_grpo
"""
import math
import random
from fractions import Fraction

# =============================================================================
# GIVEN: numerics
# =============================================================================
def softmax(z):
    m = max(z)
    e = [math.exp(v - m) for v in z]
    s = sum(e)
    return [v / s for v in e]


def log_softmax(z):
    m = max(z)
    lse = m + math.log(sum(math.exp(v - m) for v in z))
    return [v - lse for v in z]


def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


# =============================================================================
# GIVEN: the task. Twelve arithmetic questions, six candidate answer strings each.
# =============================================================================
class Question:
    """text: "17 x 23";  answer: the true integer;  candidates: K answer strings, a few of them tricky.

    Candidate strings are not always clean integers: some correct answers come in a second surface
    form ("391.0", " 391", "0391") and some wrong ones are hedges that mention the right number
    ("391 or 392"). The verifier has to cope with all of them.
    """

    def __init__(self, text, answer, candidates):
        self.text, self.answer, self.candidates = text, answer, candidates


class Task:
    """questions, and ref: the frozen reference logits ref[q][k] (an 'SFT model' that is right 1% to 60% of the time)."""

    def __init__(self, questions, ref):
        self.questions, self.ref = questions, ref

    @property
    def n_questions(self):
        return len(self.questions)

    @property
    def k(self):
        return len(self.questions[0].candidates)


# the reference's total probability of a correct answer, question by question: easy to hard
REF_P_CORRECT = [0.60, 0.45, 0.35, 0.28, 0.22, 0.16, 0.12, 0.08, 0.05, 0.03, 0.015, 0.008]


def _is_correct_form(text, answer):
    try:
        return Fraction(text.strip()) == answer
    except (ValueError, ZeroDivisionError):
        return False


def make_task(seed=0):
    rng = random.Random(seed)
    ops = ["+", "-", "x"]
    questions, ref = [], []
    for qi, p in enumerate(REF_P_CORRECT):
        op = ops[qi % 3]
        if op == "+":
            a, b = rng.randint(120, 480), rng.randint(120, 480)
            ans, wrong_op = a + b, a - b
        elif op == "-":
            a, b = rng.randint(600, 990), rng.randint(110, 480)
            ans, wrong_op = a - b, a + b
        else:
            a, b = rng.randint(12, 38), rng.randint(12, 38)
            ans, wrong_op = a * b, a + b
        swapped = int(str(ans)[:-2] + str(ans)[-1] + str(ans)[-2]) if ans >= 100 else ans + 3
        pool = [ans + 1, ans - 1, ans + 10, ans - 10, swapped, wrong_op, ans + 100, ans - 100]
        pool = sorted({v for v in pool if v != ans and v > 0})
        distract = rng.sample(pool, 4)
        extra = f"{ans}.0" if qi % 2 == 0 else f"{ans} or {ans + 1}"          # a second correct form, or a hedge
        cands = [str(ans)] + [str(v) for v in distract] + [extra]
        rng.shuffle(cands)
        questions.append(Question(f"{a} {op} {b}", ans, cands))
        # reference logits: random for wrong answers; the correct forms get total mass p
        z = [rng.gauss(0.0, 0.5) for _ in cands]
        correct = [k for k, c in enumerate(cands) if _is_correct_form(c, ans)]
        wrong_mass = sum(math.exp(z[k]) for k in range(len(cands)) if k not in correct)
        total_correct = p / (1 - p) * wrong_mass
        split = [1.0] if len(correct) == 1 else [0.7, 0.3]
        for k, share in zip(correct, split):
            z[k] = math.log(total_correct * share)
        ref.append(z)
    return Task(questions, ref)


# =============================================================================
# Milestone 1: the verifier, sampling, KL
# =============================================================================
def parse_number(text):
    """The exact numeric value of an answer string as a Fraction, or None if it is not a number.

    "391", " 391\n", "0391", "391.0" and "3.91e2" are all the number 391. "about 391", "391 or 392"
    and "" are not numbers. Use fractions.Fraction (it raises ValueError on junk) so that "0.1" is
    exactly one tenth and no tolerance is needed.
    """
    raise NotImplementedError("TODO milestone 1: parse_number")


def reward(text, answer):
    """The verifiable reward: 1.0 if `text` parses to a number exactly equal to `answer`, else 0.0."""
    raise NotImplementedError("TODO milestone 1: reward")


def sample_index(probs, rng):
    """Draw an index with the given probabilities by inverse CDF using ONE call to rng.random().

    u = rng.random(); return the first k whose running sum of probs exceeds u (the last index if
    rounding leaves u above the total).
    """
    raise NotImplementedError("TODO milestone 1: sample_index")


def kl_divergence(p, q):
    """Exact KL(p || q) = sum_k p_k log(p_k / q_k) over two probability vectors (terms with p_k = 0 are 0)."""
    raise NotImplementedError("TODO milestone 1: kl_divergence")


# =============================================================================
# GIVEN: evaluation of a whole policy (a list of logit vectors, one per question)
# =============================================================================
def rewards_of(q):
    """The verifier's reward for every candidate of question q."""
    return [reward(c, q.answer) for c in q.candidates]


def expected_reward(task, z):
    """Mean over questions of the probability that a sampled answer is correct."""
    return sum(sum(p * r for p, r in zip(softmax(zq), rewards_of(q))) for q, zq in zip(task.questions, z)) / task.n_questions


def greedy_accuracy(task, z):
    """Fraction of questions whose single most likely answer is correct."""
    hits = 0
    for q, zq in zip(task.questions, z):
        best = max(range(len(zq)), key=lambda k: zq[k])
        hits += reward(q.candidates[best], q.answer)
    return hits / task.n_questions


def mean_kl(task, z, ref):
    """Mean over questions of KL(pi_theta || pi_ref): how far the whole policy has drifted."""
    return sum(kl_divergence(softmax(a), softmax(b)) for a, b in zip(z, ref)) / task.n_questions


def copy_logits(z):
    return [row[:] for row in z]


# =============================================================================
# Milestone 2: the DPO loss and its gradient
# =============================================================================
def implicit_rewards(zq, zref_q, beta):
    """The implicit reward of every candidate: beta * (log pi_theta(k) - log pi_ref(k)), as a list (chapter 12)."""
    raise NotImplementedError("TODO milestone 2: implicit_rewards")


def dpo_margin(zq, zref_q, w, l, beta):
    """m = r_hat(w) - r_hat(l), the difference of implicit rewards of the chosen (w) and rejected (l) answers."""
    raise NotImplementedError("TODO milestone 2: dpo_margin")


def dpo_loss(z, ref, pairs, beta):
    """Mean over pairs (q, w, l) of -log sigmoid(margin). z and ref are lists of logit vectors, one per question."""
    raise NotImplementedError("TODO milestone 2: dpo_loss")


def dpo_grads(z, ref, pairs, beta):
    """Gradient of dpo_loss with respect to every logit, as a list of vectors shaped like z.

    For one pair: d loss / d z[w] = -beta * sigmoid(-m), d loss / d z[l] = +beta * sigmoid(-m), and
    nothing else moves (the log-sum-exp terms of the two log-probabilities cancel). Average over pairs.
    """
    raise NotImplementedError("TODO milestone 2: dpo_grads")


# =============================================================================
# Milestone 3: preference pairs from a verifier, and DPO training
# =============================================================================
def make_pairs(task, n, rng, max_attempts=None):
    """Up to n preference pairs (q, chosen, rejected), labelled by the verifier, from the reference policy.

    Repeat: q = rng.randrange(n_questions); draw two candidates a, b from softmax(task.ref[q]) with
    sample_index (a first, then b); if their rewards differ, keep (q, winner, loser). Pairs whose
    rewards tie are discarded. Stop when n pairs are kept or after max_attempts draws
    (default 50 * n), and return what you have.
    """
    raise NotImplementedError("TODO milestone 3: make_pairs")


def train_dpo(task, pairs, beta, lr, steps):
    """Full-batch gradient descent on the DPO loss, starting from the reference logits.

    Returns (z, losses): the trained logits and the loss before each step. task.ref is not modified.
    """
    raise NotImplementedError("TODO milestone 3: train_dpo")


# =============================================================================
# Milestone 4: group-relative advantages
# =============================================================================
def group_advantages(rewards, mode="std", eps=1e-4):
    """Advantages for one group of G sampled answers to the same question.

        "std"   (r_i - mean) / (std + eps)      GRPO as in the R1 paper; std is the POPULATION std (divide by G)
        "mean"  r_i - mean                      no std scaling (Dr. GRPO style)
        "rloo"  r_i - mean of the OTHER G-1 rewards (leave-one-out baseline); needs G >= 2
    """
    raise NotImplementedError("TODO milestone 4: group_advantages")


def zero_signal(rewards):
    """True if every reward in the group is the same, so the group has nothing to teach."""
    raise NotImplementedError("TODO milestone 4: zero_signal")


# =============================================================================
# Milestone 5: the GRPO objective for one group
# =============================================================================
def ratio(zq, zold_q, a):
    """rho = pi_theta(a) / pi_old(a) for the sampled candidate a, computed through log-probabilities."""
    raise NotImplementedError("TODO milestone 5: ratio")


def clipped_objective(rho, adv, eps):
    """PPO's per-sample term min(rho * A, clip(rho, 1 - eps, 1 + eps) * A). This is a quantity to MAXIMISE."""
    raise NotImplementedError("TODO milestone 5: clipped_objective")


def k3(zq, zref_q, a):
    """The k3 estimator of KL(pi_theta || pi_ref) from one sample a: r - log r - 1 with r = pi_ref(a) / pi_theta(a)."""
    raise NotImplementedError("TODO milestone 5: k3")


def grpo_loss_and_grad(zq, zold_q, zref_q, actions, advs, eps, beta):
    """(loss, dz) for ONE group of samples `actions` (candidate indices) with advantages `advs`.

        loss = -(1/G) sum_i clipped_objective(rho_i, A_i, eps)  +  beta * (1/G) sum_i k3_i

    dz is the gradient of that loss with respect to the K logits zq. Per sample, with p = softmax(zq)
    and e_a the one-hot vector of the sampled candidate:
        policy term:  d(-rho A)/dz = -rho * A * (e_a - p), but ZERO when the clip is active, i.e.
                      when (A > 0 and rho > 1 + eps) or (A < 0 and rho < 1 - eps)   (strict inequalities)
        KL term:      d(k3)/dz = (1 - pi_ref(a) / pi_theta(a)) * (e_a - p)
    """
    raise NotImplementedError("TODO milestone 5: grpo_loss_and_grad")


# =============================================================================
# Milestone 6: the GRPO training loop
# =============================================================================
def train_grpo(task, steps, group_size=8, batch_questions=6, inner=4, lr=0.5, eps=0.2, beta=0.04,
               mode="std", seed=0):
    """Train from the reference with GRPO. Returns (z, log) where log is a list of dicts, one per step:
    {"reward": expected_reward after the step, "zero_groups": number of groups with no signal this step}.

    Each step:
      1. pick batch_questions distinct questions (rng.sample(range(n_questions), batch_questions))
      2. for each, freeze z_old = copy of the current logits and sample group_size candidates from
         softmax(z_old) with sample_index; score them with the verifier and compute advantages
      3. repeat `inner` times: for every group take grpo_loss_and_grad at the CURRENT logits (z_old stays
         frozen) and make ONE plain gradient step on the question's logits: z -= lr * dz
    Groups with zero signal still go through step 3 (their policy term is zero, only the KL term acts).
    """
    raise NotImplementedError("TODO milestone 6: train_grpo")


if __name__ == "__main__":
    task = make_task()
    print(f"reference: expected reward {expected_reward(task, task.ref):.3f}, greedy accuracy {greedy_accuracy(task, task.ref):.2f}")
    pairs = make_pairs(task, 400, random.Random(0))
    zd, _ = train_dpo(task, pairs, 0.1, 5.0, 300)
    print(f"DPO ({len(pairs)} pairs): expected reward {expected_reward(task, zd):.3f}, greedy {greedy_accuracy(task, zd):.2f}, KL {mean_kl(task, zd, task.ref):.3f}")
    zg, log = train_grpo(task, 60)
    print(f"GRPO: expected reward {expected_reward(task, zg):.3f}, greedy {greedy_accuracy(task, zg):.2f}, KL {mean_kl(task, zg, task.ref):.3f}")
