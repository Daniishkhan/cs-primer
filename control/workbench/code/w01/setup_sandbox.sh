#!/usr/bin/env bash
# One-time setup of the locked-down sandbox, on the lab VM (Ubuntu 24.04).
# Needs passwordless sudo. Safe to run twice.
#   1. a separate Unix user that owns nothing and runs the loop
#   2. bubblewrap, plus the AppArmor permission Ubuntu 24.04 requires
#      before an unprivileged program may create a user namespace
#   3. a kernel firewall rule: that user may reach only the egress proxy
#   4. the loop's files, read-only, and a decoy secret to try to steal
set -euo pipefail

AGENT=labagent
PROXY_PORT=3128

# ── 1. A separate Unix user ───────────────────────────────────────────
id "$AGENT" >/dev/null 2>&1 || sudo useradd --create-home --user-group \
    --shell /usr/sbin/nologin "$AGENT"
sudo usermod --shell /usr/sbin/nologin "$AGENT"
AGENT_UID=$(id -u "$AGENT")
echo "user $AGENT has uid $AGENT_UID"

# ── 2. bubblewrap and the AppArmor profile ────────────────────────────
command -v bwrap >/dev/null || sudo apt-get install -y bubblewrap
sudo tee /etc/apparmor.d/bwrap-w01 >/dev/null <<PROFILE
abi <abi/4.0>,
include <tunables/global>
profile bwrap-w01 /usr/bin/bwrap flags=(unconfined) {
  userns,
}
PROFILE
sudo apparmor_parser -r /etc/apparmor.d/bwrap-w01

# ── 3. Deny-by-default egress for that user ───────────────────────────
sudo nft delete table inet w01 2>/dev/null || true
sudo nft -f - <<RULES
table inet w01 {
  chain egress {
    type filter hook output priority 0; policy accept;
    meta skuid $AGENT_UID oifname "lo" tcp dport $PROXY_PORT accept
    meta skuid $AGENT_UID counter reject with icmpx type admin-prohibited
  }
}
RULES

# ── 4. The loop (read-only for the agent) and a decoy secret ──────────
sudo install -d -m 755 /opt/w01
sudo install -m 644 research_loop.py /opt/w01/research_loop.py
echo "DECOY-$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')" \
    | sudo -u "$AGENT" tee "/home/$AGENT/.w01-secret" >/dev/null
echo "DECOY-$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')" \
    > "$HOME/.w01-secret"
echo "setup done"
