"""Build the one small tabular task: Ames house prices, split three ways.

    python make_task.py --aide-dir PATH/TO/aide/example_tasks/house_prices

Writes, next to this script's working directory:
    task/train.csv, task/data_description.txt   what the agent may see
    task/test.csv                               the same rows, no SalePrice
    private/test_labels.csv                     only the evaluator reads it

The task folder is what you hand to aideml as data_dir. The private folder
stays outside it: the agent's code runs in a copy of task/ and never sees
the labels, which is the public/private split of chapter 3.
"""
import argparse
import csv
import os
import random
import shutil

ap = argparse.ArgumentParser()
ap.add_argument("--aide-dir", required=True)
ap.add_argument("--n-private", type=int, default=360)   # rows held back
ap.add_argument("--seed", type=int, default=0)          # fixes the split
args, _ = ap.parse_known_args()

# ── 1. Read the 1,460 labelled rows that ship with aideml ────────────────
with open(os.path.join(args.aide_dir, "train.csv"), newline="") as f:
    rows = list(csv.DictReader(f))
header = list(rows[0].keys())

# ── 2. Split: 1,100 public rows with labels, 360 private ones ────────────
random.Random(args.seed).shuffle(rows)
private, public = rows[:args.n_private], rows[args.n_private:]
os.makedirs("task", exist_ok=True)
os.makedirs("private", exist_ok=True)

with open("task/train.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=header)
    w.writeheader()
    w.writerows(public)
with open("task/test.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[h for h in header if h != "SalePrice"])
    w.writeheader()
    for r in private:
        w.writerow({k: v for k, v in r.items() if k != "SalePrice"})
with open("task/sample_submission.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Id", "SalePrice"])
    for r in private:
        w.writerow([r["Id"], 163000])
with open("private/test_labels.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Id", "SalePrice"])
    for r in private:
        w.writerow([r["Id"], r["SalePrice"]])
shutil.copy(os.path.join(args.aide_dir, "data_description.txt"), "task/")

# ── 3. Say what was written ──────────────────────────────────────────────
print(f"public train rows {len(public)}, private test rows {len(private)}")
print("agent sees: " + ", ".join(sorted(os.listdir("task"))))
print("evaluator only: " + ", ".join(sorted(os.listdir("private"))))
