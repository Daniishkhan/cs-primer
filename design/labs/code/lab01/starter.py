"""Lab 1: Estimation Drills, your starter.

A napkin-maths toolkit. Every function is a few lines of arithmetic; the skill is in
choosing which one to call and in keeping the units straight. Standard library only.

Conventions (the same as chapter 2):
  * sizes use powers of TEN (1 KB = 1,000 B); the 2.4% difference from 1,024 is far
    smaller than the error bars of an estimate;
  * "per day" becomes "per second" by dividing by 86,400;
  * bandwidth is in BITS per second, storage in BYTES.
"""
import math

# ------------------------------------------------------------------------------------
# Milestone 1: units, powers of ten, human()
# ------------------------------------------------------------------------------------
KB, MB, GB, TB, PB = 10 ** 3, 10 ** 6, 10 ** 9, 10 ** 12, 10 ** 15
SECONDS_PER_DAY = 86_400          # roughly 10^5
DAYS_PER_YEAR = 365
SECONDS_PER_YEAR = SECONDS_PER_DAY * DAYS_PER_YEAR


def per_day_to_per_sec(n_per_day):
    """Events per day -> events per second (the average rate)."""
    raise NotImplementedError("TODO milestone 1: per_day_to_per_sec")


def per_sec_to_per_day(n_per_sec):
    """Events per second -> events per day."""
    raise NotImplementedError("TODO milestone 1: per_sec_to_per_day")


def bytes_to_bits(n_bytes):
    """Bytes -> bits (bandwidth is quoted in bits)."""
    raise NotImplementedError("TODO milestone 1: bytes_to_bits")


def order_of_magnitude(x):
    """floor(log10(x)): 999 -> 2, 1000 -> 3, 0.02 -> -2. x must be positive."""
    raise NotImplementedError("TODO milestone 1: order_of_magnitude")


_SUFFIXES = ((1e15, "P"), (1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "k"))


def human(n, unit=""):
    """Format with three significant digits and an SI-style suffix.

    human(54_750_000_000_000, "B") -> '54.8 TB';  human(12) -> '12';  human(0.5) -> '0.5'
    """
    raise NotImplementedError("TODO milestone 1: human")


def within_factor(estimate, truth, factor):
    """True if estimate is within `factor` of truth, in either direction."""
    raise NotImplementedError("TODO milestone 1: within_factor")


# ------------------------------------------------------------------------------------
# Milestone 2: QPS from DAU, actions per user and a peak factor
# ------------------------------------------------------------------------------------
def avg_qps(dau, actions_per_user_per_day):
    """Average requests per second."""
    raise NotImplementedError("TODO milestone 2: avg_qps")


def peak_qps(avg, peak_factor=3.0):
    """Peak requests per second: the average times a stated peak-to-average factor."""
    raise NotImplementedError("TODO milestone 2: peak_qps")


def qps_from_dau(dau, actions_per_user_per_day, peak_factor=3.0):
    """(average QPS, peak QPS) for a user population."""
    raise NotImplementedError("TODO milestone 2: qps_from_dau")


def split_read_write(total_qps, reads_per_write):
    """Split a total into (reads, writes) for a read:write ratio of `reads_per_write` : 1."""
    raise NotImplementedError("TODO milestone 2: split_read_write")


# ------------------------------------------------------------------------------------
# Milestone 3: storage over N years, replication and index overhead
# ------------------------------------------------------------------------------------
def raw_bytes_per_year(writes_per_day, bytes_per_write):
    """Unreplicated bytes written in one year."""
    raise NotImplementedError("TODO milestone 3: raw_bytes_per_year")


def storage_bytes(writes_per_day, bytes_per_write, years, replication=3.0, index_overhead=0.0):
    """Total fleet storage: raw bytes x (1 + index overhead) x replication factor.

    index_overhead is a fraction (0.3 means indexes and metadata add 30%).
    replication may be fractional (erasure coding at 1.5x).
    """
    raise NotImplementedError("TODO milestone 3: storage_bytes")


def nodes_for_storage(total_bytes, bytes_per_node, max_fill=0.7):
    """Machines needed if each may be filled to `max_fill` of its capacity."""
    raise NotImplementedError("TODO milestone 3: nodes_for_storage")


# ------------------------------------------------------------------------------------
# Milestone 4: bandwidth and cache sizing (80/20)
# ------------------------------------------------------------------------------------
def bandwidth_bps(qps, bytes_per_response):
    """Bits per second for a request rate and a response size."""
    raise NotImplementedError("TODO milestone 4: bandwidth_bps")


def origin_qps(qps, hit_ratio):
    """Requests that get past a cache or CDN with the given hit ratio."""
    raise NotImplementedError("TODO milestone 4: origin_qps")


def required_hit_ratio(qps, origin_capacity_qps):
    """The hit ratio the cache must reach so the origin sees at most its capacity (0 if none needed)."""
    raise NotImplementedError("TODO milestone 4: required_hit_ratio")


def cache_bytes(new_bytes_per_day, window_days, hot_fraction=0.2):
    """80/20 cache sizing: hold the hot fraction of what was written in the window that is still read."""
    raise NotImplementedError("TODO milestone 4: cache_bytes")


def nics_needed(bps, nic_bps=10e9, max_utilisation=0.5):
    """Network cards of `nic_bps` needed if each runs at most at `max_utilisation`."""
    raise NotImplementedError("TODO milestone 4: nics_needed")


# ------------------------------------------------------------------------------------
# Milestone 5: machine counts from per-box capacity with headroom
# ------------------------------------------------------------------------------------
def machines(peak, per_box, utilisation=0.6, zones=1, spares=0):
    """Machines for `peak` load when each box may run at `utilisation` of `per_box`.

    zones > 1 means: survive losing one whole zone, so the other (zones - 1) zones
    must carry the peak, which multiplies the count by zones / (zones - 1).
    Spares are added on top.
    """
    raise NotImplementedError("TODO milestone 5: machines")


def in_flight(rate, latency_seconds):
    """Little's law: requests in flight = arrival rate x time in system."""
    raise NotImplementedError("TODO milestone 5: in_flight")


def latency_inflation(utilisation):
    """M/M/1 mean time in system as a multiple of the bare service time: 1 / (1 - rho)."""
    raise NotImplementedError("TODO milestone 5: latency_inflation")


def max_utilisation_for(inflation_budget):
    """The highest utilisation whose M/M/1 latency inflation stays within the budget."""
    raise NotImplementedError("TODO milestone 5: max_utilisation_for")
