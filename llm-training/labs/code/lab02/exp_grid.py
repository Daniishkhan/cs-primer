from solution import *

env = GridWorld()
table, V, hist = train_reinforce_grid(env, seed=0)
print("mean return per 25 iterations:", [round(sum(hist[i:i + 25]) / 25, 2) for i in range(0, 150, 25)])
ret, win = evaluate(env, table)
print(f"trained policy: return {ret:.2f}, reaches the goal in {100 * win:.0f}% of episodes")
arrows = "^v<>"
for row in range(4):
    cells = []
    for col in range(4):
        s = 4 * row + col
        if s == env.WALL: cells.append("#")
        elif s == env.GOAL: cells.append("G")
        elif s in env.PITS: cells.append("P")
        else:
            p = softmax(table[s])
            cells.append(arrows[p.index(max(p))])
    print(" ".join(cells), "    V:", " ".join(f"{V[4 * row + c]:5.2f}" for c in range(4)))
