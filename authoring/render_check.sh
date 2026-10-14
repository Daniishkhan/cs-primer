#!/bin/sh
# Load each page in headless Chrome and report uncaught JavaScript errors.
# Usage: sh authoring/render_check.sh page.html [...]   (needs to run outside the sandbox)
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for p in "$@"; do
  abs="$(cd "$(dirname "$p")" && pwd)/$(basename "$p")"
  out=$("$CH" --headless=new --disable-gpu --enable-logging=stderr --v=0 --virtual-time-budget=4000 --dump-dom "file://$abs" 2>&1 >/dev/null | grep -E "Uncaught|SyntaxError|TypeError|ReferenceError" | grep -v updater | head -3)
  if [ -n "$out" ]; then echo "JSERR $p"; echo "$out" | sed 's/^/    /'; else echo "ok    $p"; fi
done
