"""A stand-in evaluator for the checks: prints the file named in argv[1].

Used by check.py to play evaluators that lie: one that signs nothing, one
that replays an old genuine result, one that answers about another solution.
"""
import sys

sys.stdout.write(open(sys.argv[1]).read())
