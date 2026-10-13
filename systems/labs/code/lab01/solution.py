"""Lab 1 solution: a tiny shell built from fork, exec, wait, pipe, dup2 and signals.

Run it:
    python3 solution.py          # an interactive prompt: try  ls | sort -r | head -n 3

POSIX only (macOS, Linux, WSL): there is no fork on plain Windows.

Conventions used by this shell (and by check.py):
  * run_line(line) returns the command's exit status as an int.
  * A command killed by signal N reports 128 + N, like bash does.
    So Ctrl-C (SIGINT = 2) shows up as 130 and SIGTERM (15) as 143.
  * "command not found" is 127, "found but could not be run" is 126.
  * Child output goes to the inherited stdout/stderr (file descriptors 1 and 2).
"""
import os
import shlex
import signal
import sys


# ---------------------------------------------------------------------------
# Tokenizing (given: parsing is not the lesson of this lab)
# ---------------------------------------------------------------------------

def tokenize(line):
    """Split a line into words, treating | < > >> as separate tokens.

    Quotes work as in a real shell: echo "a  b" gives one word. Raises
    ValueError for an unclosed quote. Limitation: a quoted '|' by itself
    looks the same as the pipe operator (a stretch goal fixes this).
    """
    lex = shlex.shlex(line, posix=True, punctuation_chars="|<>")
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


# ---------------------------------------------------------------------------
# Milestone 1: run one command  (fork, exec, wait)
# ---------------------------------------------------------------------------

def decode_status(status):
    """Turn the raw status from os.waitpid into a shell-style exit code.

    Normal exit with code N        -> N
    Killed by signal N             -> 128 + N   (bash's convention)
    """
    if hasattr(os, "waitstatus_to_exitcode"):          # Python 3.9+
        code = os.waitstatus_to_exitcode(status)       # negative means "killed by signal"
        return code if code >= 0 else 128 - code
    if os.WIFSIGNALED(status):                         # older Pythons: decode by hand
        return 128 + os.WTERMSIG(status)
    return os.WEXITSTATUS(status)


def exec_child(argv, redirs=()):
    """Runs inside the child process. Becomes the program, or exits. Never returns."""
    code = 127
    try:
        # Milestone 5: ignored signals survive exec, so put the defaults back.
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # Python ignores SIGPIPE at startup
        # Milestone 3: wire up files before the program starts.
        apply_redirections(redirs)
        os.execvp(argv[0], argv)                        # on success this never returns
    except FileNotFoundError:
        os.write(2, f"sh: {argv[0]}: command not found\n".encode())
        code = 127
    except OSError as e:                                # e.g. permission denied
        os.write(2, f"sh: {argv[0]}: {e.strerror}\n".encode())
        code = 126
    except BaseException as e:                          # a bug of ours: still must not escape
        os.write(2, f"sh: internal error in child: {e!r}\n".encode())
        code = 126
    # os._exit, not sys.exit: sys.exit would run the PARENT's cleanup code and
    # unwind into the shell's main loop, leaving two shells reading your keyboard.
    os._exit(code)


def run_command(argv, redirs=()):
    """Run one external command and wait for it. Returns its exit code."""
    sys.stdout.flush()                  # don't let buffered text be copied into the child
    sys.stderr.flush()
    pid = os.fork()
    if pid == 0:
        exec_child(argv, redirs)        # never returns
    _, status = os.waitpid(pid, 0)
    return decode_status(status)


# ---------------------------------------------------------------------------
# Milestone 2: builtins (commands the shell must run itself)
# ---------------------------------------------------------------------------

class ShellExit(Exception):
    """Raised by the `exit` builtin so the main loop (or a test) can stop."""

    def __init__(self, code=0):
        super().__init__(code)
        self.code = code


def run_builtin(argv):
    """Run `cd` or `exit` in this process. Return its status, or None if argv is not a builtin."""
    name = argv[0]
    if name == "cd":
        target = argv[1] if len(argv) > 1 else os.environ.get("HOME", "/")
        try:
            os.chdir(target)            # changes THIS process's working directory
        except OSError as e:
            print(f"sh: cd: {target}: {e.strerror}", file=sys.stderr)
            return 1
        return 0
    if name == "exit":
        try:
            code = int(argv[1]) if len(argv) > 1 else 0
        except ValueError:
            print("sh: exit: numeric argument required", file=sys.stderr)
            code = 2
        raise ShellExit(code)
    return None


# ---------------------------------------------------------------------------
# Milestone 3: redirection  (open + dup2 in the child)
# ---------------------------------------------------------------------------

def parse_redirections(tokens):
    """Split a command's tokens into (argv, redirs).

    redirs is a list of (op, path) with op in "<", ">", ">>".
    Raises ValueError if an operator has no file name after it.
    """
    argv, redirs = [], []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("<", ">", ">>"):
            if i + 1 >= len(tokens) or tokens[i + 1] in ("<", ">", ">>", "|"):
                raise ValueError(f"syntax error: expected a file name after {tok}")
            redirs.append((tok, tokens[i + 1]))
            i += 2
        else:
            argv.append(tok)
            i += 1
    return argv, redirs


def apply_redirections(redirs):
    """In the child: point fd 0 or fd 1 at the named files."""
    for op, path in redirs:
        if op == "<":
            flags, target_fd = os.O_RDONLY, 0
        elif op == ">":
            flags, target_fd = os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 1
        else:  # ">>"
            flags, target_fd = os.O_WRONLY | os.O_CREAT | os.O_APPEND, 1
        try:
            fd = os.open(path, flags, 0o666)
        except OSError as e:
            os.write(2, f"sh: {path}: {e.strerror}\n".encode())
            os._exit(1)
        os.dup2(fd, target_fd)          # now fd 0/1 refers to the file
        os.close(fd)                    # the extra descriptor is no longer needed


# ---------------------------------------------------------------------------
# Milestone 4: pipelines  (os.pipe, and closing the ends you don't use)
# ---------------------------------------------------------------------------

def split_pipeline(tokens):
    """Split tokens on '|' into a list of per-command token lists.

    Raises ValueError if any command is empty ("| foo", "foo |", "a | | b").
    """
    stages, current = [], []
    for tok in tokens:
        if tok == "|":
            if not current:
                raise ValueError("syntax error near |")
            stages.append(current)
            current = []
        else:
            current.append(tok)
    if not current:
        raise ValueError("syntax error near |")
    stages.append(current)
    return stages


def run_pipeline(stages):
    """Run [(argv, redirs), ...] connected by pipes. Returns the LAST command's status."""
    sys.stdout.flush()
    sys.stderr.flush()
    pids = []
    prev_read = None                            # read end of the previous pipe
    for i, (argv, redirs) in enumerate(stages):
        is_last = i == len(stages) - 1
        read_end = write_end = None
        if not is_last:
            read_end, write_end = os.pipe()
        pid = os.fork()
        if pid == 0:
            # --- child: wire stdin/stdout, then close EVERY pipe descriptor we hold
            if prev_read is not None:
                os.dup2(prev_read, 0)
            if write_end is not None:
                os.dup2(write_end, 1)
            for fd in (prev_read, read_end, write_end):
                if fd is not None:
                    os.close(fd)                # the dup2 copies on 0/1 are enough
            exec_child(argv, redirs)
        # --- parent
        pids.append(pid)
        if prev_read is not None:
            os.close(prev_read)                 # this pipe is fully handed over
        if write_end is not None:
            os.close(write_end)                 # CRUCIAL: else the next reader never sees EOF
        prev_read = read_end
    status = 0
    for pid in pids:
        _, st = os.waitpid(pid, 0)
        status = decode_status(st)              # keep the last one
    return status


# ---------------------------------------------------------------------------
# Milestone 5: signals
# ---------------------------------------------------------------------------

def setup_signals():
    """Call once in the shell process: Ctrl-C must not kill the shell itself."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # (exec_child puts SIGINT and SIGPIPE back to SIG_DFL in each child.)


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

def run_line(line):
    """Run one line of input. Returns the exit status (see the conventions at the top)."""
    try:
        tokens = tokenize(line)
        if not tokens:
            return 0
        stages = [parse_redirections(s) for s in split_pipeline(tokens)]
        if any(not argv for argv, _ in stages):
            raise ValueError("syntax error: missing command")
    except ValueError as e:
        print(f"sh: {e}", file=sys.stderr)
        return 2
    if len(stages) == 1:
        argv, redirs = stages[0]
        status = run_builtin(argv)              # builtins only run when alone on the line
        if status is not None:
            return status
        return run_command(argv, redirs)
    return run_pipeline(stages)


def main():
    setup_signals()
    status = 0
    while True:
        try:
            line = input(f"mini[{status}]$ " if status else "mini$ ")
        except EOFError:                        # Ctrl-D
            print()
            break
        try:
            status = run_line(line)
        except ShellExit as e:
            status = e.code
            break
    sys.exit(status)


if __name__ == "__main__":
    main()
