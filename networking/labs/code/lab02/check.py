"""Self-check for Lab 2.

    python3 check.py              # checks your starter.py
    python3 check.py solution     # checks the reference solution

Each milestone runs real transfers over a LossyChannel (loopback UDP with
seeded loss, duplication and reordering) and prints ✔ / ✘ / … (not started yet).
The whole run takes roughly 15 to 25 seconds.
"""
import importlib
import sys
import time

target = sys.argv[1] if len(sys.argv) > 1 else "starter"
mod = importlib.import_module(target)
results = []


def check(name, fn):
    try:
        note = fn()
        print(f"  ✔ {name}" + (f"  ({note})" if note else ""))
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:  # anything else is a bug worth seeing
        print(f"  ✘ {name}: {type(e).__name__}: {e}")
        results.append(False)


# --- Milestone 1 ----------------------------------------------------------------

def m1():
    hdr = mod.HEADER_LEN
    assert isinstance(hdr, int) and hdr == 9, f"HEADER_LEN should be 9 (1+4+4), got {hdr!r}"
    for ptype, seq, payload in [(mod.DATA, 0, b"hello"), (mod.ACK, 41, b""),
                                (mod.DATA, 2**32 - 1, bytes(range(256)))]:
        raw = mod.make_packet(ptype, seq, payload)
        assert isinstance(raw, bytes), "make_packet must return bytes"
        assert len(raw) == hdr + len(payload), "packet should be header + payload, nothing else"
        got = mod.parse_packet(raw)
        assert got == (ptype, seq, payload), f"round trip failed: {got!r}"
    raw = mod.make_packet(mod.DATA, 7, b"some payload bytes")
    assert raw[0] == mod.DATA, "the first byte should be the packet type"
    assert raw[1:5] == (7).to_bytes(4, "big"), "bytes 1-4 should be the sequence number, big-endian"
    for i in range(len(raw)):                 # damage each byte in turn
        bad = raw[:i] + bytes([raw[i] ^ 0x01]) + raw[i + 1:]
        assert mod.parse_packet(bad) is None, f"flipping a bit in byte {i} was not detected"
    assert mod.parse_packet(raw[:-1]) is None, "a truncated packet should be rejected"
    assert mod.parse_packet(raw + b"x") is None, "a packet with an extra byte should be rejected"
    assert mod.parse_packet(b"") is None and mod.parse_packet(b"\x01\x00") is None, \
        "too-short input should return None, not raise"


# --- Milestone 2 ----------------------------------------------------------------

def m2():
    data = mod.make_test_data(30_000, seed=5)
    # 2a: a clean, fast link: exactly one DATA packet per chunk, plus the end marker.
    got, sent, _ = mod.run_transfer(mod.stop_and_wait_send, mod.receive, data, rtt=0.004)
    assert got == data, f"clean link: received {len(got)} bytes, which differ from the {len(data)} sent"
    assert sent == 31, f"clean link: expected 31 DATA packets (30 chunks + end marker), sent {sent}"
    # 2b: a nasty link.
    got, sent, secs = mod.run_transfer(mod.stop_and_wait_send, mod.receive, data, rtt=0.01,
                                       loss=0.10, dup=0.10, reorder=0.10, corrupt=0.03, seed=11)
    assert got == data, "with loss/duplication/reordering the file did not arrive intact " \
                        f"(got {len(got)} of {len(data)} bytes)"
    assert sent > 31, "with 10% loss some packets must have been retransmitted"
    return f"{secs:.1f} s, {sent} packets for 31 needed"


# --- Milestone 3 ----------------------------------------------------------------

def m3():
    chunk = mod.CHUNK
    r1 = mod.measure_throughput(mod.stop_and_wait_send, rtt=0.02)
    r2 = mod.measure_throughput(mod.stop_and_wait_send, rtt=0.04)
    for rtt, got in ((0.02, r1), (0.04, r2)):
        ceiling = chunk / rtt
        assert 0.5 * ceiling <= got <= 1.05 * ceiling, (
            f"at RTT {rtt * 1000:.0f} ms stop-and-wait should manage about one chunk per RTT "
            f"(about {ceiling / 1000:.0f} KB/s), measured {got / 1000:.0f} KB/s")
    assert 1.5 <= r1 / r2 <= 2.5, f"doubling the RTT should roughly halve throughput, ratio was {r1 / r2:.2f}"
    bdp = mod.bandwidth_delay_product(100e6, 0.05)
    assert abs(bdp - 625_000) < 1, f"100 Mbit/s x 50 ms should be 625,000 bytes, got {bdp!r}"
    w = mod.window_for_full_pipe(10e6, 0.02, 1000)
    assert w == 25, f"10 Mbit/s x 20 ms with 1000-byte packets needs 25 packets in flight, got {w!r}"
    return f"{r1 / 1000:.0f} KB/s at 20 ms, {r2 / 1000:.0f} KB/s at 40 ms"


# --- Milestone 4 ----------------------------------------------------------------

def m4():
    data = mod.make_test_data(200_000, seed=3)             # 200 chunks
    # RTT is 10 ms, so a 30 ms timeout (3 x RTT) for both senders keeps it fair.
    kw = dict(rtt=0.01, loss=0.10, dup=0.05, reorder=0.05, corrupt=0.02, seed=21, timeout=0.03)
    got, gbn_sent, gbn_secs = mod.run_transfer(mod.gbn_send, mod.receive, data, **kw)
    assert got == data, f"Go-Back-N: file did not arrive intact (got {len(got)} of {len(data)} bytes)"
    assert gbn_sent > 201, "with 10% loss some packets must have been resent"
    got, sw_sent, sw_secs = mod.run_transfer(mod.stop_and_wait_send, mod.receive, data, **kw)
    assert got == data, "stop-and-wait: file did not arrive intact"
    assert gbn_secs < sw_secs * 0.62, (
        f"the window should be much faster: Go-Back-N {gbn_secs:.1f} s vs stop-and-wait {sw_secs:.1f} s")
    return (f"200 KB through 10% loss: stop-and-wait {sw_secs:.1f} s ({sw_sent} pkts), "
            f"go-back-n {gbn_secs:.1f} s ({gbn_sent} pkts), {sw_secs / gbn_secs:.1f}x faster")


# --- Milestone 5 (optional) -----------------------------------------------------

def m5():
    est = mod.RttEstimator(initial_rto=0.5, min_rto=0.001, max_rto=10)
    est.update(0.100)
    assert abs(est.srtt - 0.100) < 1e-9 and abs(est.rttvar - 0.050) < 1e-9, \
        f"first sample: SRTT=R, RTTVAR=R/2; got srtt={est.srtt}, rttvar={est.rttvar}"
    assert abs(est.rto - 0.300) < 1e-9, f"RTO = SRTT + 4*RTTVAR = 0.300 after one sample, got {est.rto}"
    est.update(0.140)
    assert abs(est.rttvar - 0.0475) < 1e-9, f"RTTVAR must use the OLD srtt: expected 0.0475, got {est.rttvar}"
    assert abs(est.srtt - 0.105) < 1e-9, f"expected SRTT 0.105, got {est.srtt}"
    assert abs(est.rto - 0.295) < 1e-9, f"expected RTO 0.295, got {est.rto}"
    est.backoff()
    assert abs(est.rto - 0.590) < 1e-9, f"backoff should double the RTO, got {est.rto}"
    clamp = mod.RttEstimator(initial_rto=0.5, min_rto=0.2, max_rto=1.0)
    clamp.update(0.001)
    assert clamp.rto == 0.2, f"RTO must not go below min_rto, got {clamp.rto}"
    clamp.rto = 0.9
    clamp.backoff()
    assert clamp.rto == 1.0, f"RTO must not exceed max_rto, got {clamp.rto}"
    # Now use it in a real transfer on a slow, lossy link. The sender is not told the RTT.
    data = mod.make_test_data(40_000, seed=8)
    est = mod.RttEstimator(initial_rto=0.3, min_rto=0.02)
    got, sent, secs = mod.run_transfer(mod.gbn_send, mod.receive, data, rtt=0.06, loss=0.03,
                                       reorder=0.03, seed=31, window=4, estimator=est)
    assert got == data, "adaptive Go-Back-N did not deliver the file intact"
    assert est.srtt is not None, "gbn_send never fed an RTT sample to the estimator"
    assert 0.04 <= est.srtt <= 0.12, f"the link's RTT is 60 ms, but SRTT ended at {est.srtt * 1000:.0f} ms"
    return f"SRTT {est.srtt * 1000:.0f} ms (true RTT 60 ms), RTO {est.rto * 1000:.0f} ms"


print(f"Lab 2 checks against {target}.py\n")
t0 = time.time()
check("Milestone 1: packet format and checksum", m1)
check("Milestone 2: stop-and-wait over a lossy channel", m2)
check("Milestone 3: throughput vs RTT, bandwidth-delay product", m3)
check("Milestone 4: sliding window (Go-Back-N) beats stop-and-wait", m4)
check("Milestone 5 (optional): adaptive timeout from measured RTT", m5)
passed = sum(results)
print(f"\n{passed}/{len(results)} milestones passing" + ("  🎉 Lab complete!" if passed == len(results) else "")
      + f"   ({time.time() - t0:.0f} s)")
sys.exit(0 if passed == len(results) else 1)
