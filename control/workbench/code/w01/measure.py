"""Workbench 1: a locked-down research sandbox, and what it costs.

Run on the lab VM after `bash setup_sandbox.sh`:
    python3 measure.py                  # both parts, 7 timed runs each
    python3 measure.py --repeats 3 --experiments 10     # quicker
    python3 measure.py --only attack    # or: --only timing

Part 1 runs the same research loop, whose proposer tries to carry a secret
out of the box, in three settings: no protection, a separate user behind a
kernel firewall rule, and the full sandbox. Part 2 times the loop in four
settings to price each layer. Needs: bubblewrap, nft and sudo (all set up
by setup_sandbox.sh) and nothing outside the standard library.
"""
import argparse
import json
import os
import pwd
import re
import statistics
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── 1. Settings ───────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--repeats", type=int, default=7)
ap.add_argument("--experiments", type=int, default=200)
ap.add_argument("--only", choices=["attack", "timing"])
args, _ = ap.parse_known_args()    # notebooks pass their own flags

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
    else os.getcwd()
PY, LOOP = "/usr/bin/python3", "/opt/w01/research_loop.py"
PROXY = "http://127.0.0.1:3128"
CANARY_PORT = 9000
RUN = "/var/tmp/w01"
AGENT = "labagent"
LIMITS = ["prlimit", "--cpu=120", "--as=2147483648", "--nproc=128",
          "--nofile=256", "--fsize=104857600", "--"]   # per-process rlimits


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def fresh_dir(name):
    """A new empty directory the sandboxed user can write to."""
    path = f"{RUN}/{name}"
    sh(["sudo", "-n", "rm", "-rf", path])
    sh(["sudo", "-n", "install", "-d", "-o", AGENT, "-g", AGENT,
        "-m", "700", path])
    return path


def bwrap(workdir, inner, real_home=False):
    """The sandbox: bubblewrap run as root (it then needs no user
    namespace), with new pid/ipc/uts namespaces, a read-only /usr, an
    empty home and /tmp, one writable directory and a cleared environment.
    Inside, setpriv drops to the agent user before anything of ours runs:
    its uid and gid, no extra groups, no new privileges, no capabilities."""
    pw = pwd.getpwnam(AGENT)          # looked up here: /etc/passwd is not
    home = (["--bind", pw.pw_dir, pw.pw_dir] if real_home    # in the box
            else ["--perms", "1777", "--tmpfs", pw.pw_dir])
    parents = [x for d in ("/etc", "/opt", "/home")      # bwrap makes
               for x in ("--perms", "0755", "--dir", d)]  # parents 0700
    return (["sudo", "-n", "bwrap"] + parents +
            ["--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
             "--symlink", "usr/lib", "/lib",
             "--symlink", "usr/lib64", "/lib64",
             "--ro-bind", "/etc/ssl", "/etc/ssl",
             "--ro-bind", "/opt/w01", "/opt/w01",
             "--bind", workdir, "/work",
             "--perms", "1777", "--tmpfs", "/tmp"] + home +
            ["--proc", "/proc", "--dev", "/dev",
             "--unshare-pid", "--unshare-ipc", "--unshare-uts",
             "--unshare-cgroup", "--new-session", "--die-with-parent",
             "--clearenv", "--setenv", "HOME", pw.pw_dir,
             "--setenv", "PATH", "/usr/bin", "--chdir", "/work", "--",
             "setpriv", "--reuid", str(pw.pw_uid), "--regid",
             str(pw.pw_gid), "--clear-groups", "--no-new-privs",
             "--inh-caps=-all", "--bounding-set=-all", "--"] + inner)


def loop_cmd(setting, name, extra):
    """(command, output directory) for the loop in one setting."""
    n = ["--experiments", str(args.experiments)]
    if setting == "bare":
        out = f"{RUN}/{name}"
        sh(["rm", "-rf", out])
        os.makedirs(out)
        return [PY, LOOP, "--out", out] + n + extra, out
    out = fresh_dir(name)
    if setting == "user":
        return ["sudo", "-n", "-u", AGENT, PY, LOOP, "--out", out] \
            + n + extra, out
    inner = [PY, LOOP, "--out", "/work"] + n + extra
    if setting == "bwrap":
        return bwrap(out, inner), out
    return bwrap(out, LIMITS + inner), out


def counter():
    t = sh(["sudo", "-n", "nft", "list", "chain", "inet", "w01", "egress"])
    m = re.search(r"counter packets (\d+) bytes (\d+)", t.stdout)
    return int(m.group(1)) if m else 0


# ── 2. The canary: a pretend attacker's server, and the proxy ─────────
received = []


class Canary(BaseHTTPRequestHandler):
    def do_GET(self):
        received.append("GET " + self.path)
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        received.append(self.rfile.read(n).decode())
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def start_services(allow="pypi.org"):
    srv = HTTPServer(("127.0.0.1", CANARY_PORT), Canary)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log = f"{RUN}/proxy.jsonl"
    open(log, "w").close()
    proc = subprocess.Popen(
        [PY, os.path.join(HERE, "egress_proxy.py"), "--allow",
         allow, "--log", log], stdout=subprocess.DEVNULL)
    time.sleep(0.5)
    return srv, proc, log


# ── 3. Part 1: the attack, three ways ─────────────────────────────────
def attack():
    os.makedirs(RUN, exist_ok=True)
    srv, proxy, log = start_services()
    home = os.path.expanduser("~")
    settings = [
        ("1. no protection (my own user)", "bare",
         ["--exfil", "--secret", f"{home}/.w01-secret"]),
        ("2. separate user + firewall + proxy", "user",
         ["--exfil", "--secret", f"/home/{AGENT}/.w01-secret",
          "--proxy", PROXY]),
        ("3. full sandbox", "bwrap",
         ["--exfil", "--secret", f"/home/{AGENT}/.w01-secret",
          "--proxy", PROXY]),
    ]
    for title, setting, extra in settings:
        received.clear()
        before, seen = counter(), len(open(log).readlines())
        cmd, _ = loop_cmd(setting, "attack-" + setting, extra)
        done = sh(cmd, cwd="/", timeout=120)
        assert done.returncode == 0, done.stderr[-400:]
        report = json.loads(done.stdout.strip().splitlines()[-1])
        print(f"\n== {title} ==")
        for a in report["attempts"]:
            print(f"  {a['attempt']:36} {a['outcome']:10} {a['detail']}")
        print(f"  canary received:       {received or 'nothing'}")
        lines = open(log).readlines()[seen:]
        print(f"  proxy decisions:       "
              + (", ".join(f"{json.loads(l)['verdict']} "
                           f"{json.loads(l)['host']}" for l in lines)
                 or "none"))
        print(f"  firewall rejects:      {counter() - before} packets")
        print(f"  loop finished:         {report['experiments']} experiments,"
              f" best val loss {report['best_val_loss']}")
    proxy.terminate()
    srv.shutdown()


# ── 4. Part 2: what each layer costs ──────────────────────────────────
def timing():
    os.makedirs(RUN, exist_ok=True)
    settings = [("bare", "my own user"),
                ("user", "+ separate user (sudo -u)"),
                ("bwrap", "+ bubblewrap namespaces"),
                ("full", "+ rlimits and proxy settings")]
    times = {s: [] for s, _ in settings}
    cpu = {s: [] for s, _ in settings}      # the loop's own CPU seconds
    data = {}
    # Interleave the settings so that drift on a shared machine hits all
    # four equally, instead of favouring whichever ran last.
    for r in range(args.repeats):
        for setting, _ in settings:
            extra = ["--proxy", PROXY] if setting == "full" else []
            cmd, out = loop_cmd(setting, "time-" + setting, extra)
            t0 = time.perf_counter()
            done = sh(cmd, cwd="/", timeout=300)
            times[setting].append(time.perf_counter() - t0)
            assert done.returncode == 0, done.stderr[-300:]
            cpu[setting].append(
                json.loads(done.stdout.strip().splitlines()[-1])["cpu_seconds"])
            data[setting] = sh(["sudo", "-n", "cat",
                                out + "/results.jsonl"]).stdout
    hashes = set(data.values())
    base_cpu = statistics.median(cpu["bare"])
    print(f"load average while timing: {os.getloadavg()[0]:.1f} "
          f"on {os.cpu_count()} vCPUs")
    print(f"{'setting':32}{'wall med':>9}{'wall min':>9}{'cpu med':>9}"
          f"{'cpu vs bare':>12}")
    for s, label in settings:
        m = statistics.median(cpu[s])
        print(f"{label:32}{statistics.median(times[s]):9.3f}"
              f"{min(times[s]):9.3f}{m:9.3f}{(m / base_cpu - 1) * 100:+11.1f}%")
    print(f"identical results.jsonl in all settings: {len(hashes) == 1}")
    # Start-up alone: a program that does nothing.
    def launch(cmd, n=30):
        t0 = time.perf_counter()
        for _ in range(n):
            sh(cmd, cwd="/")
        return (time.perf_counter() - t0) / n * 1000
    wd = fresh_dir("noop")
    plain = launch(["/usr/bin/true"])
    boxed = launch(bwrap(wd, LIMITS + ["/usr/bin/true"]))
    print(f"\nlaunching /usr/bin/true: {plain:.1f} ms bare, "
          f"{boxed:.1f} ms boxed ({boxed - plain:+.1f} ms per launch)")


if __name__ == "__main__":
    if args.only != "timing":
        attack()
    if args.only != "attack":
        print("\n== timing ==" if args.only != "timing" else "")
        timing()
