"""
TrustLayer EU — Flask Web Application
MVP Integration Layer

Routes:
  GET  /                    → Dashboard (upload + oracle check UI)
  POST /api/classify        → AI content classifier pipeline
  POST /api/oracle          → Oracle anomaly detector pipeline
  GET  /api/verdicts        → In-memory verdict ledger (on-chain stub)
  GET  /api/health          → Health check
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from oracle.anomaly_detector  import run_oracle_check
from deepfake.content_classifier import classify_content

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

# ── In-memory verdict ledger (replaces on-chain for MVP demo) ─────────────────
VERDICT_LEDGER = []

def add_to_ledger(result: dict, pipeline: str):
    entry = {
        "id":             len(VERDICT_LEDGER) + 1,
        "pipeline":       pipeline,
        "action":         result.get("action"),
        "confidence":     result.get("confidence_score"),
        "evidence_hash":  result.get("evidence_hash", "n/a"),
        "escalated":      result.get("escalate_to_human", False),
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "layer_path":     result.get("layer_path", ""),
    }
    VERDICT_LEDGER.append(entry)
    return entry["id"]


# ── HTML Dashboard ────────────────────────────────────────────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>TrustLayer EU — MVP</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body   { font-family: Arial, sans-serif; background: #f4f6f4; color: #1a2a1a; }
    header { background: #1A3A2A; color: #fff; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
    header h1 { font-size: 1.4rem; }
    header span { font-size: 0.85rem; color: #9FBFB0; }
    .container { max-width: 1100px; margin: 0 auto; padding: 28px 20px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    .card { background: #fff; border-radius: 10px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
    .card h2 { font-size: 1.05rem; color: #1D9E75; margin-bottom: 14px; border-bottom: 2px solid #E1F5EE; padding-bottom: 8px; }
    label  { display: block; font-size: .85rem; color: #444; margin-bottom: 4px; margin-top: 10px; }
    input[type=file], input[type=text], select {
      width: 100%; padding: 8px 10px; border: 1px solid #ccc; border-radius: 6px;
      font-size: .9rem; margin-bottom: 4px;
    }
    .btn { display: inline-block; padding: 10px 22px; border-radius: 6px; border: none;
           font-size: .9rem; font-weight: bold; cursor: pointer; margin-top: 12px; }
    .btn-teal  { background: #1D9E75; color: #fff; }
    .btn-coral { background: #D85A30; color: #fff; }
    .btn:hover { opacity: .88; }
    .result-box { margin-top: 16px; background: #f8faf8; border-radius: 8px; padding: 14px;
                  font-size: .82rem; white-space: pre-wrap; font-family: monospace;
                  border-left: 4px solid #1D9E75; max-height: 340px; overflow-y: auto; display:none; }
    .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size:.78rem; font-weight:bold; }
    .badge-pass    { background:#D4EDDA; color:#155724; }
    .badge-alert   { background:#FFF3CD; color:#856404; }
    .badge-human   { background:#D1ECF1; color:#0C5460; }
    .badge-break   { background:#F8D7DA; color:#721C24; }
    #ledger { margin-top: 28px; }
    #ledger h2 { font-size: 1rem; color: #1A3A2A; margin-bottom: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: .82rem; }
    th { background: #1A3A2A; color: #fff; padding: 8px 10px; text-align: left; }
    td { padding: 7px 10px; border-bottom: 1px solid #eee; }
    tr:hover td { background: #f0faf5; }
    .tag { font-size:.75rem; color:#888; background:#eee; padding:2px 7px; border-radius:10px; }
  </style>
</head>
<body>
<header>
  <div>
    <h1>TrustLayer EU &nbsp;·&nbsp; MVP Dashboard</h1>
    <span>Group 1 — Operational &amp; Technology Risk &nbsp;|&nbsp; IE University</span>
  </div>
</header>
<div class="container">
  <div class="grid">

    <!-- ── ORACLE PANEL ──────────────────────────────────────────── -->
    <div class="card">
      <h2>🔗 Oracle Anomaly Detector</h2>
      <p style="font-size:.85rem;color:#555;margin-bottom:12px;">
        Fetches ETH/USD from 3 independent feeds. Detects price divergence,
        staleness, and manipulation spikes. Reproduces the Synthetix KRW incident.
      </p>
      <label>Simulation mode</label>
      <select id="oracle-mode">
        <option value="normal">Normal market conditions</option>
        <option value="spike">Synthetix-style spike (10× manipulation)</option>
      </select>
      <button class="btn btn-teal" onclick="runOracle()">Run Oracle Check</button>
      <div class="result-box" id="oracle-result"></div>
    </div>

    <!-- ── CONTENT CLASSIFIER PANEL ─────────────────────────────── -->
    <div class="card">
      <h2>🎭 AI Content Classifier</h2>
      <p style="font-size:.85rem;color:#555;margin-bottom:12px;">
        Checks uploaded media for deepfake signals, C2PA provenance credentials,
        and SynthID watermarks. Reproduces the HK deepfake fraud scenario.
      </p>
      <label>Upload image / media file</label>
      <input type="file" id="content-file" accept="image/*,video/*,audio/*"/>
      <label style="margin-top:8px;">Or enter filename to simulate a scenario</label>
      <input type="text" id="sim-filename" placeholder="e.g. corporate_videocall_ai_generated.jpg"/>
      <button class="btn btn-coral" onclick="runClassifier()">Classify Content</button>
      <div class="result-box" id="content-result"></div>
    </div>

  </div>

  <!-- ── VERDICT LEDGER ─────────────────────────────────────────── -->
  <div id="ledger">
    <h2>📋 On-Chain Verdict Ledger <span class="tag">in-memory stub → Solidity contract in production</span></h2>
    <table>
      <thead>
        <tr><th>#</th><th>Pipeline</th><th>Action</th><th>Confidence</th><th>Layer Path</th><th>Escalated</th><th>Evidence Hash</th><th>Time</th></tr>
      </thead>
      <tbody id="ledger-body">
        <tr><td colspan="8" style="color:#aaa;text-align:center;padding:20px;">No verdicts yet — run a check above</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
function badgeHtml(action) {
  const map = {
    AUTO_PASS:         '<span class="badge badge-pass">AUTO PASS</span>',
    ALERT:             '<span class="badge badge-alert">ALERT</span>',
    ESCALATE_TO_HUMAN: '<span class="badge badge-human">HUMAN REVIEW</span>',
    CIRCUIT_BREAK:     '<span class="badge badge-break">CIRCUIT BREAK</span>',
  };
  return map[action] || action;
}

async function runOracle() {
  const mode = document.getElementById('oracle-mode').value;
  const box  = document.getElementById('oracle-result');
  box.style.display = 'block';
  box.textContent = 'Running oracle check…';
  const resp = await fetch('/api/oracle', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ inject_spike: mode === 'spike' })
  });
  const data = await resp.json();
  box.innerHTML = '<b>Action: </b>' + badgeHtml(data.action) + '  Confidence: <b>' + data.confidence_score + '%</b>\\n\\n' + JSON.stringify(data, null, 2);
  refreshLedger();
}

async function runClassifier() {
  const file    = document.getElementById('content-file').files[0];
  const simName = document.getElementById('sim-filename').value.trim();
  const box     = document.getElementById('content-result');
  box.style.display = 'block';
  box.textContent = 'Classifying content…';

  let resp;
  if (file) {
    const fd = new FormData();
    fd.append('file', file);
    resp = await fetch('/api/classify', { method: 'POST', body: fd });
  } else if (simName) {
    resp = await fetch('/api/classify', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ simulate_filename: simName })
    });
  } else {
    box.textContent = 'Please upload a file or enter a simulation filename.';
    return;
  }

  const data = await resp.json();
  box.innerHTML = '<b>Label: ' + data.label + '</b>  Action: ' + badgeHtml(data.action) + '  Confidence: <b>' + data.confidence_score + '%</b>\\n\\n' + JSON.stringify(data, null, 2);
  refreshLedger();
}

async function refreshLedger() {
  const resp = await fetch('/api/verdicts');
  const data = await resp.json();
  const tbody = document.getElementById('ledger-body');
  if (!data.verdicts.length) return;
  tbody.innerHTML = data.verdicts.slice().reverse().map(v => `
    <tr>
      <td>${v.id}</td>
      <td>${v.pipeline}</td>
      <td>${badgeHtml(v.action)}</td>
      <td>${v.confidence}%</td>
      <td style="font-size:.75rem">${v.layer_path}</td>
      <td>${v.escalated ? '⚠ Yes' : '✓ No'}</td>
      <td style="font-family:monospace;font-size:.75rem">${v.evidence_hash.slice(0,18)}…</td>
      <td style="font-size:.75rem">${v.timestamp.slice(11,19)} UTC</td>
    </tr>
  `).join('');
}

// Auto-refresh ledger every 5s
setInterval(refreshLedger, 5000);
</script>
</body>
</html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/oracle", methods=["POST"])
def api_oracle():
    body = request.get_json(silent=True) or {}
    inject = bool(body.get("inject_spike", False))
    result = run_oracle_check(inject_spike=inject)
    add_to_ledger(result, "oracle_anomaly")
    return jsonify(result)


@app.route("/api/classify", methods=["POST"])
def api_classify():
    # Real file upload
    if "file" in request.files:
        f = request.files["file"]
        image_bytes = f.read()
        filename    = f.filename or "upload"
    else:
        # Simulation via filename
        body = request.get_json(silent=True) or {}
        sim_name    = body.get("simulate_filename", "test_image.jpg")
        import random
        # Generate bytes based on filename hint to drive realistic scenarios
        fn = sim_name.lower()
        if any(k in fn for k in ["ai", "synthetic", "generated", "deepfake"]):
            image_bytes = bytes([random.randint(80, 180) for _ in range(4096)])
        else:
            image_bytes = bytes([random.randint(0, 255) for _ in range(4096)])
        filename = sim_name

    result = classify_content(image_bytes, filename)
    add_to_ledger(result, "content_classifier")
    return jsonify(result)


@app.route("/api/verdicts", methods=["GET"])
def api_verdicts():
    return jsonify({
        "total": len(VERDICT_LEDGER),
        "verdicts": VERDICT_LEDGER,
        "note": "In-memory ledger for MVP. Production: Solidity TrustLayerVerdicts.sol on EVM."
    })


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "service": "TrustLayer EU MVP",
        "version": "1.0.0",
        "pipelines": ["oracle_anomaly", "content_classifier"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  TrustLayer EU — MVP Flask App")
    print("  http://localhost:5050")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
