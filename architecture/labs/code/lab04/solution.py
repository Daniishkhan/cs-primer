"""Lab 4: A Saga Orchestrator. Reference solution.

Three in-process fake services (inventory, payments, courier) that can be told to fail, to
time out in two different ways, to deliver a request twice, and even to kill the
orchestrator. The orchestrator runs a saga: forward steps, then compensations in reverse
if a step fails, with its progress saved in sqlite so a restart can pick up where it left off.

Sections:   GIVEN (fake services and fault injection)  |  YOUR WORK (Service.handle, Orchestrator)
"""
import json
import sqlite3
from collections import namedtuple

# =====================================================================================
# GIVEN: failures, fault injection and the fake services. Read it, do not edit it
# (except Service.handle, which is milestone 3).
# =====================================================================================


class ServiceError(Exception):
    """The call definitely did NOT take effect (out of stock, card declined, ...)."""


class Timeout(Exception):
    """No answer. The call MAY or MAY NOT have taken effect: the 'unknown outcome'."""


class Crash(BaseException):
    """The orchestrator process dies here. BaseException, so `except Exception` cannot hide it."""


class Faults:
    """A script of misbehaviour, consumed one entry per call of an operation.

        faults.add("payments.charge", "timeout_after", None, "fail")
            1st call of payments.charge: effect happens, reply is lost
            2nd call: behaves normally (None)
            3rd call: fails, no effect

    Kinds:  "fail"            definite failure, no effect
            "timeout_before"  request lost: no effect, no reply
            "timeout_after"   effect happens, reply lost
            "dup"             the network delivers the request twice
            "crash_before"    the orchestrator dies before the service sees the request
            "crash_after"     the orchestrator dies after the effect, before it can write it down
            a function        called just before the request is delivered (milestone 5 uses it to
                              press "Cancel" mid-saga); if it returns "crash_after" or another
                              kind from this list, that fault is applied too
    """

    def __init__(self):
        self.script = {}

    def add(self, op_name, *kinds):
        self.script.setdefault(op_name, []).extend(kinds)

    def next(self, op_name):
        queue = self.script.get(op_name)
        return queue.pop(0) if queue else None


class Service:
    """Base class of the fake services."""
    name = "service"

    def __init__(self, faults):
        self.faults = faults
        self.results = {}        # (op, key) -> result: what this service remembers about requests
        self.deliveries = []     # every (op, key) that reached the service, duplicates included
        self.applied = []        # every (op, key) whose effect actually ran
        self.status_calls = 0

    def call(self, op, key, data):
        """What the orchestrator calls. Raises ServiceError, Timeout or Crash on trouble."""
        fault = self.faults.next(f"{self.name}.{op}")
        if callable(fault):
            fault = fault()
        if fault == "crash_before":
            raise Crash(f"orchestrator died before {self.name}.{op} {key}")
        if fault == "fail":
            raise ServiceError(f"{self.name}.{op} failed")
        if fault == "timeout_before":
            raise Timeout(f"{self.name}.{op}: request lost")
        self.deliveries.append((op, key))
        result = self.handle(op, key, data)
        if fault == "dup":
            self.deliveries.append((op, key))
            self.handle(op, key, data)
        if fault == "timeout_after":
            raise Timeout(f"{self.name}.{op}: reply lost")
        if fault == "crash_after":
            raise Crash(f"orchestrator died after {self.name}.{op} {key}")
        return result

    def apply(self, op, key, data):
        """Run the effect of an operation. NOT idempotent: calling it twice does it twice."""
        self.applied.append((op, key))
        return getattr(self, "do_" + op)(key, data)

    # ---- milestone 3: make requests idempotent ----
    def handle(self, op, key, data):
        """Handle one delivery of (op, key): apply it once, answer repeats from memory."""
        if (op, key) in self.results:                 # a repeat: same answer, no second effect
            return self.results[(op, key)]
        result = self.apply(op, key, data)
        self.results[(op, key)] = result
        return result

    def status(self, op, key):
        """'DONE' if this service has handled (op, key), else 'NOT_DONE'. Never fails."""
        self.status_calls += 1
        return "DONE" if (op, key) in self.results else "NOT_DONE"


class Inventory(Service):
    name = "inventory"

    def __init__(self, faults, stock=10):
        super().__init__(faults)
        self.available, self.held, self.reservations = stock, 0, {}

    def do_reserve(self, key, data):
        if self.available < data["qty"]:
            raise ServiceError("out of stock")
        self.available -= data["qty"]
        self.held += data["qty"]
        self.reservations[key] = data["qty"]
        return "reserved"

    def do_release(self, key, data):
        qty = self.reservations.get(key)
        if qty:                                   # nothing reserved under this key: nothing to release
            self.available += qty
            self.held -= qty
        return "released"


class Payments(Service):
    name = "payments"

    def __init__(self, faults, balances=None):
        super().__init__(faults)
        self.balance = dict(balances or {"ana": 20000})
        self.charges = {}

    def do_charge(self, key, data):
        if self.balance[data["account"]] < data["amount"]:
            raise ServiceError("card declined")
        self.balance[data["account"]] -= data["amount"]
        self.charges[key] = (data["account"], data["amount"])
        return "charged"

    def do_refund(self, key, data):
        charge = self.charges.get(key)            # refund the charge made under this key, if any
        if charge:
            self.balance[charge[0]] += charge[1]
        return "refunded"


class Courier(Service):
    name = "courier"

    def __init__(self, faults):
        super().__init__(faults)
        self.bookings = {}

    def do_book(self, key, data):
        self.bookings[key] = "BOOKED"
        return "booked"

    def do_cancel(self, key, data):
        if key in self.bookings:
            self.bookings[key] = "CANCELLED"
        return "cancelled"

    def active(self):
        return sum(1 for s in self.bookings.values() if s == "BOOKED")


Step = namedtuple("Step", "name service action compensation")


def default_steps():
    """The checkout saga. compensation=None would mean 'cannot be undone'."""
    return [
        Step("reserve stock", "inventory", "reserve", "release"),
        Step("charge payment", "payments", "charge", "refund"),
        Step("book courier", "courier", "book", "cancel"),
    ]


MAX_ATTEMPTS = 5                      # tries per call before the orchestrator gives up on it
TERMINAL = ("COMPLETED", "COMPENSATED")


# =====================================================================================
# YOUR WORK: the orchestrator
# =====================================================================================


class Orchestrator:
    """Runs sagas and keeps their state in sqlite, so a new Orchestrator on the same file
    can finish what a dead one started.

    services: {"inventory": Inventory, "payments": Payments, "courier": Courier}
    steps:    a list of Step
    """

    def __init__(self, db_path, services, steps):
        self.db = sqlite3.connect(db_path)
        self.services = services
        self.steps = steps
        self._create_tables()

    # ---- milestone 1: state in sqlite ----
    def _create_tables(self):
        with self.db:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS sagas (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL, status TEXT NOT NULL,
                    step INTEGER NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS log (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, saga_id TEXT NOT NULL,
                    step INTEGER NOT NULL, phase TEXT NOT NULL, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, status TEXT NOT NULL);
            """)

    def run_saga(self, saga_id, data):
        """Create the saga (if it does not exist yet), run it to the end, return its status."""
        with self.db:                       # one transaction: the saga and its order exist together
            self.db.execute("INSERT OR IGNORE INTO sagas(id, data, status, step) VALUES (?, ?, 'RUNNING', 0)",
                            (saga_id, json.dumps(data)))
            self.db.execute("INSERT OR IGNORE INTO orders(id, status) VALUES (?, 'PENDING')", (saga_id,))
        return self._drive(saga_id)

    def status(self, saga_id):
        """RUNNING, COMPENSATING, COMPLETED or COMPENSATED (None for an unknown saga)."""
        row = self.db.execute("SELECT status FROM sagas WHERE id = ?", (saga_id,)).fetchone()
        return row[0] if row else None

    def history(self, saga_id):
        """[(step name, 'action' | 'compensation', 'DONE' | 'FAILED'), ...] in the order it happened."""
        rows = self.db.execute("SELECT step, phase, state FROM log WHERE saga_id = ? AND state != 'STARTED' "
                               "ORDER BY seq", (saga_id,)).fetchall()
        return [(self.steps[step].name, phase, state) for step, phase, state in rows]

    def _load(self, saga_id):
        return self.db.execute("SELECT data, status, step, cancel_requested FROM sagas WHERE id = ?",
                               (saga_id,)).fetchone()

    def _drive(self, saga_id):
        """Loop: look at the saved state, do the next thing, save the new state. Repeat."""
        while True:
            data_json, status, step, cancel = self._load(saga_id)
            data = json.loads(data_json)
            if status in TERMINAL:
                return status
            if status == "RUNNING":
                if cancel and self._last_state(saga_id, step, "action") != "STARTED":
                    # milestone 5: the user changed their mind. (Not while a call may be half done:
                    # finish that step first, so its compensation is not forgotten.)
                    self._set(saga_id, "COMPENSATING", step - 1)
                elif step == len(self.steps):
                    self._finish(saga_id, "COMPLETED", "CONFIRMED")
                elif self._attempt(saga_id, step, "action", data):
                    self._set(saga_id, "RUNNING", step + 1, DONE=(step, "action"))
                else:                                       # milestone 2: step failed, undo the ones before it
                    self._set(saga_id, "COMPENSATING", step - 1, FAILED=(step, "action"))
            else:                                           # COMPENSATING: `step` is the next one to undo
                if step < 0:
                    self._finish(saga_id, "COMPENSATED", "CANCELLED")
                else:
                    self._attempt(saga_id, step, "compensation", data)
                    self._set(saga_id, "COMPENSATING", step - 1, DONE=(step, "compensation"))

    def _last_state(self, saga_id, i, phase):
        row = self.db.execute("SELECT state FROM log WHERE saga_id = ? AND step = ? AND phase = ? "
                              "ORDER BY seq DESC LIMIT 1", (saga_id, i, phase)).fetchone()
        return row[0] if row else None

    def _set(self, saga_id, status, step, **outcome):
        """Save the new position and the outcome of the step just finished, in ONE transaction."""
        with self.db:
            for state, (finished_step, phase) in outcome.items():
                self.db.execute("INSERT INTO log(saga_id, step, phase, state) VALUES (?, ?, ?, ?)",
                                (saga_id, finished_step, phase, state))
            self.db.execute("UPDATE sagas SET status = ?, step = ? WHERE id = ?", (status, step, saga_id))

    def _finish(self, saga_id, status, order_status):
        with self.db:
            self.db.execute("UPDATE sagas SET status = ? WHERE id = ?", (status, saga_id))
            self.db.execute("UPDATE orders SET status = ? WHERE id = ?", (order_status, saga_id))

    # ---- the call itself: milestones 2 to 4 ----
    def _attempt(self, saga_id, i, phase, data):
        """Make one action or compensation happen. True on success, False if an ACTION failed.

        A compensation is retried until it works, because giving up would leave the
        customer's money or the shop's stock stuck. It raises after MAX_ATTEMPTS.
        """
        step = self.steps[i]
        op = step.action if phase == "action" else step.compensation
        service = self.services[step.service]
        key = f"{saga_id}:{i}"                              # milestone 3: idempotency key = saga + step
        last = self._last_state(saga_id, i, phase)
        if last is None:                                    # milestone 4: write it down BEFORE the call
            with self.db:
                self.db.execute("INSERT INTO log(saga_id, step, phase, state) VALUES (?, ?, ?, 'STARTED')",
                                (saga_id, i, phase))
        elif service.status(op, key) == "DONE":             # we died during this call: did it happen?
            return True
        for _ in range(MAX_ATTEMPTS):
            try:
                service.call(op, key, data)
                return True
            except ServiceError:
                if phase == "action":
                    return False                            # a definite "no": the saga must back out
            except Timeout:
                if service.status(op, key) == "DONE":       # milestone 4: ask before you retry
                    return True
        if phase == "action":
            return False
        raise RuntimeError(f"compensation {op} for {saga_id} still failing after {MAX_ATTEMPTS} attempts: needs a human")

    # ---- milestone 4: restart ----
    def resume(self, saga_id):
        """Continue a saga that already exists (for example after a restart)."""
        return self._drive(saga_id)

    def recover(self):
        """Resume every saga that is not finished. Return their ids."""
        rows = self.db.execute("SELECT id FROM sagas WHERE status NOT IN ('COMPLETED', 'COMPENSATED') "
                               "ORDER BY id").fetchall()
        for (saga_id,) in rows:
            self.resume(saga_id)
        return [saga_id for (saga_id,) in rows]

    # ---- milestone 5 (optional): a semantic lock on the order ----
    def order_status(self, order_id):
        """PENDING while the saga runs (the semantic lock), then CONFIRMED or CANCELLED."""
        row = self.db.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        return row[0] if row else None

    def cancel_order(self, order_id):
        """A user presses Cancel. Return 'CANCEL_REQUESTED', 'TOO_LATE', 'ALREADY_CANCELLED' or 'UNKNOWN_ORDER'."""
        status = self.order_status(order_id)
        if status is None:
            return "UNKNOWN_ORDER"
        if status == "CONFIRMED":
            return "TOO_LATE"
        if status == "CANCELLED":
            return "ALREADY_CANCELLED"
        with self.db:                                       # PENDING: record the wish; the saga acts on it
            self.db.execute("UPDATE sagas SET cancel_requested = 1 WHERE id = ?", (order_id,))
        return "CANCEL_REQUESTED"
