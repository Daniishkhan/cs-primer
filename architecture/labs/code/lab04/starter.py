"""Lab 4: A Saga Orchestrator. Your file.

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
        """Handle one delivery of (op, key).

        TODO milestone 3: the network may deliver a request twice (fault "dup"), and the
        orchestrator may re-send after a timeout or a crash. Make a repeat of the same
        (op, key) return the first answer WITHOUT running the effect again:
          * if (op, key) is in self.results, return the stored result;
          * otherwise call self.apply(op, key, data), store its result under (op, key), return it.
        status() below reads self.results, so storing is also what lets the orchestrator ask
        "did my call happen?" in milestone 4.
        """
        return self.apply(op, key, data)        # naive: every delivery does the work again

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

    # ---- milestone 1: the happy path, with state in sqlite ----
    def _create_tables(self):
        """Create (if they do not exist) the tables you need. A suggestion:

            sagas(id TEXT PRIMARY KEY, data TEXT, status TEXT, step INTEGER, cancel_requested INTEGER)
            log(seq INTEGER PRIMARY KEY AUTOINCREMENT, saga_id TEXT, step INTEGER, phase TEXT, state TEXT)
            orders(id TEXT PRIMARY KEY, status TEXT)          # only for milestone 5

        Use `with self.db:` for every write: it commits on success and rolls back on an exception.
        """
        raise NotImplementedError("TODO milestone 1: _create_tables")

    def run_saga(self, saga_id, data):
        """Create the saga (if it does not exist yet), run it to the end, return its status.

        data is a plain dict (json.dumps it into the table). Steps:
          1. INSERT OR IGNORE the saga row: status 'RUNNING', step 0. If the id already exists,
             do not start over: carry on from where it is (milestone 4 relies on that).
          2. Call self._drive(saga_id) and return what it returns.

        Statuses: RUNNING, COMPENSATING, COMPLETED, COMPENSATED.
        """
        raise NotImplementedError("TODO milestone 1: run_saga")

    def status(self, saga_id):
        """The saga's status string, or None if there is no such saga."""
        raise NotImplementedError("TODO milestone 1: status")

    def history(self, saga_id):
        """[(step name, 'action' | 'compensation', 'DONE' | 'FAILED'), ...] in the order it happened.

        Keep a log table with one row per event (an AUTOINCREMENT seq gives you the order).
        Rows for STARTED belong in the log (milestone 4) but not in this list.
        """
        raise NotImplementedError("TODO milestone 1: history")

    def _drive(self, saga_id):
        """The heart of the orchestrator: a loop over the SAVED state.

        Milestone 1 (forward only):
          loop: load the saga row; if step == len(self.steps) mark it COMPLETED and return;
                otherwise call step `step`: service = self.services[s.service];
                service.call(s.action, key, data) with key = f"{saga_id}:{step}"
                and then, in one transaction, log DONE and set step = step + 1.
        Milestone 2: if the call raises ServiceError the step FAILED. In one transaction log FAILED
                and switch the saga to COMPENSATING with step = failed_step - 1. In that state each
                loop turn calls the compensation of `step` (s.compensation), logs it DONE and moves
                step down. When step < 0 the saga is COMPENSATED. The failed step itself is not
                compensated: it never took effect. A compensation that fails must be retried
                (up to MAX_ATTEMPTS), because nobody is going to do it for you.
        Milestone 4: see _attempt's docstring for what must be saved before and after a call.
        Milestone 5: honour the cancel flag at the top of the loop.
        """
        raise NotImplementedError("TODO milestone 1: _drive")

    def _attempt(self, saga_id, i, phase, data):
        """Make one action (phase='action') or compensation (phase='compensation') of step i happen.

        Return True if it worked, False if an ACTION definitely failed.

        Milestone 2/3: key = f"{saga_id}:{i}" for both the action and its compensation.
        Milestone 4:
          * BEFORE the call, log a 'STARTED' row for (saga, step, phase) and commit it.
          * If you find a STARTED row already there, a previous orchestrator died during this call:
            ask service.status(op, key). 'DONE' means it happened, do not call again.
          * On Timeout the outcome is unknown. Ask service.status(op, key) first. If 'DONE', treat the
            call as a success. If not, call again with the same key. After MAX_ATTEMPTS tries,
            an action counts as failed; a compensation raises RuntimeError (a human is needed).
        """
        raise NotImplementedError("TODO milestone 2: _attempt")

    # ---- milestone 4: restart ----
    def resume(self, saga_id):
        """Continue a saga that already exists. Usually just self._drive(saga_id)."""
        raise NotImplementedError("TODO milestone 4: resume")

    def recover(self):
        """Resume every saga whose status is not COMPLETED or COMPENSATED. Return their ids, sorted."""
        raise NotImplementedError("TODO milestone 4: recover")

    # ---- milestone 5 (optional): a semantic lock on the order ----
    def order_status(self, order_id):
        """PENDING while the saga runs (the semantic lock), then CONFIRMED or CANCELLED. None if unknown."""
        raise NotImplementedError("TODO milestone 5: order_status")

    def cancel_order(self, order_id):
        """A user presses Cancel while the saga is running.

        Return 'UNKNOWN_ORDER', 'TOO_LATE' (already CONFIRMED), 'ALREADY_CANCELLED', or
        'CANCEL_REQUESTED' (still PENDING: save a flag in sqlite; _drive acts on it at the
        next step boundary by compensating whatever has been done, then the order is CANCELLED).
        Careful: if a call may be half done (a STARTED row without DONE), finish that step first.
        """
        raise NotImplementedError("TODO milestone 5: cancel_order")
