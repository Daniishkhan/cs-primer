"""The architecture rules for the shop. Given: your checker reads this file.

Three rules, written down once so a tool can enforce them:

1. A module may depend only on the modules listed for it in ALLOWED.
2. Other modules may import only  shop.<module>.api  (PUBLIC_API), never its internals.
3. Anything that is not a declared module (for example shop.db) is shared state, and
   nobody may import it.

"app" is the entry point (the composition root): it may use every module, but through
their public api like everyone else.
"""

MODULES = ["catalog", "cart", "ordering", "payments", "shipping"]

ALLOWED = {
    "catalog":  [],
    "cart":     ["catalog"],
    "ordering": ["catalog", "cart", "payments", "shipping"],
    "payments": [],
    "shipping": [],
    "app":      ["catalog", "cart", "ordering", "payments", "shipping"],
}

PUBLIC_API = "api"
