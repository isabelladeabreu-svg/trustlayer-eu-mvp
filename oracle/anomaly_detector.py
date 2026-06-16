"""
TrustLayer EU — Oracle Anomaly Detector
MVP Component 1

Fetches ETH/USD price from 3 independent sources, detects:
  - Feed divergence (any feed deviates >5% from median)
  - Staleness (feed not updated within threshold)
  - Spike injection (simulates Synthetix KRW-style attack)

Output: verdict dict with confidence score + anomaly flags
"""

import time
import statistics
import random
from datetime import datetime, timezone


# ── Simulated price feeds (mimics real API responses) ────────────────────────
# In production these would be: CoinGecko, DeFi Llama, Chainlink REST, Binance
def fetch_feeds(inject_spike: bool = False, spike_multiplier: float = 10.0):
    """
    Simulate fetching ETH/USD from 3 independent sources.
    inject_spike: if True, corrupts feed_2 to simulate oracle manipulation.
    Returns list of dicts: {source, price, timestamp, latency_ms}
    """
    base_price = 3_241.50 + random.uniform(-15, 15)   # realistic ETH price variance

    feeds = [
        {
            "source": "CoinGecko",
            "price": round(base_price + random.uniform(-8, 8), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(80, 220),
            "status": "ok"
        },
        {
            "source": "DeFi Llama",
            "price": round(
                (base_price * spike_multiplier) if inject_spike
                else base_price + random.uniform(-10, 10),
                2
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(90, 310),
            "status": "ok"
        },
        {
            "source": "Binance API",
            "price": round(base_price + random.uniform(-6, 6), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(60, 180),
            "status": "ok"
        },
    ]
    return feeds


# ── Staleness check ────────────────────────────────────────────────────────────
def check_staleness(feeds, max_age_seconds: int = 60):
    """Flag any feed whose timestamp is older than max_age_seconds."""
    now = datetime.now(timezone.utc)
    stale = []
    for f in feeds:
        ts = datetime.fromisoformat(f["timestamp"])
        age = (now - ts).total_seconds()
        if age > max_age_seconds:
            stale.append(f["source"])
    return stale


# ── Divergence analysis ───────────────────────────────────────────────────────
def analyse_divergence(feeds, threshold_pct: float = 5.0):
    """
    Calculate median price. Flag any feed that deviates > threshold_pct%.
    Also computes a manipulation_probability score (0–100).
    """
    prices   = [f["price"] for f in feeds]
    median   = statistics.median(prices)
    mean     = statistics.mean(prices)
    deviations = []
    flagged  = []

    for f in feeds:
        pct_dev = abs(f["price"] - median) / median * 100
        deviations.append({"source": f["source"], "price": f["price"], "deviation_pct": round(pct_dev, 2)})
        if pct_dev > threshold_pct:
            flagged.append(f["source"])

    max_dev = max(d["deviation_pct"] for d in deviations)

    # Manipulation probability heuristic:
    # 0-5% dev → 0-10 score | 5-50% → linear 10-70 | >50% → 70-100
    if max_dev <= 5:
        manip_score = round(max_dev / 5 * 10, 1)
    elif max_dev <= 50:
        manip_score = round(10 + (max_dev - 5) / 45 * 60, 1)
    else:
        manip_score = round(min(70 + (max_dev - 50) / 50 * 30, 100), 1)

    return {
        "median_price": round(median, 2),
        "mean_price":   round(mean, 2),
        "deviations":   deviations,
        "flagged_feeds": flagged,
        "max_deviation_pct": round(max_dev, 2),
        "manipulation_probability": manip_score,
    }


# ── Circuit breaker logic ─────────────────────────────────────────────────────
def circuit_breaker(analysis: dict, stale: list):
    """
    Determine action based on analysis:
      AUTO_PASS      → no anomaly, proceed normally
      ALERT          → flag for monitoring, proceed with caution
      CIRCUIT_BREAK  → halt execution, escalate to human review
    """
    mp  = analysis["manipulation_probability"]
    dev = analysis["max_deviation_pct"]

    if stale:
        return "CIRCUIT_BREAK", f"Stale feeds detected: {stale}. Halting until feeds recover."
    elif mp >= 70 or dev > 20:
        return "CIRCUIT_BREAK", (
            f"HIGH anomaly: {dev:.1f}% deviation, "
            f"manipulation probability {mp}%. Escalating to human review."
        )
    elif mp >= 30 or dev > 5:
        return "ALERT", (
            f"MODERATE anomaly: {dev:.1f}% deviation, "
            f"manipulation probability {mp}%. Monitor closely."
        )
    else:
        return "AUTO_PASS", (
            f"Feeds within normal range. Deviation {dev:.1f}%, "
            f"manipulation probability {mp}%."
        )


# ── Evidence hash (stub for on-chain anchoring) ───────────────────────────────
def build_evidence_hash(feeds, analysis, action):
    """
    In production this would be keccak256(feeds_json + verdict).
    Here we produce a deterministic hex stub for demo purposes.
    """
    import hashlib, json
    payload = json.dumps({
        "feeds": feeds,
        "median": analysis["median_price"],
        "max_dev": analysis["max_deviation_pct"],
        "action": action,
        "ts": datetime.now(timezone.utc).isoformat()
    }, sort_keys=True)
    return "0x" + hashlib.sha256(payload.encode()).hexdigest()


# ── Main public function ───────────────────────────────────────────────────────
def run_oracle_check(inject_spike: bool = False, spike_multiplier: float = 10.0):
    """
    Full oracle anomaly check pipeline.
    Returns a structured result dict ready for the Flask API.
    """
    t0    = time.time()
    feeds = fetch_feeds(inject_spike=inject_spike, spike_multiplier=spike_multiplier)
    stale = check_staleness(feeds)
    analysis = analyse_divergence(feeds)
    action, message = circuit_breaker(analysis, stale)
    evidence_hash = build_evidence_hash(feeds, analysis, action)
    elapsed = round((time.time() - t0) * 1000, 1)

    # Confidence score: inverse of manipulation probability (how confident we are it's CLEAN)
    confidence = round(100 - analysis["manipulation_probability"], 1)

    return {
        "pipeline": "oracle_anomaly_monitor",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": elapsed,
        "feeds": feeds,
        "analysis": analysis,
        "stale_feeds": stale,
        "action": action,          # AUTO_PASS | ALERT | CIRCUIT_BREAK
        "message": message,
        "confidence_score": confidence,
        "evidence_hash": evidence_hash,
        "escalate_to_human": action == "CIRCUIT_BREAK",
        "layer_path": (
            "Data → AI → Consensus (auto-pass)"
            if action == "AUTO_PASS"
            else "Data → AI → Human Layer → Consensus"
        )
    }


# ── CLI demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    print("\n" + "="*60)
    print("  TrustLayer EU — Oracle Anomaly Detector Demo")
    print("="*60)

    print("\n[SCENARIO 1] Normal market conditions")
    print("-"*60)
    result = run_oracle_check(inject_spike=False)
    print(f"  Action          : {result['action']}")
    print(f"  Confidence      : {result['confidence_score']}%")
    print(f"  Max deviation   : {result['analysis']['max_deviation_pct']}%")
    print(f"  Manip. prob.    : {result['analysis']['manipulation_probability']}%")
    print(f"  Message         : {result['message']}")
    print(f"  Evidence hash   : {result['evidence_hash'][:20]}...")
    print(f"  Layer path      : {result['layer_path']}")

    print("\n[SCENARIO 2] Synthetix KRW-style spike — feed_2 inflated 10x")
    print("-"*60)
    result2 = run_oracle_check(inject_spike=True, spike_multiplier=10.0)
    print(f"  Action          : {result2['action']}")
    print(f"  Confidence      : {result2['confidence_score']}%")
    print(f"  Max deviation   : {result2['analysis']['max_deviation_pct']}%")
    print(f"  Manip. prob.    : {result2['analysis']['manipulation_probability']}%")
    print(f"  Flagged feeds   : {result2['analysis']['flagged_feeds']}")
    print(f"  Message         : {result2['message']}")
    print(f"  Escalate human  : {result2['escalate_to_human']}")
    print(f"  Evidence hash   : {result2['evidence_hash'][:20]}...")
    print(f"  Layer path      : {result2['layer_path']}")

    print("\n[FEED DETAILS — Scenario 2]")
    for f in result2["feeds"]:
        flag = " ⚠ SPIKED" if f["source"] in result2["analysis"]["flagged_feeds"] else ""
        print(f"  {f['source']:15s}  ${f['price']:>10,.2f}{flag}")
    print(f"\n  Median price    : ${result2['analysis']['median_price']:>10,.2f}")
    print()
