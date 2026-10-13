"""Lab 1 starter: a tiny shell built from fork, exec, wait, pipe, dup2 and signals.

Fill in every TODO, one milestone at a time, and run `python3 check.py`
after each one. The lab page walks you through it.

Try your shell by hand any time:
    python3 starter.py          # an interactive prompt

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

    Hints: os.waitstatus_to_exitcode(status) (Python 3.9+) returns N, or -N
    when the process was killed by signal N. On older Pythons use
    os.WIFSIGNALED / os.WTERMSIG / os.WEXITSTATUS.
    """
    raise NotImplementedError("TODO milestone 1: decode_status")


def exec_child(argv, redirs=()):
    """Runs inside the child process. Becomes the program, or exits. Never returns.

    Milestone 1: os.execvp(argv[0], argv). If it raises FileNotFoundError,
        write "sh: NAME: command not found" to fd 2 and os._exit(127).
        Other OSError (e.g. permission denied): message and os._exit(126).
        Use os._exit, never sys.exit or a bare `return`: the child must not
        fall back into the parent's code.
    Milestone 3: before exec, call apply_redirections(redirs).
    Milestone 5: before exec, set SIGINT and SIGPIPE back to signal.SIG_DFL.
    """
    raise NotImplementedError("TODO milestone 1: exec_child")


def run_command(argv, redirs=()):
    """Run one external command and wait for it. Returns its exit code.

    fork(); in the child call exec_child(argv, redirs); in the parent
    os.waitpid(pid, 0) and decode_status(the status).
    Flush sys.stdout and sys.stderr before forking.
    """
    raise NotImplementedError("TODO milestone 1: run_command")


# ---------------------------------------------------------------------------
# Milestone 2: builtins (commands the shell must run itself)
# ---------------------------------------------------------------------------

class ShellExit(Exception):
    """Raised by the `exit` builtin so the main loop (or a test) can stop."""

    def __init__(self, code=0):
        super().__init__(code)
        self.code = code


def run_builtin(argv):
    """Run `cd` or `exit` in this process. Return its status, or None if argv is not a builtin.

    cd [DIR]   os.chdir(DIR); with no DIR go to $HOME. On OSError print
               "sh: cd: DIR: reason" to stderr and return 1.
    exit [N]   raise ShellExit(N)  (N defaults to 0).
    """
    raise NotImplementedError("TODO milestone 2: run_builtin")


# ---------------------------------------------------------------------------
# Milestone 3: redirection  (open + dup2 in the child)
# ---------------------------------------------------------------------------

def parse_redirections(tokens):
    """Split a command's tokens into (argv, redirs).

    redirs is a list of (op, path) with op in "<", ">", ">>".
        ["sort", "<", "in", ">", "out"]  ->  (["sort"], [("<", "in"), (">", "out")])
    Raise ValueError if an operator has no file name after it.
    """
    raise NotImplementedError("TODO milestone 3: parse_redirections")


def apply_redirections(redirs):
    """In the child: point fd 0 or fd 1 at the named files.

        "<"   os.open(path, os.O_RDONLY)                                    -> fd 0
        ">"   os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)   -> fd 1
        ">>"  os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)  -> fd 1

    Then os.dup2(fd, target) and os.close(fd). If os.open fails, write a
    message to fd 2 and os._exit(1).
    """
    raise NotImplementedError("TODO milestone 3: apply_redirections")


# ---------------------------------------------------------------------------
# Milestone 4: pipelines  (os.pipe, and closing the ends you don't use)
# ---------------------------------------------------------------------------

def split_pipeline(tokens):
    """Split tokens on '|' into a list of per-command token lists.

        ["a", "x", "|", "b"]  ->  [["a", "x"], ["b"]]
    Raise ValueError if any command is empty ("| foo", "foo |", "a | | b").
    """
    raise NotImplementedError("TODO milestone 4: split_pipeline")


def run_pipeline(stages):
    """Run [(argv, redirs), ...] connected by pipes. Returns the LAST command's status.

    For each stage except the last: r, w = os.pipe(). Fork. In the child:
    dup2 the previous pipe's read end onto 0 and this pipe's write end onto 1,
    then os.close EVERY pipe descriptor it holds, then exec_child(...).
    In the parent: close the write end you just created and the previous
    read end after forking. Finally waitpid for all children.
    If any write end stays open anywhere, the reader never sees EOF and hangs.
    """
    raise NotImplementedError("TODO milestone 4: run_pipeline")


# ---------------------------------------------------------------------------
# Milestone 5: signals
# ---------------------------------------------------------------------------

def setup_signals():
    """Call once in the shell process: Ctrl-C must not kill the shell itself.

    signal.signal(signal.SIGINT, signal.SIG_IGN). Remember to undo this in
    exec_child, because an ignored signal stays ignored across exec.
    """
    raise NotImplementedError("TODO milestone 5: setup_signals")


# ---------------------------------------------------------------------------
# Putting it together: you grow this function milestone by milestone
# ---------------------------------------------------------------------------

def run_line(line):
    """Run one line of input. Returns the exit status (see the conventions at the top).

    Milestone 1: tokenize; return 0 for an empty line; return run_command(tokens).
    Milestone 2: if run_builtin(argv) returns a status (not None), return that.
    Milestone 3: use parse_redirections(tokens) -> (argv, redirs).
    Milestone 4: split_pipeline(tokens); one stage -> as before,
                 several -> run_pipeline([(argv, redirs), ...]).
    On ValueError (bad syntax, unclosed quote) print "sh: ..." to stderr and return 2.
    """
    raise NotImplementedError("TODO milestone 1: run_line")


def main():
    try:
        setup_signals()
    except NotImplementedError:
        pass                                    # fine until milestone 5
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
