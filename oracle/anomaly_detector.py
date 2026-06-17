"""
TrustLayer EU - Oracle Integrity Monitor
MVP Component 1

This module simulates an operational control around external market data:
external data risk -> anomaly detection -> control decision -> escalation
-> tamper-evident evidence hash.

The heuristics are intentionally simple and explainable for a classroom MVP.
They are not a replacement for production oracle monitoring.
"""

import hashlib
import json
import random
import statistics
import time
from datetime import datetime, timedelta, timezone


DEFAULT_ORACLE_CONFIG = {
    "divergence_threshold_pct": 5.0,
    "stale_threshold_seconds": 60,
    "minimum_active_sources": 3,
    "circuit_break_threshold_pct": 20.0,
    "minimum_source_diversity_score": 0.70,
}


SCENARIO_PRESETS = {
    "normal": {
        "name": "Normal market conditions",
        "description": "All sources are active, fresh, and close to the market median.",
    },
    "manipulated_spike": {
        "name": "Manipulated spike",
        "description": "One feed is inflated to simulate price manipulation.",
    },
    "stale_feed": {
        "name": "Stale feed",
        "description": "One source is active but older than the governed freshness threshold.",
    },
    "degraded_redundancy": {
        "name": "Reduced source redundancy / degraded fallback",
        "description": "Two independent sources are unavailable, creating fallback weakness.",
    },
    "combined_risk": {
        "name": "Combined risk scenario",
        "description": "One source is stale, one source is anomalous, and redundancy is weak.",
    },
}


SOURCE_TEMPLATE = [
    {"source": "CoinGecko", "source_type": "market_data_aggregator"},
    {"source": "DeFi Llama", "source_type": "defi_aggregator"},
    {"source": "Binance API", "source_type": "exchange_api"},
    {"source": "Chainlink Reference", "source_type": "decentralized_oracle"},
]


def _utc_now():
    return datetime.now(timezone.utc)


def _clean_config(config=None):
    merged = DEFAULT_ORACLE_CONFIG.copy()
    if config:
        for key in merged:
            if key in config:
                merged[key] = config[key]
    merged["divergence_threshold_pct"] = float(merged["divergence_threshold_pct"])
    merged["stale_threshold_seconds"] = int(merged["stale_threshold_seconds"])
    merged["minimum_active_sources"] = int(merged["minimum_active_sources"])
    merged["circuit_break_threshold_pct"] = float(merged["circuit_break_threshold_pct"])
    merged["minimum_source_diversity_score"] = float(merged["minimum_source_diversity_score"])
    return merged


def normalise_scenario(scenario):
    if scenario in SCENARIO_PRESETS:
        return scenario
    return "normal"


def fetch_feeds(scenario="normal", config=None, spike_multiplier=None):
    """
    Simulate fetching ETH/USD from independent oracle/data sources.

    In production these would be signed responses from vendors or nodes.
    Here each scenario mutates a transparent set of simulated feed records.
    """
    config = _clean_config(config)
    scenario = normalise_scenario(scenario)
    now = _utc_now()
    base_price = 3241.50 + random.uniform(-12, 12)

    feeds = []
    for source in SOURCE_TEMPLATE:
        feeds.append({
            **source,
            "asset_pair": "ETH/USD",
            "price": round(base_price + random.uniform(-7, 7), 2),
            "timestamp": now.isoformat(),
            "latency_ms": random.randint(70, 260),
            "status": "ok",
            "active": True,
        })

    if scenario == "manipulated_spike":
        multiplier = spike_multiplier if spike_multiplier is not None else 1.28
        feeds[1]["price"] = round(base_price * multiplier, 2)
        feeds[1]["status"] = "price_spike"

    if scenario == "stale_feed":
        stale_at = now - timedelta(seconds=config["stale_threshold_seconds"] * 4)
        feeds[0]["timestamp"] = stale_at.isoformat()
        feeds[0]["latency_ms"] = random.randint(950, 1400)
        feeds[0]["status"] = "stale"

    if scenario == "degraded_redundancy":
        for idx, status in [(1, "source_outage"), (3, "timeout")]:
            feeds[idx]["price"] = None
            feeds[idx]["timestamp"] = None
            feeds[idx]["latency_ms"] = None
            feeds[idx]["status"] = status
            feeds[idx]["active"] = False

    if scenario == "combined_risk":
        stale_at = now - timedelta(seconds=config["stale_threshold_seconds"] * 5)
        feeds[0]["timestamp"] = stale_at.isoformat()
        feeds[0]["status"] = "stale"
        feeds[0]["latency_ms"] = random.randint(1000, 1600)

        multiplier = spike_multiplier if spike_multiplier is not None else 1.24
        feeds[1]["price"] = round(base_price * multiplier, 2)
        feeds[1]["status"] = "price_spike"

        feeds[3]["price"] = None
        feeds[3]["timestamp"] = None
        feeds[3]["latency_ms"] = None
        feeds[3]["status"] = "source_outage"
        feeds[3]["active"] = False

    return feeds


def check_staleness(feeds, max_age_seconds=60):
    """Return stale source names and annotate active feeds with age in seconds."""
    now = _utc_now()
    stale = []
    for feed in feeds:
        if not feed.get("active"):
            feed["age_seconds"] = None
            continue
        timestamp = feed.get("timestamp")
        if not timestamp:
            feed["age_seconds"] = None
            continue
        age = (now - datetime.fromisoformat(timestamp)).total_seconds()
        feed["age_seconds"] = round(age, 1)
        if age > max_age_seconds or feed.get("status") == "stale":
            stale.append(feed["source"])
    return stale


def analyse_divergence(feeds, threshold_pct=5.0):
    """
    Calculate the market median and flag active feeds that diverge from it.
    Unavailable sources are excluded from median calculation but remain visible.
    """
    active_price_feeds = [
        feed for feed in feeds
        if feed.get("active") and isinstance(feed.get("price"), (int, float))
    ]

    if not active_price_feeds:
        return {
            "median_price": None,
            "mean_price": None,
            "deviations": [],
            "flagged_feeds": [],
            "max_deviation_pct": 0.0,
            "manipulation_probability": 100.0,
        }

    prices = [feed["price"] for feed in active_price_feeds]
    median = statistics.median(prices)
    mean = statistics.mean(prices)
    deviations = []
    flagged = []

    for feed in active_price_feeds:
        pct_dev = abs(feed["price"] - median) / median * 100 if median else 0
        rounded_dev = round(pct_dev, 2)
        feed["deviation_pct"] = rounded_dev
        deviations.append({
            "source": feed["source"],
            "price": feed["price"],
            "deviation_pct": rounded_dev,
        })
        if pct_dev > threshold_pct:
            flagged.append(feed["source"])

    max_dev = max(item["deviation_pct"] for item in deviations) if deviations else 0.0
    if max_dev <= threshold_pct:
        manipulation_probability = round(max_dev / max(threshold_pct, 0.01) * 12, 1)
    elif max_dev <= 50:
        manipulation_probability = round(12 + (max_dev - threshold_pct) / 45 * 63, 1)
    else:
        manipulation_probability = round(min(75 + (max_dev - 50) / 50 * 25, 100), 1)

    return {
        "median_price": round(median, 2),
        "mean_price": round(mean, 2),
        "deviations": deviations,
        "flagged_feeds": flagged,
        "max_deviation_pct": round(max_dev, 2),
        "manipulation_probability": manipulation_probability,
    }


def assess_source_health(feeds, analysis, stale_feeds, config):
    flagged = set(analysis["flagged_feeds"])
    stale = set(stale_feeds)
    active_feeds = [feed for feed in feeds if feed.get("active")]
    inactive_feeds = [feed for feed in feeds if not feed.get("active")]
    healthy_feeds = [
        feed for feed in active_feeds
        if feed["source"] not in flagged and feed["source"] not in stale
    ]
    healthy_types = {feed["source_type"] for feed in healthy_feeds}
    diversity_score = round(len(healthy_types) / len(SOURCE_TEMPLATE), 2)

    min_sources = config["minimum_active_sources"]
    min_diversity = config["minimum_source_diversity_score"]
    healthy_count = len(healthy_feeds)
    active_count = len(active_feeds)

    if healthy_count >= min_sources and diversity_score >= min_diversity:
        redundancy_status = "healthy"
    elif healthy_count <= 1:
        redundancy_status = "single_source_dependency"
    elif active_count < min_sources or healthy_count < min_sources:
        redundancy_status = "degraded_fallback"
    else:
        redundancy_status = "low_source_diversity"

    return {
        "active_sources": active_count,
        "healthy_sources": healthy_count,
        "inactive_sources": len(inactive_feeds),
        "inactive_source_names": [feed["source"] for feed in inactive_feeds],
        "source_diversity_score": diversity_score,
        "redundancy_status": redundancy_status,
    }


def evaluate_control_decision(analysis, source_health, stale_feeds, config):
    max_dev = analysis["max_deviation_pct"]
    failure_modes = []

    if max_dev > config["divergence_threshold_pct"]:
        failure_modes.append("price_spike")
    if stale_feeds:
        failure_modes.append("stale_feed")
    if source_health["inactive_sources"]:
        failure_modes.append("source_outage")
    if (
        source_health["active_sources"] < config["minimum_active_sources"]
        or source_health["healthy_sources"] < config["minimum_active_sources"]
    ):
        failure_modes.append("degraded_redundancy")
    if source_health["source_diversity_score"] < config["minimum_source_diversity_score"]:
        failure_modes.append("low_source_diversity")

    if not failure_modes:
        return {
            "risk_level": "LOW",
            "failure_mode": "none",
            "failure_modes": [],
            "recommended_control": "proceed",
            "action": "AUTO_PASS",
            "business_impact_hint": "No material oracle integrity impact detected.",
            "control_message": "Sources are fresh, redundant, and within the governed divergence threshold.",
            "confidence_score": 95.0,
        }

    core_modes = {"price_spike", "stale_feed", "source_outage", "degraded_redundancy"}
    combined = len(core_modes.intersection(failure_modes)) >= 2
    failure_mode = "combined_signal" if combined else failure_modes[0]

    if (
        max_dev >= config["circuit_break_threshold_pct"]
        or (combined and "price_spike" in failure_modes)
        or source_health["healthy_sources"] <= 1
    ):
        risk_level = "CRITICAL"
        recommended_control = "circuit_break"
        action = "CIRCUIT_BREAK"
        confidence = 92.0
    elif (
        source_health["active_sources"] < config["minimum_active_sources"]
        or source_health["healthy_sources"] < config["minimum_active_sources"]
        or max_dev > config["divergence_threshold_pct"] * 2
    ):
        risk_level = "HIGH"
        recommended_control = "pause_and_review"
        action = "ESCALATE_TO_HUMAN"
        confidence = 86.0
    else:
        risk_level = "MEDIUM"
        recommended_control = "monitor"
        action = "ALERT"
        confidence = 78.0

    impact_by_mode = {
        "price_spike": "Collateral mispricing and liquidation risk.",
        "stale_feed": "Settlement integrity risk from delayed market state.",
        "source_outage": "Fallback weakness and reduced operational resilience.",
        "degraded_redundancy": "Single-source dependency risk in a stressed market.",
        "low_source_diversity": "Consensus quality weakens when independent source types are limited.",
        "combined_signal": "Collateral mispricing, liquidation, and settlement integrity risk.",
    }

    return {
        "risk_level": risk_level,
        "failure_mode": failure_mode,
        "failure_modes": failure_modes,
        "recommended_control": recommended_control,
        "action": action,
        "business_impact_hint": impact_by_mode.get(failure_mode, "Operational data integrity risk."),
        "control_message": _build_control_message(
            risk_level, failure_modes, max_dev, source_health, stale_feeds
        ),
        "confidence_score": confidence,
    }


def _build_control_message(risk_level, failure_modes, max_dev, source_health, stale_feeds):
    parts = [
        f"{risk_level} oracle integrity risk",
        f"max deviation {max_dev:.2f}%",
        f"{source_health['healthy_sources']} healthy of {len(SOURCE_TEMPLATE)} configured sources",
    ]
    if stale_feeds:
        parts.append(f"stale feeds: {', '.join(stale_feeds)}")
    if failure_modes:
        parts.append(f"signals: {', '.join(failure_modes)}")
    return ". ".join(parts) + "."


def build_evidence_hash(feeds, analysis, source_health, controls, config, scenario):
    """
    Production would anchor a keccak256 hash on-chain. The MVP uses SHA-256.
    """
    payload = json.dumps({
        "scenario": scenario,
        "feeds": feeds,
        "analysis": analysis,
        "source_health": source_health,
        "controls": controls,
        "config": config,
        "timestamp": _utc_now().isoformat(),
    }, sort_keys=True)
    return "0x" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_oracle_check(inject_spike=False, spike_multiplier=None, scenario="normal", config=None):
    """
    Run the full oracle integrity pipeline and return a structured verdict.
    """
    t0 = time.time()
    config = _clean_config(config)
    if inject_spike:
        scenario = "manipulated_spike"
        spike_multiplier = spike_multiplier if spike_multiplier is not None else 10.0

    scenario = normalise_scenario(scenario)
    feeds = fetch_feeds(scenario=scenario, config=config, spike_multiplier=spike_multiplier)
    stale_feeds = check_staleness(feeds, max_age_seconds=config["stale_threshold_seconds"])
    analysis = analyse_divergence(feeds, threshold_pct=config["divergence_threshold_pct"])
    source_health = assess_source_health(feeds, analysis, stale_feeds, config)
    controls = evaluate_control_decision(analysis, source_health, stale_feeds, config)
    evidence_hash = build_evidence_hash(feeds, analysis, source_health, controls, config, scenario)
    elapsed = round((time.time() - t0) * 1000, 1)

    result = {
        "pipeline": "oracle_integrity_monitor",
        "scenario": scenario,
        "scenario_name": SCENARIO_PRESETS[scenario]["name"],
        "scenario_description": SCENARIO_PRESETS[scenario]["description"],
        "timestamp": _utc_now().isoformat(),
        "elapsed_ms": elapsed,
        "asset_pair": "ETH/USD",
        "feeds": feeds,
        "analysis": analysis,
        "stale_feeds": stale_feeds,
        "active_sources": source_health["active_sources"],
        "healthy_sources": source_health["healthy_sources"],
        "inactive_sources": source_health["inactive_sources"],
        "inactive_source_names": source_health["inactive_source_names"],
        "source_diversity_score": source_health["source_diversity_score"],
        "redundancy_status": source_health["redundancy_status"],
        "risk_level": controls["risk_level"],
        "failure_mode": controls["failure_mode"],
        "failure_modes": controls["failure_modes"],
        "recommended_control": controls["recommended_control"],
        "business_impact_hint": controls["business_impact_hint"],
        "action": controls["action"],
        "message": controls["control_message"],
        "confidence_score": controls["confidence_score"],
        "evidence_hash": evidence_hash,
        "escalate_to_human": controls["action"] in ("ESCALATE_TO_HUMAN", "CIRCUIT_BREAK"),
        "layer_path": (
            "Data -> AI control -> Consensus ledger"
            if controls["action"] == "AUTO_PASS"
            else "Data -> AI control -> Human review -> Consensus ledger"
        ),
        "governance_config_used": config,
    }
    return result


if __name__ == "__main__":
    for scenario_key in SCENARIO_PRESETS:
        result = run_oracle_check(scenario=scenario_key)
        print("\n" + SCENARIO_PRESETS[scenario_key]["name"])
        print("-" * 60)
        print(f"Action: {result['action']}")
        print(f"Risk: {result['risk_level']}")
        print(f"Failure mode: {result['failure_mode']}")
        print(f"Recommended control: {result['recommended_control']}")
        print(f"Healthy sources: {result['healthy_sources']}/{len(SOURCE_TEMPLATE)}")
        print(f"Max deviation: {result['analysis']['max_deviation_pct']}%")
        print(f"Evidence hash: {result['evidence_hash'][:22]}...")
