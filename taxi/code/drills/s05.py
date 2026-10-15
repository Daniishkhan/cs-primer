# project.py at step 5 of 20: the loss surface
# Everything up to here is written. Fill in: sweep
# Check it with: python3 check.py 5
"""project.py: the program that grows, one step at a time, from five taxi
rides to a loop that improves a model of their fares.

Each step adds one or two functions marked "# drill": those are yours to
write. Everything else is given. Check a step with

    python3 check.py 7        # step 7 only, against this file
    python3 check.py          # every step so far

The data is rides.csv: 6,367 real New York taxi rides from March 2019,
the seaborn sample of the city's public Taxi and Limousine Commission
records, trimmed to pickup, dropoff, passengers, distance, fare and the
pickup borough. Standard library only.
"""
import csv
import hashlib
import json
import math
import random
from datetime import datetime


# ── Step 1: five rides and a guess ─────────────────────────────────────
# Five real rides: distance in miles, minutes on the road, passengers, fare.
RIDES5 = [
    (1.60, 6.2, 1, 7.0),
    (0.79, 7.1, 1, 5.0),
    (1.37, 7.4, 1, 7.5),
    (7.70, 25.9, 1, 27.0),
    (2.16, 9.5, 3, 9.0),
]


def guess(distance, base, per_mile):  # drill
    """A fare guess for one ride: a flag-drop `base` plus `per_mile` for
    every mile. guess(1.6, 2.5, 2.0) is 5.7."""
    return base + per_mile * distance


def total_error(rides, base, per_mile):  # drill
    """How wrong the guess is over many rides: the sum of |guess - fare|,
    in dollars. rides are (distance, minutes, passengers, fare) tuples.
    total_error(RIDES5, 2.5, 2.0) is 15.76."""
    return sum(abs(guess(d, base, per_mile) - fare) for d, _, _, fare in rides)


# ── Step 2: a ride is a vector ─────────────────────────────────────────
def features(ride):
    """A ride as a list of numbers the model reads: a constant 1 (for the
    flag-drop), distance in miles, minutes on the road."""
    distance, minutes, _, _ = ride
    return [1.0, distance, minutes]


def dot(x, w):  # drill
    """The dot product: multiply entries pairwise and add them up.
    dot([1, 2, 3], [4, 5, 6]) is 32. Different lengths raise ValueError."""
    if len(x) != len(w):
        raise ValueError(f"length mismatch: {len(x)} vs {len(w)}")
    return sum(a * b for a, b in zip(x, w))


def predict(ride, w):  # drill
    """The fare a weight vector predicts for one ride: dot(features, w).
    With w = [2.5, 2.0, 0.0] this is step 1's guess again."""
    return dot(features(ride), w)


# ── Step 3: many rides are a matrix ────────────────────────────────────
def load_rides(path="rides.csv"):
    """Every ride in the file as (distance, minutes, passengers, fare)."""
    rides = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            a = datetime.strptime(row["pickup"], "%Y-%m-%d %H:%M:%S")
            b = datetime.strptime(row["dropoff"], "%Y-%m-%d %H:%M:%S")
            minutes = (b - a).total_seconds() / 60
            rides.append((float(row["distance"]), minutes,
                          int(row["passengers"]), float(row["fare"])))
    return rides


def design_matrix(rides):
    """One row of features per ride: a list of lists, shape (n, 3)."""
    return [features(r) for r in rides]


def targets(rides):
    """The true fares, one per ride."""
    return [r[3] for r in rides]


def matvec(X, w):  # drill
    """Predict every ride at once: the matrix-vector product, one dot
    product per row. matvec([[1, 2], [3, 4]], [1, 1]) is [3, 7]."""
    return [dot(row, w) for row in X]


# ── Step 4: a loss ─────────────────────────────────────────────────────
def mse(pred, y):  # drill
    """Mean squared error: average over rides of (prediction - fare)^2.
    mse([1, 2], [1, 4]) is 2.0. Squaring punishes big misses most."""
    if len(pred) != len(y):
        raise ValueError(f"length mismatch: {len(pred)} vs {len(y)}")
    return sum((p - t) ** 2 for p, t in zip(pred, y)) / len(y)


def loss(X, y, w):
    """The loss of weights w on data (X, y): mse of the predictions."""
    return mse(matvec(X, w), y)


# ── Step 5: the loss surface ───────────────────────────────────────────
def sweep(X, y, w, index, values):  # drill
    """Vary one weight and watch the loss: for each value, set w[index]
    to it (leaving the others as they are) and record (value, loss).
    Returns the list of pairs, in the order given."""
    raise NotImplementedError("TODO step 5: sweep")
