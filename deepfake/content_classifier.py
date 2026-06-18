"""
TrustLayer EU - Synthetic Content Triage Module
MVP Component 2

This secondary module demonstrates how the same layered control architecture
can extend beyond oracle integrity into synthetic-content verification.

The implementation uses lightweight byte-statistics and transparent metadata
heuristics. SynthID and parts of C2PA handling are simulated for demo purposes.
It is not a benchmarked production deepfake detector.
"""

import hashlib
import math
import random
import time
from datetime import datetime, timezone


def extract_pixel_features(image_bytes):
    """
    Extract lightweight byte-statistics for an explainable MVP signal.

    These are proxies for richer forensic checks. They help demonstrate the
    control flow but should not be treated as model-grade evidence.
    """
    byte_array = list(image_bytes[:8192])
    if not byte_array:
        return {"error": "empty_file"}

    freq = {}
    for value in byte_array:
        freq[value] = freq.get(value, 0) + 1

    total = len(byte_array)
    entropy = -sum((count / total) * math.log2(count / total) for count in freq.values())
    deltas = [abs(byte_array[i + 1] - byte_array[i]) for i in range(len(byte_array) - 1)]
    hf_variance = sum(delta ** 2 for delta in deltas) / len(deltas) if deltas else 0
    byte_range = max(byte_array) - min(byte_array)
    mean_value = sum(byte_array) / total
    mad = sum(abs(value - mean_value) for value in byte_array) / total

    return {
        "byte_entropy": round(entropy, 4),
        "hf_variance": round(hf_variance, 2),
        "byte_range": byte_range,
        "mean_abs_dev": round(mad, 2),
        "sample_size": total,
        "mvp_note": "Byte-statistics proxy; not a trained forensic model.",
    }


def score_pixel_features(features):
    """Convert byte-statistics into a synthetic-content triage score."""
    if "error" in features:
        return 50.0

    score = 0.0
    entropy = features["byte_entropy"]
    if entropy < 5.5:
        score += 35
    elif entropy < 6.5:
        score += 20
    elif entropy < 7.0:
        score += 10

    hf_variance = features["hf_variance"]
    if hf_variance < 500:
        score += 30
    elif hf_variance < 1500:
        score += 15
    elif hf_variance < 3000:
        score += 5

    byte_range = features["byte_range"]
    if byte_range < 150:
        score += 20
    elif byte_range < 200:
        score += 10
    elif byte_range < 230:
        score += 5

    mad = features["mean_abs_dev"]
    if mad < 40:
        score += 15
    elif mad < 60:
        score += 8
    elif mad < 80:
        score += 3

    return round(score, 1)


def check_c2pa(image_bytes, filename=""):
    """
    MVP-level C2PA provenance check.

    Production would parse C2PA/JUMBF metadata. This demo checks filename
    hints and a minimal byte header pattern so the workflow remains visible.
    """
    filename_lc = filename.lower()
    if any(token in filename_lc for token in ["ai", "synthetic", "generated", "deepfake", "fake"]):
        return {
            "status": "present",
            "generator": "Demo AI Media Service",
            "edited_with_ai": True,
            "detail": "Demo C2PA-like credential indicates AI-generated or AI-edited media.",
            "credential_hash": "0x" + hashlib.sha256(image_bytes[:256]).hexdigest()[:16],
            "simulated": True,
        }

    if any(token in filename_lc for token in ["stripped", "no_meta", "scrubbed"]):
        return {
            "status": "stripped",
            "generator": None,
            "edited_with_ai": None,
            "detail": "Metadata appears removed in this demo scenario. Absence of credentials does not prove authenticity.",
            "credential_hash": None,
            "simulated": True,
        }

    hex_header = image_bytes[:512].hex()
    has_jumbf_marker = "6a756d62" in hex_header
    if has_jumbf_marker:
        return {
            "status": "present",
            "generator": "Unknown credential issuer",
            "edited_with_ai": True,
            "detail": "JUMBF-like marker found in file header. Full C2PA validation is outside this MVP.",
            "credential_hash": "0x" + hashlib.sha256(image_bytes[:256]).hexdigest()[:16],
            "simulated": False,
        }

    return {
        "status": "absent",
        "generator": None,
        "edited_with_ai": None,
        "detail": "No credential marker found. This is inconclusive, not proof of authenticity.",
        "credential_hash": None,
        "simulated": False,
    }


def check_synthid(image_bytes, filename=""):
    """
    Simulate a SynthID-style watermark signal.

    Production would call the relevant provider verification API when available.
    """
    filename_lc = filename.lower()
    if any(token in filename_lc for token in ["synthid", "gemini", "google", "ai", "generated"]):
        return {
            "detected": True,
            "confidence": round(random.uniform(0.82, 0.97), 3),
            "detail": "Simulated SynthID-style watermark signal detected.",
            "simulated": True,
        }

    return {
        "detected": False,
        "confidence": round(random.uniform(0.05, 0.25), 3),
        "detail": "No simulated SynthID signal detected. This does not prove authentic origin.",
        "simulated": True,
    }


def ensemble_score(pixel_score, c2pa, synthid):
    """Combine the MVP signals into a transparent synthetic probability score."""
    if c2pa["status"] == "present":
        c2pa_score = 90.0
    elif c2pa["status"] == "stripped":
        c2pa_score = 55.0
    else:
        c2pa_score = 20.0

    synthid_score = synthid["confidence"] * 100 if synthid["detected"] else synthid["confidence"] * 30
    final = (pixel_score * 0.40) + (c2pa_score * 0.40) + (synthid_score * 0.20)
    return round(min(final, 100.0), 1)


def classify(synthetic_probability):
    """
    Return label, action, confidence, and control message.
    """
    if synthetic_probability < 30:
        return (
            "LIKELY AUTHENTIC",
            "AUTO_PASS",
            round(100 - synthetic_probability, 1),
            "Low synthetic-content score. Proceed through the normal workflow.",
        )

    if synthetic_probability <= 70:
        return (
            "INCONCLUSIVE",
            "ESCALATE_TO_HUMAN",
            round(100 - abs(synthetic_probability - 50) * 2, 1),
            "Ambiguous signals. Human review is required for any high-value action.",
        )

    return (
        "LIKELY SYNTHETIC",
        "CIRCUIT_BREAK",
        round(synthetic_probability, 1),
        "High synthetic-content score. Block the action and verify out of band.",
    )


def _risk_fields(label, action, c2pa, synthid):
    if action == "AUTO_PASS":
        return {
            "risk_level": "LOW",
            "failure_mode": "none",
            "recommended_control": "proceed",
            "business_impact_hint": "No material synthetic-content risk signal in the MVP triage.",
        }

    if action == "CIRCUIT_BREAK":
        failure_mode = "synthetic_content_signal"
        risk_level = "HIGH"
        recommended_control = "pause_and_review"
    else:
        failure_mode = "provenance_gap" if c2pa["status"] in ("absent", "stripped") else "ambiguous_content_signal"
        risk_level = "MEDIUM"
        recommended_control = "human_review"

    if synthid["detected"]:
        failure_mode = "synthetic_content_signal"

    return {
        "risk_level": risk_level,
        "failure_mode": failure_mode,
        "recommended_control": recommended_control,
        "business_impact_hint": "Impersonation, payment authorization, or evidence integrity risk.",
    }


def build_evidence_hash(image_bytes, result):
    payload = {
        "file_hash": hashlib.sha256(image_bytes).hexdigest(),
        "label": result["label"],
        "synthetic_probability": result["synthetic_probability"],
        "action": result["action"],
        "timestamp": result["timestamp"],
    }
    return "0x" + hashlib.sha256(
        str(sorted(payload.items())).encode("utf-8")
    ).hexdigest()


def classify_content(image_bytes, filename="upload.jpg", input_mode="uploaded_file"):
    """
    Full synthetic-content triage pipeline for the Flask API.
    """
    t0 = time.time()

    features = extract_pixel_features(image_bytes)
    pixel_score = score_pixel_features(features)
    c2pa = check_c2pa(image_bytes, filename)
    synthid = check_synthid(image_bytes, filename)
    synthetic_probability = ensemble_score(pixel_score, c2pa, synthid)
    label, action, confidence, message = classify(synthetic_probability)
    risk_fields = _risk_fields(label, action, c2pa, synthid)

    result = {
        "pipeline": "synthetic_content_triage",
        "module_role": "secondary_extension",
        "scenario_name": "Synthetic content triage",
        "filename": filename,
        "input_mode": input_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "file_size_bytes": len(image_bytes),
        "file_hash": "0x" + hashlib.sha256(image_bytes).hexdigest(),
        "pixel_features": features,
        "pixel_synthetic_score": pixel_score,
        "c2pa": c2pa,
        "synthid": synthid,
        "synthetic_probability": synthetic_probability,
        "label": label,
        "confidence_score": confidence,
        "action": action,
        "message": message,
        "escalate_to_human": action in ("ESCALATE_TO_HUMAN", "CIRCUIT_BREAK"),
        "layer_path": (
            "Data -> AI triage -> Consensus ledger"
            if action == "AUTO_PASS"
            else "Data -> AI triage -> Human review -> Consensus ledger"
        ),
        "signals_checked": [
            {
                "signal": "byte_statistics",
                "method": "MVP heuristic",
                "simulated": False,
                "inference": f"pixel_synthetic_score={pixel_score}",
            },
            {
                "signal": "c2pa_provenance",
                "method": "filename/header demo check",
                "simulated": c2pa.get("simulated", False),
                "inference": c2pa["status"],
            },
            {
                "signal": "synthid_watermark",
                "method": "simulated provider signal",
                "simulated": True,
                "inference": "detected" if synthid["detected"] else "not_detected",
            },
        ],
        "simulated_parts": [
            "SynthID watermark verification is simulated.",
            "C2PA handling is an MVP-level metadata demonstration, not full manifest validation.",
        ],
        **risk_fields,
    }

    result["evidence_hash"] = build_evidence_hash(image_bytes, result)
    return result


if __name__ == "__main__":
    demo_files = [
        ("family_photo.jpg", bytes([random.randint(0, 255) for _ in range(4096)])),
        ("corporate_videocall_ai_generated.jpg", bytes([random.randint(80, 180) for _ in range(4096)])),
        ("document_stripped.jpg", bytes([random.randint(60, 200) for _ in range(4096)])),
    ]

    for filename, payload in demo_files:
        result = classify_content(payload, filename, input_mode="simulation")
        print("\n" + filename)
        print("-" * 60)
        print(f"Label: {result['label']}")
        print(f"Action: {result['action']}")
        print(f"Risk: {result['risk_level']}")
        print(f"Synthetic probability: {result['synthetic_probability']}%")
        print(f"Evidence hash: {result['evidence_hash'][:22]}...")
