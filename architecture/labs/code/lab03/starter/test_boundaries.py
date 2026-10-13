"""Milestone 5 (optional): the module rules as a unit test that CI can run.

    python3 test_boundaries.py

SHOP_ROOT lets the lab's check point this test at another copy of the code; by default it
checks the shop/ folder next to this file.

TODO: write two tests with your archtool functions (extract_imports, check_boundaries,
module_graph, find_cycles):
  * no boundary violations, with the violations listed in the failure message;
  * no dependency cycles, with the cycles listed in the failure message.
Delete the NotImplementedError line when you are done.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("SHOP_ROOT", HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import archtool  # noqa: E402


class BoundaryTests(unittest.TestCase):
    def test_no_boundary_violations(self):
        raise NotImplementedError("TODO milestone 5: assert there are no violations")

    def test_no_dependency_cycles(self):
        raise NotImplementedError("TODO milestone 5: assert there are no cycles")


if __name__ == "__main__":
    unittest.main()
