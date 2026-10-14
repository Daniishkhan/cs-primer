from solution import candidate_probability, threshold

settings = [(7, 16), (14, 8), (28, 4), (56, 2)]
print("similarity  " + "  ".join(f"{b:>2d} x {r:<2d}" for b, r in settings))
for s in (0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9):
    print(f"{s:>10.2f}  " + "  ".join(f"{candidate_probability(s, b, r):7.3f}" for b, r in settings))
print("threshold   " + "  ".join(f"{threshold(b, r):7.3f}" for b, r in settings))
