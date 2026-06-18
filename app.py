"""
TrustLayer EU - Flask Web Application
MVP Integration Layer

Routes:
  GET  /              -> Oracle-first dashboard
  POST /api/oracle    -> Oracle integrity monitor
  POST /api/classify  -> Synthetic content triage module
  GET  /api/verdicts  -> In-memory MVP verdict ledger
  POST /api/review    -> Simulated human-in-the-loop review event
  GET  /api/config    -> Oracle governance thresholds
  POST /api/config    -> Update oracle governance thresholds in memory
  GET  /api/health    -> Health check
"""

import os
import random
import sys
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, os.path.dirname(__file__))

from deepfake.content_classifier import classify_content
from oracle.anomaly_detector import (
    DEFAULT_ORACLE_CONFIG,
    SCENARIO_PRESETS,
    run_oracle_check,
)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ORACLE_CONFIG = DEFAULT_ORACLE_CONFIG.copy()
VERDICT_LEDGER = []
HUMAN_REVIEW_EVENTS = []

VALID_REVIEW_DECISIONS = {"APPROVE", "ESCALATE", "REJECT", "ADD_NOTE"}


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def add_to_ledger(result, pipeline):
    """Add a compact control/audit record to the in-memory MVP ledger."""
    review_required = bool(result.get("escalate_to_human", False))
    entry = {
        "id": len(VERDICT_LEDGER) + 1,
        "pipeline": pipeline,
        "pipeline_label": (
            "Oracle Integrity Monitor"
            if pipeline == "oracle_integrity"
            else "Synthetic Content Triage Module"
        ),
        "scenario_name": result.get("scenario_name", "n/a"),
        "failure_mode": result.get("failure_mode", "none"),
        "failure_modes": result.get("failure_modes", []),
        "risk_level": result.get("risk_level", "LOW"),
        "recommended_control": result.get("recommended_control", "proceed"),
        "action": result.get("action"),
        "confidence": result.get("confidence_score"),
        "evidence_hash": result.get("evidence_hash", "n/a"),
        "escalated": review_required,
        "human_review_status": "REVIEW_PENDING" if review_required else "NOT_REQUIRED",
        "final_reviewed_status": "PENDING_REVIEW" if review_required else "SYSTEM_ACCEPTED",
        "timestamp": utc_timestamp(),
        "layer_path": result.get("layer_path", ""),
        "business_impact_hint": result.get("business_impact_hint", ""),
        "system_message": result.get("message", ""),
        "review_events": [],
        "original_verdict": {
            "action": result.get("action"),
            "risk_level": result.get("risk_level"),
            "failure_mode": result.get("failure_mode"),
            "recommended_control": result.get("recommended_control"),
            "confidence_score": result.get("confidence_score"),
            "evidence_hash": result.get("evidence_hash", "n/a"),
            "message": result.get("message", ""),
        },
    }
    VERDICT_LEDGER.append(entry)
    return entry["id"]


def find_verdict(verdict_id):
    for verdict in VERDICT_LEDGER:
        if verdict["id"] == verdict_id:
            return verdict
    return None


def apply_review_decision(verdict, decision, note, reviewer):
    event = {
        "id": len(HUMAN_REVIEW_EVENTS) + 1,
        "verdict_id": verdict["id"],
        "decision": decision,
        "note": note,
        "reviewer": reviewer or "MVP Reviewer",
        "timestamp": utc_timestamp(),
    }
    HUMAN_REVIEW_EVENTS.append(event)
    verdict["review_events"].append(event)

    if decision == "APPROVE":
        verdict["human_review_status"] = "APPROVED"
        verdict["final_reviewed_status"] = "APPROVED_TO_PROCEED"
    elif decision == "REJECT":
        verdict["human_review_status"] = "REJECTED"
        verdict["final_reviewed_status"] = "REJECTED_BLOCKED"
    elif decision == "ESCALATE":
        verdict["human_review_status"] = "ESCALATED"
        verdict["final_reviewed_status"] = "ESCALATED_TO_SECOND_LINE"
    elif decision == "ADD_NOTE":
        if verdict["human_review_status"] == "NOT_REQUIRED":
            verdict["human_review_status"] = "NOTE_ADDED"
        verdict["final_reviewed_status"] = (
            "PENDING_REVIEW"
            if verdict["human_review_status"] == "REVIEW_PENDING"
            else verdict["final_reviewed_status"]
        )

    return event


def parse_config_update(body):
    updated = ORACLE_CONFIG.copy()
    numeric_fields = {
        "divergence_threshold_pct": float,
        "stale_threshold_seconds": int,
        "minimum_active_sources": int,
        "circuit_break_threshold_pct": float,
        "minimum_source_diversity_score": float,
    }
    for key, converter in numeric_fields.items():
        if key not in body:
            continue
        value = converter(body[key])
        if key in ("divergence_threshold_pct", "circuit_break_threshold_pct") and value <= 0:
            raise ValueError(f"{key} must be greater than zero")
        if key == "stale_threshold_seconds" and value < 5:
            raise ValueError("stale_threshold_seconds must be at least 5")
        if key == "minimum_active_sources" and value < 1:
            raise ValueError("minimum_active_sources must be at least 1")
        if key == "minimum_source_diversity_score" and not 0 <= value <= 1:
            raise ValueError("minimum_source_diversity_score must be between 0 and 1")
        updated[key] = value
    return updated


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        scenario_presets=SCENARIO_PRESETS,
    )


@app.route("/api/oracle", methods=["POST"])
def api_oracle():
    body = request.get_json(silent=True) or {}
    scenario = body.get("scenario", "normal")
    inject_spike = bool(body.get("inject_spike", False))
    result = run_oracle_check(
        scenario=scenario,
        inject_spike=inject_spike,
        config=ORACLE_CONFIG,
    )
    verdict_id = add_to_ledger(result, "oracle_integrity")
    result["verdict_id"] = verdict_id
    return jsonify(result)


@app.route("/api/classify", methods=["POST"])
def api_classify():
    if "file" in request.files:
        uploaded_file = request.files["file"]
        image_bytes = uploaded_file.read()
        filename = uploaded_file.filename or "upload"
        input_mode = "uploaded_file"
    else:
        body = request.get_json(silent=True) or {}
        filename = body.get("simulate_filename", "test_image.jpg")
        input_mode = "filename_simulation"
        filename_lc = filename.lower()
        if any(token in filename_lc for token in ["ai", "synthetic", "generated", "deepfake"]):
            image_bytes = bytes([random.randint(80, 180) for _ in range(4096)])
        elif any(token in filename_lc for token in ["stripped", "scrubbed", "no_meta"]):
            image_bytes = bytes([random.randint(60, 200) for _ in range(4096)])
        else:
            image_bytes = bytes([random.randint(0, 255) for _ in range(4096)])

    result = classify_content(image_bytes, filename, input_mode=input_mode)
    verdict_id = add_to_ledger(result, "synthetic_content")
    result["verdict_id"] = verdict_id
    return jsonify(result)


@app.route("/api/verdicts", methods=["GET"])
def api_verdicts():
    return jsonify({
        "total": len(VERDICT_LEDGER),
        "verdicts": VERDICT_LEDGER,
        "review_events": HUMAN_REVIEW_EVENTS,
        "note": (
            "In-memory MVP ledger. Production would anchor evidence hashes "
            "to TrustLayerVerdicts.sol or an equivalent on-chain registry."
        ),
    })


@app.route("/api/review", methods=["POST"])
def api_review():
    body = request.get_json(silent=True) or {}
    try:
        verdict_id = int(body.get("verdict_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "verdict_id is required"}), 400

    decision = str(body.get("decision", "")).upper()
    if decision not in VALID_REVIEW_DECISIONS:
        return jsonify({
            "error": "decision must be one of APPROVE, ESCALATE, REJECT, ADD_NOTE",
        }), 400

    verdict = find_verdict(verdict_id)
    if not verdict:
        return jsonify({"error": "verdict not found"}), 404

    event = apply_review_decision(
        verdict=verdict,
        decision=decision,
        note=body.get("note", ""),
        reviewer=body.get("reviewer", "MVP Reviewer"),
    )
    return jsonify({"review_event": event, "verdict": verdict})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    global ORACLE_CONFIG
    if request.method == "GET":
        return jsonify({
            "config": ORACLE_CONFIG,
            "note": "Session-level MVP governance thresholds.",
        })

    body = request.get_json(silent=True) or {}
    try:
        ORACLE_CONFIG = parse_config_update(body)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "config": ORACLE_CONFIG,
        "note": "Oracle governance thresholds updated for this Flask session.",
    })


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "service": "TrustLayer EU MVP",
        "version": "2.0.0",
        "primary_pipeline": "oracle_integrity_monitor",
        "extension_pipeline": "synthetic_content_triage",
        "timestamp": utc_timestamp(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("TRUSTLAYER_PORT", "5050"))
    print("\n" + "=" * 60)
    print("  TrustLayer EU - Oracle-first MVP Flask App")
    print(f"  http://localhost:{port}")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
