"""
Produces one "flow" dict per call -- the thing the scorer consumes.

Today this is a synthetic generator so the replay loop is demoable with
zero dependency on the dataset being wired up yet. Swap `next_flow()`'s
body for a CSV row-reader over the ML teammate's held-out CICIDS split
and nothing downstream (scorer, DB write, WebSocket push) changes.
"""
from __future__ import annotations

import random

PROTOCOLS = ["TCP", "UDP", "ICMP"]


def _rand_ip() -> str:
    return f"{random.randint(10,203)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def next_flow() -> dict:
    """
    Returns a dict with both the raw fields an Incident row needs (src_ip,
    dst_ip, protocol, packet_count) and the feature fields the scorer reads
    (syn_flag_count, flow_duration_ms, packets_per_second).
    """
    is_attack_like = random.random() < 0.35
    if is_attack_like:
        syn = random.randint(150, 900)
        duration = random.randint(1, 40)
        pps = random.randint(3000, 20000)
    else:
        syn = random.randint(0, 50)
        duration = random.randint(200, 5000)
        pps = random.randint(1, 500)

    return {
        "src_ip": _rand_ip(),
        "dst_ip": _rand_ip(),
        "protocol": random.choice(PROTOCOLS),
        "packet_count": random.randint(12, 48000),
        "syn_flag_count": syn,
        "flow_duration_ms": duration,
        "packets_per_second": pps,
    }
