"""Self-check for Lab 1.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Every test runs your shell in a separate Python process (a "driver"), so a
crash, a hang or a stray fork can never take check.py down with it. The driver
calls run_line() for each line and prints the returned status; whatever the
child programs print is captured from the inherited stdout.
Prints ✔ / ✘ / … (not implemented yet) per milestone.
"""
import json
import os
import re
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import time

if os.name != "posix":
    print("Lab 1 needs fork, pipes and signals, which exist only on POSIX systems.")
    print("Use macOS, Linux, or Windows with WSL (then run this inside the WSL terminal).")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else "starter"
results = []

# The driver runs inside the subprocess. MAIN guards against a classic bug: if
# your child forgets to exec/_exit and "returns", it would keep running the
# driver. We stop any such stray process here.
DRIVER = r'''
import importlib, json, os, sys, traceback
sys.path.insert(0, %(here)r)
MAIN = os.getpid()
try:
    m = importlib.import_module(%(target)r)
    for expr in %(probes)r:
        eval(expr, {"m": m})
    for line in json.loads(sys.argv[1]):
        try:
            st = m.run_line(line)
            print("@@status %%d" %% st, flush=True)
        except m.ShellExit as e:
            print("@@exit %%d" %% e.code, flush=True)
            break
except BaseException:
    traceback.print_exc()
    sys.stderr.flush()
    if os.getpid() != MAIN:
        os._exit(99)
    sys.exit(1)
if os.getpid() != MAIN:
    os._exit(99)
'''


class NotStarted(Exception):
    pass


def check(name, fn):
    try:
        fn()
        print(f"  ✔ {name}")
        results.append(True)
    except NotStarted as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)


def kill_group(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def raise_if_unimplemented(stderr):
    m = re.search(r"NotImplementedError: (.*)", stderr)
    if m:
        raise NotStarted(m.group(1).strip())


def drive(lines, cwd, probes=(), timeout=10, env_extra=None):
    """Run lines through the shell in a subprocess. Returns (stdout, stderr, statuses)."""
    env = dict(os.environ, **(env_extra or {}))
    code = DRIVER % {"here": HERE, "target": target, "probes": list(probes)}
    p = subprocess.Popen([sys.executable, "-c", code, json.dumps(lines)], cwd=cwd, env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True, text=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_group(p)
        p.communicate()
        raise AssertionError(f"the shell hung (no result after {timeout} s) while running {lines!r}. "
                             "Common cause: a pipe write end that was never closed, so a reader waits for EOF forever")
    finally:
        kill_group(p)           # no stray children, whatever happened
    raise_if_unimplemented(err)
    statuses = [int(x) for x in re.findall(r"@@(?:status|exit) (-?\d+)", out)]
    clean = re.sub(r"@@(?:status|exit) -?\d+\n?", "", out)
    if p.returncode not in (0,) and not statuses:
        raise AssertionError("the shell crashed:\n" + err.strip()[-600:])
    return clean, err, statuses, out


# --- Milestone 1 -------------------------------------------------------------------

def m1():
    with tempfile.TemporaryDirectory() as tmp:
        lines = ["echo hi", "false", "definitely-not-a-command-xyz", "sh -c 'exit 7'",
                 "sh -c 'kill -TERM $$'", "true", "   ", "echo 'two  words'"]
        out, err, st, raw = drive(lines, tmp)
        assert out == "hi\ntwo  words\n", f"expected stdout 'hi\\ntwo  words\\n', got {out!r}"
        assert st == [0, 1, 127, 7, 143, 0, 0, 0], (
            f"expected statuses [0, 1, 127, 7, 143, 0, 0, 0] (ok, false=1, not found=127, exit 7, "
            f"killed by SIGTERM=128+15, ok, blank line, ok), got {st}")
        assert "definitely-not-a-command-xyz" in err and "not found" in err, \
            f"expected a 'command not found' message on stderr, got {err!r}"
        assert raw.count("hi") == 1, "output appeared twice: flush stdout before forking, and use os._exit in the child"


# --- Milestone 2 -------------------------------------------------------------------

def m2():
    with tempfile.TemporaryDirectory() as tmp:
        home = os.path.join(tmp, "home")
        os.mkdir(home)
        lines = [f"cd {shlex.quote(tmp)}", "pwd", "cd home", "pwd", "cd", "pwd",
                 "cd /no/such/dir/anywhere", "pwd", "exit 3", "echo not-reached"]
        out, err, st, _ = drive(lines, "/", probes=["m.run_builtin(['true'])"], env_extra={"HOME": home})
        paths = out.split()
        assert len(paths) == 4, f"expected 4 lines from pwd, got {out!r}"
        want = [os.path.realpath(tmp), os.path.realpath(home), os.path.realpath(home), os.path.realpath(home)]
        got = [os.path.realpath(p) for p in paths]
        assert got[0] == want[0], f"after `cd <tmp>`, pwd printed {paths[0]!r}; expected {want[0]!r}. Did cd run in the child?"
        assert got[1] == want[1], f"after `cd home`, pwd printed {paths[1]!r}; expected {want[1]!r}"
        assert got[2] == want[2], f"`cd` with no argument should go to $HOME; pwd printed {paths[2]!r}"
        assert got[3] == want[3], "a failed cd must leave the directory unchanged"
        assert st[:6] == [0] * 6 and st[6] == 1 and st[7] == 0, f"cd statuses should be 0 (and 1 for the bad directory), got {st}"
        assert "no/such/dir" in err or "/no/such/dir/anywhere" in err, f"cd should print an error to stderr, got {err!r}"
        assert st[-1] == 3 and len(st) == 9, f"`exit 3` should raise ShellExit(3) and stop the run; got {st}"
        assert "not-reached" not in out


# --- Milestone 3 -------------------------------------------------------------------

def m3():
    with tempfile.TemporaryDirectory() as tmp:
        lines = ["echo one > f.txt", "echo two >> f.txt", "cat < f.txt", "cat < f.txt > g.txt",
                 "echo three > h.txt", "echo four>h.txt", "cat < missing.txt", "echo 'a > b'"]
        out, err, st, _ = drive(lines, tmp, probes=["m.parse_redirections(['true'])"])

        def read(name):
            with open(os.path.join(tmp, name)) as f:
                return f.read()
        assert out == "one\ntwo\na > b\n", f"stdout should be 'one\\ntwo\\na > b\\n' (redirected output must not reach the screen), got {out!r}"
        assert read("f.txt") == "one\ntwo\n", f"> then >> should leave 'one\\ntwo\\n' in f.txt, got {read('f.txt')!r}"
        assert read("g.txt") == "one\ntwo\n", f"`cat < f.txt > g.txt` should copy the file; g.txt has {read('g.txt')!r}"
        assert read("h.txt") == "four\n", f"`>` must truncate the file first; h.txt has {read('h.txt')!r}"
        assert st == [0, 0, 0, 0, 0, 0, 1, 0], f"expected statuses [0,0,0,0,0,0,1,0] (missing input file gives 1), got {st}"
        assert "missing.txt" in err, f"opening a missing input file should print an error naming it, got {err!r}"
        # a syntax error is reported, not crashed on
        out, err, st, _ = drive(["echo hi >"], tmp)
        assert st == [2] and err.strip(), f"`echo hi >` should print an error and return 2, got status {st}, stderr {err!r}"


# --- Milestone 4 -------------------------------------------------------------------

def m4():
    with tempfile.TemporaryDirectory() as tmp:
        lines = ["printf 'a\\nb\\nc\\n' | sort -r | head -n 2", "echo hello | tr a-z A-Z",
                 "printf 'x\\ny\\n' | sort -r > p.txt", "echo hi | false", "false | true",
                 "echo x | no-such-program-xyz", "yes | head -n 1"]
        out, err, st, _ = drive(lines, tmp, probes=["m.split_pipeline(['true'])"], timeout=15)
        assert out == "c\nb\nHELLO\ny\n", f"expected stdout 'c\\nb\\nHELLO\\ny\\n', got {out!r}"
        with open(os.path.join(tmp, "p.txt")) as f:
            assert f.read() == "y\nx\n", "redirection should still work on the last stage of a pipeline"
        assert st == [0, 0, 0, 1, 0, 127, 0], f"a pipeline's status is its LAST command's: expected [0,0,0,1,0,127,0], got {st}"
        # many pipelines in one process: leaked descriptors would pile up
        out, err, st, _ = drive(["echo x | cat"] * 40 + ["echo done"], tmp, timeout=20)
        assert out == "x\n" * 40 + "done\n" and st == [0] * 41, "40 pipelines in a row should all work"
        out, err, st, _ = drive(["echo hi |", "| cat"], tmp)
        assert st == [2, 2], f"an empty pipeline stage is a syntax error (status 2), got {st}"


# --- Milestone 5 -------------------------------------------------------------------

def m5():
    with tempfile.TemporaryDirectory() as tmp:
        code = DRIVER % {"here": HERE, "target": target, "probes": ["m.setup_signals()", "print('@@ready', flush=True)"]}
        p = subprocess.Popen([sys.executable, "-c", code, json.dumps(["sleep 5", "echo alive", "sleep 5 | sleep 5"])],
                             cwd=tmp, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)       # its own process group, like a terminal's foreground group
        buf = b""

        def pump(wait):
            nonlocal buf
            r, _, _ = select.select([p.stdout], [], [], wait)
            if r:
                chunk = os.read(p.stdout.fileno(), 4096)
                buf += chunk
                return bool(chunk)
            return True

        try:
            deadline = time.time() + 5
            while b"@@ready" not in buf:
                if time.time() > deadline or not pump(0.1):
                    break
            if b"@@ready" not in buf:
                p.wait(timeout=3)
                err = p.stderr.read().decode()
                raise_if_unimplemented(err)
                raise AssertionError("the shell did not start: " + err.strip()[-400:])
            start = time.time()
            for want in (1, 3):                  # first `sleep 5`, then the pipeline `sleep 5 | sleep 5`
                # Like pressing Ctrl-C: the signal goes to the whole foreground process group.
                # We repeat it until the status shows up, in case the child had not started yet.
                end = time.time() + 6
                while buf.count(b"@@status") < want and time.time() < end:
                    try:
                        os.killpg(p.pid, signal.SIGINT)
                    except (ProcessLookupError, PermissionError):
                        break
                    t = time.time() + 0.25
                    while time.time() < t and buf.count(b"@@status") < want:
                        pump(0.05)
                if want == 1:
                    while b"alive" not in buf and time.time() < end:    # let `echo alive` run before more signals
                        pump(0.05)
                    time.sleep(0.05)
            while p.poll() is None and time.time() < start + 12:
                pump(0.05)
            err = p.stderr.read().decode() if p.poll() is not None else ""
            text = buf.decode()
            statuses = [int(x) for x in re.findall(r"@@status (-?\d+)", text)]
            if p.poll() is None:
                raise AssertionError("the shell is stuck after Ctrl-C")
            if "KeyboardInterrupt" in err:
                raise AssertionError("SIGINT reached the shell itself and raised KeyboardInterrupt. Ignore it with signal.SIG_IGN in setup_signals()")
            if p.returncode != 0 and len(statuses) < 3:
                raise AssertionError(f"the shell died (exit code {p.returncode}), so Ctrl-C was not survived. {err.strip()[-300:]}")
            assert time.time() - start < 11, "the 5-second sleeps ran to the end: Ctrl-C did not stop them"
            assert statuses == [130, 0, 130], (
                f"expected statuses [130, 0, 130] (`sleep` killed by SIGINT = 128+2, then `echo alive`, then the pipeline's last "
                f"command killed by SIGINT), got {statuses}. If a sleep ran the full 5 s, the child inherited the ignored SIGINT: "
                f"restore SIG_DFL before exec")
            assert "alive" in text, "the shell should keep working after Ctrl-C: `echo alive` never printed"
        finally:
            kill_group(p)
            p.stdout.close()
            p.stderr.close()
            p.wait()


print(f"Lab 1 checks against {target}.py\n")
check("Milestone 1: run one command (fork, exec, wait, 127)", m1)
check("Milestone 2: builtins cd and exit", m2)
check("Milestone 3: redirection  <  >  >>", m3)
check("Milestone 4: pipelines  a | b | c", m4)
check("Milestone 5: Ctrl-C stops the command, not the shell", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else ""))
sys.exit(0 if passed == len(results) else 1)
