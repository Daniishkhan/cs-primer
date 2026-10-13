"""Lab 4: A Relationship-Based Authorization Engine.

You build, in five steps, the core of a Zanzibar-style authorization service:

  1. RBAC: roles to permissions, and a test that shows role explosion.
  2. Relation tuples (object#relation@subject) and a direct check.
  3. Userset rewrites: "editor implies viewer" (computed userset) and
     "viewers of the parent folder are viewers" (tuple-to-userset), with a
     bounded-depth recursive check that survives cycles.
  4. explain() and who_can(): the path that granted access, and everyone who
     has access, for audit.
  5. An API with a deliberate IDOR bug (a handler that fetches by id and never
     asks "may this caller?"). You fix it by routing every access through check.

Pure Python standard library. Everything runs in one process: no network, no
database server. Fill in each region that raises NotImplementedError, then run

    python3 check.py            # checks this file (the starter)
    python3 check.py solution   # checks the reference answer
"""
import re
from dataclasses import dataclass


# =========================================================================
# Milestone 1: RBAC, and why it explodes
# =========================================================================
class RBAC:
    """Users have roles; roles carry permissions (plain strings such as "read:d7").

    State (keep these names; the checks read them):
        role_perms: dict  role -> set of permissions
        user_roles: dict  user -> set of roles
    """

    def __init__(self):
        self.role_perms = {}
        self.user_roles = {}

    def grant(self, role, perm):
        """Give `role` the permission `perm` (creating the role if needed)."""
        self.role_perms.setdefault(role, set()).add(perm)

    def assign(self, user, role):
        """Give `user` the role `role`."""
        self.user_roles.setdefault(user, set()).add(role)

    def allowed(self, user, perm):
        """True if any of the user's roles carries `perm`. Unknown users and
        unknown permissions are simply denied (fail-safe default)."""
        return any(perm in self.role_perms.get(r, ()) for r in self.user_roles.get(user, ()))


def rbac_for_sharing(shares):
    """Express per-document sharing with roles only.

    `shares` is a list of (user, doc, level), level "viewer" or "editor".
    RBAC cannot say "editor of THIS document" with a global role, so make one
    role per (level, doc), named f"{level}:{doc}":
        viewer:d7 carries {"read:d7"}
        editor:d7 carries {"read:d7", "write:d7"}
    and assign each user the roles that match their shares.
    """
    rbac = RBAC()
    for user, doc, level in shares:
        role = f"{level}:{doc}"
        rbac.grant(role, f"read:{doc}")
        if level == "editor":
            rbac.grant(role, f"write:{doc}")
        rbac.assign(user, role)
    return rbac


def policy_size(rbac):
    """How much policy a reviewer must read: (roles, role-permission pairs)."""
    return len(rbac.role_perms), sum(len(p) for p in rbac.role_perms.values())


# =========================================================================
# Milestone 2: relation tuples and a direct check
# =========================================================================
# A tuple reads  object#relation@subject.  The subject is either a user
# ("user:alice") or a userset: "everyone who has relation R on object O",
# written "group:eng#member".   Examples:
#     doc:plan#editor@user:alice
#     folder:q3#viewer@group:eng#member
#     doc:plan#parent@folder:q3
TUPLE_PATTERN = r"([a-z]+:[^#@\s]+)#([a-z_]+)@([a-z]+:[^#@\s]+(?:#[a-z_]+)?)"


@dataclass(frozen=True)
class Tup:
    obj: str
    rel: str
    subject: str

    def __str__(self):
        return f"{self.obj}#{self.rel}@{self.subject}"


def parse_tuple(text):
    """Parse "obj#rel@subject" into a Tup, or raise ValueError.

    Use TUPLE_PATTERN with re.fullmatch (not match, and not $: Python's $ also
    matches just before a trailing newline).
    """
    m = re.fullmatch(TUPLE_PATTERN, text)
    if m is None:
        raise ValueError(f"not a relation tuple: {text!r}")
    return Tup(*m.groups())


class TupleStore:
    """A set of tuples, indexed by (object, relation)."""

    def __init__(self):
        self._by_key = {}          # (obj, rel) -> set of subject strings

    @staticmethod
    def _coerce(t):
        return parse_tuple(t) if isinstance(t, str) else t

    def add(self, t):
        """Add a Tup (or a string, which you parse). Adding twice changes nothing."""
        t = self._coerce(t)
        self._by_key.setdefault((t.obj, t.rel), set()).add(t.subject)

    def remove(self, t):
        """Remove a tuple if present; removing a missing tuple is not an error."""
        t = self._coerce(t)
        subjects = self._by_key.get((t.obj, t.rel))
        if subjects:
            subjects.discard(t.subject)
            if not subjects:
                del self._by_key[(t.obj, t.rel)]

    def subjects(self, obj, rel):
        """The subjects stored for obj#rel, as a SORTED list (so every run is the same)."""
        return sorted(self._by_key.get((obj, rel), ()))

    def __len__(self):
        return sum(len(s) for s in self._by_key.values())


def check_direct(store, obj, rel, user):
    """True only if the exact tuple obj#rel@user is stored. No usersets, no rewrites."""
    return user in store.subjects(obj, rel)


# =========================================================================
# Milestone 3: userset rewrites and a bounded, cycle-safe check
# =========================================================================
class DepthExceeded(Exception):
    """The check needed more than max_depth steps. Treat as DENY."""


# The schema says, per (type, relation), which rules produce that relation:
#   ("this",)                   tuples stored directly on obj#rel (a subject may be a userset)
#   ("computed", rel2)          anyone with obj#rel2 also has obj#rel      (editor implies viewer)
#   ("ttu", via, rel2)          follow the tuples obj#via@P to each parent object P,
#                               then ask for P#rel2                        (inherit from the folder)
DEFAULT_SCHEMA = {
    ("group", "member"): [("this",)],
    ("folder", "owner"): [("this",)],
    ("folder", "parent"): [("this",)],
    ("folder", "editor"): [("this",), ("computed", "owner")],
    ("folder", "viewer"): [("this",), ("computed", "editor"), ("ttu", "parent", "viewer")],
    ("doc", "owner"): [("this",)],
    ("doc", "parent"): [("this",)],
    ("doc", "editor"): [("this",), ("computed", "owner")],
    ("doc", "viewer"): [("this",), ("computed", "editor"), ("ttu", "parent", "viewer")],
}


class Engine:
    """Answers: does `user` ("user:alice") have relation `rel` on object `obj`?

    The recursion must (a) never revisit the same (object, relation) within one
    query, which makes cycles harmless and keeps diamonds linear, and (b) stop
    with DepthExceeded when a call is deeper than max_depth. The top-level call
    has depth 0; every recursive call is one deeper.
    """

    def __init__(self, store, schema=None, max_depth=16):
        self.store = store
        self.schema = DEFAULT_SCHEMA if schema is None else schema
        self.max_depth = max_depth

    def rules(self, obj, rel):
        """The rewrite rules for obj#rel; none for unknown types or relations (deny)."""
        return self.schema.get((obj.split(":", 1)[0], rel), [])

    def check(self, obj, rel, user):
        """True if user has obj#rel through any rule. Raises DepthExceeded when too deep."""
        return self._check(obj, rel, user, 0, set())

    def _check(self, obj, rel, user, depth, seen):
        if depth > self.max_depth:
            raise DepthExceeded(f"{obj}#{rel} is {depth} levels deep (max {self.max_depth})")
        if (obj, rel) in seen:               # cycle, or already explored in this query
            return False
        seen.add((obj, rel))
        for rule in self.rules(obj, rel):
            if rule[0] == "this":
                for s in self.store.subjects(obj, rel):
                    if s == user:
                        return True
                    if "#" in s:             # a userset: recurse into "everyone with R on O"
                        so, sr = s.split("#", 1)
                        if self._check(so, sr, user, depth + 1, seen):
                            return True
            elif rule[0] == "computed":
                if self._check(obj, rule[1], user, depth + 1, seen):
                    return True
            elif rule[0] == "ttu":
                for parent in self.store.subjects(obj, rule[1]):
                    if "#" not in parent and self._check(parent, rule[2], user, depth + 1, seen):
                        return True
        return False

    # ---------------------------------------------------------------------
    # Milestone 4: explain and expand
    # ---------------------------------------------------------------------
    def explain(self, obj, rel, user):
        """The path that grants access, or None. A path is a list of step strings:

            computed A#r => A#r2                 (rule: r2 implies r on the same object)
            ttu A#r => P#r2 via A#via@P          (inherit from parent P through tuple A#via@P)
            userset A#r => B#r2 via A#r@B#r2     (tuple A#r@B#r2 hands the question to B#r2)
            tuple A#r@user:x                     (the stored tuple that finally names the user)

        Step N's target is step N+1's source, the first source is obj#rel, and
        the last step is always a "tuple" step naming `user`.
        """
        return self._explain(obj, rel, user, 0, set())

    def _explain(self, obj, rel, user, depth, seen):
        if depth > self.max_depth:
            raise DepthExceeded(f"{obj}#{rel} is {depth} levels deep (max {self.max_depth})")
        if (obj, rel) in seen:
            return None
        seen.add((obj, rel))
        for rule in self.rules(obj, rel):
            if rule[0] == "this":
                for s in self.store.subjects(obj, rel):
                    if s == user:
                        return [f"tuple {obj}#{rel}@{s}"]
                    if "#" in s:
                        so, sr = s.split("#", 1)
                        sub = self._explain(so, sr, user, depth + 1, seen)
                        if sub is not None:
                            return [f"userset {obj}#{rel} => {so}#{sr} via {obj}#{rel}@{s}"] + sub
            elif rule[0] == "computed":
                sub = self._explain(obj, rule[1], user, depth + 1, seen)
                if sub is not None:
                    return [f"computed {obj}#{rel} => {obj}#{rule[1]}"] + sub
            elif rule[0] == "ttu":
                for parent in self.store.subjects(obj, rule[1]):
                    if "#" in parent:
                        continue
                    sub = self._explain(parent, rule[2], user, depth + 1, seen)
                    if sub is not None:
                        return [f"ttu {obj}#{rel} => {parent}#{rule[2]} via {obj}#{rule[1]}@{parent}"] + sub
        return None

    def who_can(self, obj, rel):
        """Expand: every user ("user:...") who has obj#rel, sorted. Same rules, same
        cycle guard and depth bound as check, but collecting instead of searching."""
        return sorted(self._who(obj, rel, 0, set()))

    def _who(self, obj, rel, depth, seen):
        if depth > self.max_depth:
            raise DepthExceeded(f"{obj}#{rel} is {depth} levels deep (max {self.max_depth})")
        if (obj, rel) in seen:
            return set()
        seen.add((obj, rel))
        out = set()
        for rule in self.rules(obj, rel):
            if rule[0] == "this":
                for s in self.store.subjects(obj, rel):
                    if "#" in s:
                        so, sr = s.split("#", 1)
                        out |= self._who(so, sr, depth + 1, seen)
                    elif s.startswith("user:"):
                        out.add(s)
            elif rule[0] == "computed":
                out |= self._who(obj, rule[1], depth + 1, seen)
            elif rule[0] == "ttu":
                for parent in self.store.subjects(obj, rule[1]):
                    if "#" not in parent:
                        out |= self._who(parent, rule[2], depth + 1, seen)
        return out


# =========================================================================
# Milestone 5: an API with a deliberate IDOR bug
# =========================================================================
class AccessError(Exception):
    pass


class NotFound(AccessError):
    """No such document, OR you may not even see it (the two look identical)."""


class Forbidden(AccessError):
    """You can see the document but may not do this to it."""


@dataclass(frozen=True)
class Principal:
    """Who is calling. Built from the authenticated session, never from the request."""
    user: str          # "alice"
    tenant: str        # "acme"


# Which relation each API action needs on the document.
ACTION_REL = {"read": "viewer", "update": "editor", "delete": "owner", "share": "owner"}


class App:
    """A tiny document API. THE HANDLERS BELOW HAVE A BUG: read_doc, update_doc,
    delete_doc, share and list_docs fetch by id and never ask whether the caller
    may. That is an insecure direct object reference (IDOR, OWASP's "broken
    object-level authorization"). Fix all five by routing every access through
    require() / can(), and implement those two on top of Engine.explain.
    """

    def __init__(self, engine=None):
        self.engine = engine if engine is not None else Engine(TupleStore())
        self.store = self.engine.store
        self.docs = {}             # doc id -> {"id","tenant","title","body"}
        self.folders = {}          # folder id -> {"id","tenant","name"}
        self.user_tenant = {}      # user name -> tenant (the directory of accounts)
        self.audit = []            # one dict per require() decision
        self._n = 0

    # ---- given: account directory and creation (these are written correctly) ----
    def register(self, user, tenant):
        self.user_tenant[user] = tenant

    def _next(self, prefix):
        self._n += 1
        return f"{prefix}{self._n}"

    def create_folder(self, p, name, parent=None):
        fid = self._next("f")
        if parent is not None:
            pf = self.folders.get(parent)
            if pf is None or pf["tenant"] != p.tenant or not self.engine.check(f"folder:{parent}", "editor", f"user:{p.user}"):
                raise NotFound(parent)
            self.store.add(f"folder:{fid}#parent@folder:{parent}")
        self.folders[fid] = {"id": fid, "tenant": p.tenant, "name": name}
        self.store.add(f"folder:{fid}#owner@user:{p.user}")
        return fid

    def create_doc(self, p, title, body, folder=None):
        did = self._next("d")
        if folder is not None:
            f = self.folders.get(folder)
            if f is None or f["tenant"] != p.tenant or not self.engine.check(f"folder:{folder}", "editor", f"user:{p.user}"):
                raise NotFound(folder)
            self.store.add(f"doc:{did}#parent@folder:{folder}")
        self.docs[did] = {"id": did, "tenant": p.tenant, "title": title, "body": body}
        self.store.add(f"doc:{did}#owner@user:{p.user}")
        return did

    def _load(self, doc_id):
        doc = self.docs.get(doc_id)
        if doc is None:
            raise NotFound(f"no such document: {doc_id}")
        return doc

    # ---- milestone 5: the choke point ----
    def _decide(self, p, doc_id, rel):
        """The path (list of steps) that lets `p` hold `rel` on the document, or None.

        Rules: the document must exist; its tenant must equal the PRINCIPAL's
        tenant (checked first, whatever tuples exist: tenant isolation is a hard
        wall, not a relationship); then ask the engine, as f"user:{p.user}".
        Too deep is a denial: catch DepthExceeded and return None.
        """
        doc = self.docs.get(doc_id)
        if doc is None or doc["tenant"] != p.tenant:
            return None
        try:
            return self.engine.explain(f"doc:{doc_id}", rel, f"user:{p.user}")
        except DepthExceeded:
            return None

    def can(self, p, doc_id, action):
        """Boolean, quiet (no audit entry, never raises AccessError); for filtering lists."""
        return self._decide(p, doc_id, ACTION_REL[action]) is not None

    def require(self, p, doc_id, action, target=None):
        """Raise unless `p` may `action` the document; otherwise return the path.

        * Cannot read it (or it does not exist, or it is another tenant's):
          raise NotFound(f"no such document: {doc_id}"), exactly as for a missing id,
          so the response does not reveal whether an id exists.
        * Can read it but lacks the needed relation: raise Forbidden.
        * action == "share": `target` (a user name) must be registered in the
          SAME tenant as the principal, else Forbidden. Sharing across tenants
          is a different feature that needs its own design.
        Append one dict to self.audit for every decision:
            {"user","tenant","action","doc","allowed","via"}   (via = the path, or None)
        """
        if action not in ACTION_REL:
            raise ValueError(f"unknown action {action!r}")
        path = None
        seen = self._decide(p, doc_id, "viewer")
        if seen is not None:
            path = seen if action == "read" else self._decide(p, doc_id, ACTION_REL[action])
        denial = None
        if seen is None:
            denial = NotFound(f"no such document: {doc_id}")
        elif path is None:
            denial = Forbidden(f"{p.user} may not {action} {doc_id}")
        elif action == "share" and self.user_tenant.get(target) != p.tenant:
            denial = Forbidden(f"cannot share with {target!r}: not a member of tenant {p.tenant}")
        self.audit.append({"user": p.user, "tenant": p.tenant, "action": action, "doc": doc_id,
                           "allowed": denial is None, "via": None if denial else path})
        if denial is not None:
            raise denial
        return path

    # ---- the handlers: fix each one ----
    def read_doc(self, p, doc_id):
        self.require(p, doc_id, "read")
        return dict(self._load(doc_id))

    def update_doc(self, p, doc_id, body):
        self.require(p, doc_id, "update")
        self._load(doc_id)["body"] = body

    def delete_doc(self, p, doc_id):
        self.require(p, doc_id, "delete")
        del self.docs[doc_id]

    def share(self, p, doc_id, target_user, level):
        """Give `target_user` the relation `level` ("viewer" or "editor") on a document."""
        if level not in ("viewer", "editor"):
            raise ValueError("level must be viewer or editor")
        self.require(p, doc_id, "share", target=target_user)
        self.store.add(f"doc:{doc_id}#{level}@user:{target_user}")

    def list_docs(self, p):
        """Ids of the documents p can read, in creation order."""
        ids = sorted(self.docs, key=lambda d: int(d[1:]))
        return [d for d in ids if self.can(p, d, "read")]
