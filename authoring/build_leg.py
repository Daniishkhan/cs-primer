"""Cut a leg's growing program into one file per step.

    python3 authoring/build_leg.py taxi            # writes taxi/code/drills/
    python3 authoring/build_leg.py taxi --verify   # and checks every step file

A leg's code folder (<leg>/code/) holds project.py, the complete program
in step order, with a banner "# ── Step N: title ───" before each step's
code and "# drill" at the end of the def line of every function the
learner writes; check.py checks one step at a time (python3 check.py N).

For each step N this writes <leg>/code/drills/sNN.py: the program up to
and including step N, with step N's drill functions reduced to their
signature, docstring and `raise NotImplementedError("TODO step N: name")`,
plus <leg>/code/drills/leg.json: per step, its title, the drill
functions (name, signature, docstring) and what the file holds so far.
A step page's workspace loads sNN.py, saves it as project.py and runs
check.py N. --verify runs that check for every step and insists the stub
reports "not implemented yet", the step solved with the reference bodies
passes (so no step depends on a later step's function), and the complete
program passes.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANNER = re.compile(r"^# ── Step (\d+): (.*?) ─+\s*$")


def sections(src):
    """[(step or 0, title, [lines])] in file order; 0 is the preamble."""
    out, cur = [], [0, "", []]
    for line in src.split("\n"):
        m = BANNER.match(line)
        if m:
            out.append(tuple(cur))
            cur = [int(m.group(1)), m.group(2).strip(), [line]]
        else:
            cur[2].append(line)
    out.append(tuple(cur))
    return out


def drills_in(step_src, step):
    """The drill functions of one step's source: [(qualified name, node)]."""
    tree = ast.parse(step_src)
    lines = step_src.split("\n")
    out = []

    def walk(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, stack + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if re.search(r"#\s*drill\s*$", lines[child.lineno - 1]):
                    out.append((".".join(stack + [child.name]), child))
                walk(child, stack + [child.name])
    walk(tree, [])
    return out


def stub(step_src, node, qual, step):
    """step_src with the function's body replaced by its docstring and a raise."""
    lines = step_src.split("\n")
    first_body = node.body[0].lineno
    doc = node.body[0] if isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str) else None
    body_start = (doc.end_lineno + 1) if doc else first_body
    indent = re.match(r"\s*", lines[body_start - 1]).group(0) if body_start - 1 < len(lines) else "    "
    if not indent:
        indent = re.match(r"\s*", lines[first_body - 1]).group(0)
    head = lines[:body_start - 1]
    tail = lines[node.end_lineno:]
    return "\n".join(head + [f'{indent}raise NotImplementedError("TODO step {step}: {qual}")'] + tail)


def build(leg, verify):
    code = os.path.join(ROOT, leg, "code")
    src = open(os.path.join(code, "project.py"), encoding="utf-8").read()
    secs = sections(src)
    steps = [s for s in secs if s[0]]
    ddir = os.path.join(code, "drills")
    os.makedirs(ddir, exist_ok=True)
    for f in os.listdir(ddir):
        if re.match(r"s\d\d\.py$", f):
            os.remove(os.path.join(ddir, f))
    meta = []
    failures = []
    preamble = "\n".join(secs[0][2])
    for i, (n, title, lines) in enumerate(steps):
        step_src = "\n".join(lines)
        drills = drills_in(step_src, n)
        if not drills:
            print(f"  warning: step {n} has no '# drill' function")
        stubbed = step_src
        for qual, node in reversed(drills):             # bottom-up keeps line numbers valid
            stubbed = stub(stubbed, node, qual, n)
            stubbed_tree = ast.parse(stubbed)             # must still parse
        earlier = "\n".join("\n".join(s[2]) for s in steps[:i])
        header = [f"# project.py at step {n} of {len(steps)}: {title}",
                  "# Everything up to here is written. Fill in: " + ", ".join(q for q, _ in drills),
                  f"# Check it with: python3 check.py {n}", ""]
        out = "\n".join(header) + preamble.rstrip("\n") + "\n\n\n" + (earlier.rstrip("\n") + "\n\n\n" if earlier.strip() else "") + stubbed.rstrip("\n") + "\n"
        ast.parse(out)
        fname = f"s{n:02d}.py"
        open(os.path.join(ddir, fname), "w", encoding="utf-8").write(out)
        have = [q for s in steps[:i] for q, _ in all_defs("\n".join(s[2]))] + [q for q, _ in all_defs(step_src) if q not in [d[0] for d in drills]]
        meta.append({
            "n": n, "title": title, "file": fname,
            "functions": [{"name": q, "signature": signature(step_src, node), "doc": ast.get_docstring(node) or ""} for q, node in drills],
            "have": have, "lines": out.count("\n"),
        })
        if verify:
            failures += verify_step(code, out, n)
            solved = "\n".join(header) + preamble.rstrip("\n") + "\n\n\n" + (earlier.rstrip("\n") + "\n\n\n" if earlier.strip() else "") + step_src.rstrip("\n") + "\n"
            failures += verify_solved(code, solved, n)
    json.dump({"leg": leg, "steps": meta}, open(os.path.join(ddir, "leg.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{leg}: {len(steps)} steps, {sum(len(m['functions']) for m in meta)} drill functions")
    if verify:
        r = subprocess.run([sys.executable, "-I", "check.py"], cwd=code, capture_output=True, text=True)
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
        print("complete program:", last)
        if r.returncode != 0:
            failures.append("the complete program does not pass check.py")
        print(f"verify: {len(failures)} problem(s)")
        for f in failures:
            print("  " + f)
        if failures:
            sys.exit(1)


def all_defs(src):
    out = []

    def walk(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, stack + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append((".".join(stack + [child.name]), child))
    walk(ast.parse(src), [])
    return out


def signature(src, node):
    lines = src.split("\n")
    first_body = node.body[0].lineno if node.body else node.lineno + 1
    sig = "\n".join(l.strip() for l in lines[node.lineno - 1:max(node.lineno, first_body - 1)]).strip()
    return re.sub(r"\s*#\s*drill\s*$", "", sig)


def verify_step(code, src, n):
    with tempfile.TemporaryDirectory() as tmp:
        for f in os.listdir(code):
            if f.endswith((".py", ".csv")) and f != "project.py":
                shutil.copy(os.path.join(code, f), tmp)
        open(os.path.join(tmp, "project.py"), "w", encoding="utf-8").write(src)
        try:
            r = subprocess.run([sys.executable, "-I", "check.py", str(n)], cwd=tmp, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return [f"step {n}: check.py {n} timed out"]
        out = r.stdout + r.stderr
        tail = "\n    " + out.strip().replace("\n", "\n    ")[-500:]
        if "Traceback" in out:
            return [f"step {n}: the checker crashed:" + tail]
        if "not implemented yet" not in out:
            return [f"step {n}: the stub did not report 'not implemented yet':" + tail]
        m = re.search(r"(\d+)/(\d+) steps passing", out)
        if not m or int(m.group(1)) != 0:
            return [f"step {n}: the stub should fail its step:" + tail]
    return []


def verify_solved(code, src, n):
    """The program up to step N with step N written must pass check.py N:
    a step may not use a function that a later step introduces."""
    with tempfile.TemporaryDirectory() as tmp:
        for f in os.listdir(code):
            if f.endswith((".py", ".csv")) and f != "project.py":
                shutil.copy(os.path.join(code, f), tmp)
        open(os.path.join(tmp, "project.py"), "w", encoding="utf-8").write(src)
        try:
            r = subprocess.run([sys.executable, "-I", "check.py", str(n)], cwd=tmp, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return [f"step {n}: check.py {n} on the solved step timed out"]
        out = r.stdout + r.stderr
        m = re.search(r"(\d+)/(\d+) steps passing", out)
        if not m or int(m.group(1)) != 1:
            tail = "\n    " + out.strip().replace("\n", "\n    ")[-500:]
            return [f"step {n}: the solved step does not pass its own check (a later step's function used?):" + tail]
    return []


if __name__ == "__main__":
    legs = [a for a in sys.argv[1:] if not a.startswith("--")] or ["taxi"]
    for leg in legs:
        build(leg, "--verify" in sys.argv)
