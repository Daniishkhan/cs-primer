"""An architecture fitness function: the module rules as a unit test.

CI runs it on every change, so a forbidden import fails the build the same way a broken
test does.   python3 test_boundaries.py     (or: python3 -m unittest test_boundaries)

SHOP_ROOT lets the lab's check point it at another copy of the code; by default it checks
the shop/ folder next to this file.
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
    def setUp(self):
        self.imports = archtool.extract_imports(ROOT)

    def test_no_boundary_violations(self):
        violations = archtool.check_boundaries(self.imports)
        report = "\n".join(f"{v.file}:{v.line}: [{v.rule}] {v.message}" for v in violations)
        self.assertEqual([], violations, "\n" + report)

    def test_no_dependency_cycles(self):
        cycles = archtool.find_cycles(archtool.module_graph(self.imports))
        report = "\n".join(" -> ".join(c + [c[0]]) for c in cycles)
        self.assertEqual([], cycles, "\n" + report)


if __name__ == "__main__":
    unittest.main()
