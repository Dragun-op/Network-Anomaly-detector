"""
Produces one "flow" dict per call -- the thing the scorer consumes.

Samples real held-out CICIDS-2017 rows (ml/data/test.parquet, written by
ml/preprocess.py) so TrainedModelScorer sees genuine feature vectors instead
of synthetic values it was never trained on. Each row already carries the
exact feature columns feature_pipeline.transform() expects, so it round-trips
through FeatureExtractor as a no-op. src_ip/dst_ip/protocol/packet_count
aren't in the CICIDS feature set (dropped during preprocessing), so those are
still synthesized for display purposes only -- they never reach the model.

If the parquet isn't available (e.g. only backend/ was checked out), falls
back to the old synthetic generator so nothing hard-crashes; that path only
ever produces "normal-looking" or "attack-like" rule-based signals, so it
won't drive TrainedModelScorer to anything meaningful, but it also won't be
the thing that ships broken -- rebuild ml/data/test.parquet to fix it.
"""
from __future__ import annotations

import random
from pathlib import Path

PROTOCOLS = ["TCP", "UDP", "ICMP"]

_TEST_PARQUET = Path(__file__).resolve().parents[3] / "ml" / "data" / "test.parquet"

_real_rows = None          # all held-out rows, feature columns only
_real_attack_rows = None   # subset with label != Benign, for demo pacing


def _rand_ip() -> str:
    return f"{random.randint(10,203)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _load_real_rows():
    global _real_rows, _real_attack_rows
    import pandas as pd

    df = pd.read_parquet(_TEST_PARQUET)
    feature_cols = [c for c in df.columns if c not in ("label", "label_raw")]
    _real_rows = df[feature_cols]
    _real_attack_rows = df.loc[df["label"] != "Benign", feature_cols]


def _synthetic_flow() -> dict:
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
        "syn_flag_count": syn,
        "flow_duration_ms": duration,
        "packets_per_second": pps,
    }


def next_flow() -> dict:
    """
    Returns a dict with both the raw fields an Incident row needs (src_ip,
    dst_ip, protocol, packet_count) and the real CICIDS feature fields
    TrainedModelScorer's feature pipeline reads (Flow Duration, Total Fwd
    Packets, ... -- see ml/artifacts/features.json for the full list).
    """
    if _real_rows is None and _TEST_PARQUET.exists():
        _load_real_rows()

    if _real_rows is not None and len(_real_rows):
        # Bias toward attack rows so the demo feed isn't 90% silent Benign
        # traffic, while still scoring genuine feature vectors either way.
        pool = _real_attack_rows if random.random() < 0.4 and len(_real_attack_rows) else _real_rows
        row = pool.sample(1).iloc[0]
        features = row.to_dict()
        fwd_pkts = int(features.get("Total Fwd Packets", 0) or 0)
        bwd_pkts = int(features.get("Total Backward Packets", 0) or 0)
        packet_count = max(fwd_pkts + bwd_pkts, 1)
    else:
        features = _synthetic_flow()
        packet_count = random.randint(12, 48000)

    return {
        **features,
        "src_ip": _rand_ip(),
        "dst_ip": _rand_ip(),
        "protocol": random.choice(PROTOCOLS),
        "packet_count": packet_count,
    }
