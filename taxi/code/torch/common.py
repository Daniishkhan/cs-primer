"""Shared loader for the PyTorch mirrors: the same rides.csv as project.py,
as tensors. Run from taxi/code: ~/lab/bin/python torch/step03.py"""
import csv
import os
from datetime import datetime

import torch

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RIDES5 = [
    (1.60, 6.2, 1, 7.0),
    (0.79, 7.1, 1, 5.0),
    (1.37, 7.4, 1, 7.5),
    (7.70, 25.9, 1, 27.0),
    (2.16, 9.5, 3, 9.0),
]


def load_rides(path=os.path.join(HERE, "rides.csv")):
    """Every ride as a row: distance, minutes, passengers, fare."""
    rows = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            a = datetime.strptime(row["pickup"], "%Y-%m-%d %H:%M:%S")
            b = datetime.strptime(row["dropoff"], "%Y-%m-%d %H:%M:%S")
            rows.append((float(row["distance"]), (b - a).total_seconds() / 60,
                         int(row["passengers"]), float(row["fare"])))
    return torch.tensor(rows, dtype=torch.float64)


def design_matrix(rides):
    """Rows of [1, distance, minutes]: shape (n, 3)."""
    ones = torch.ones(len(rides), 1, dtype=rides.dtype)
    return torch.cat([ones, rides[:, :2]], dim=1)


def targets(rides):
    return rides[:, 3]
