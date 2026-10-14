import random
from solution import *

env = GridWorld()
ref = reference_table(env)
print(f"{'beta':>5s} {'exact KL':>9s} {'mean k3':>8s} {'return':>7s} {'success':>8s}")
for beta in (0.0, 0.1, 0.3, 1.0, 3.0):
    table, _ = train_ppo_grid(env, ref, beta, seed=0)
    ret, win = evaluate(env, table)
    rng, exact, k3, n = random.Random(1), 0.0, 0.0, 0
    for _ in range(300):
        states, actions, _ = run_episode(env, table, rng)
        for s, a in zip(states, actions):
            exact += kl_divergence(softmax(table[s]), softmax(ref[s]))
            k3 += kl_k3(log_softmax(table[s])[a], log_softmax(ref[s])[a])
            n += 1
    print(f"{beta:5.1f} {exact / n:9.3f} {k3 / n:8.3f} {ret:7.2f} {win:8.2f}")
