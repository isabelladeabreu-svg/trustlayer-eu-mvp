# TrustLayer EU — MVP
**Group 1 · Operational & Technology Risk · IE University · June 2026**

---

## What This Is
A working Minimum Viable Product demonstrating the two core pipelines of TrustLayer EU:

| Component | File | What it proves |
|---|---|---|
| Oracle Anomaly Detector | `oracle/anomaly_detector.py` | Detects price feed manipulation (Synthetix KRW scenario) |
| AI Content Classifier | `deepfake/content_classifier.py` | Classifies deepfakes via C2PA + pixel features + SynthID (HK fraud scenario) |
| Smart Contract | `contracts/TrustLayerVerdicts.sol` | On-chain verdict anchoring (Consensus Layer) |
| Web Dashboard | `app.py` | Flask UI tying all pipelines together with live verdict ledger |

---

## Quick Start

```bash
# Install dependencies
pip install flask scikit-learn numpy requests pillow

# Run CLI demos (no server needed)
python oracle/anomaly_detector.py
python deepfake/content_classifier.py

# Launch web dashboard
python app.py
# → open http://localhost:5050
```

---

## Architecture Layer Mapping

```
INPUT (oracle feeds / media files / C2PA manifests)
        ↓
DATA LAYER     — multi-source ingestion, staleness check
        ↓
AI LAYER       — anomaly_detector.py / content_classifier.py
        ↓ (flagged)              ↓ (auto-pass, high confidence)
HUMAN LAYER    — jury escalation  →  skip to Consensus
        ↓
CONSENSUS      — TrustLayerVerdicts.sol (on-chain anchoring)
        ↓
INCENTIVE      — reputation scoring, staking rewards
        ↓
GOVERNANCE     — DAO / oversight council / incident runbooks
        ↑_______________________________________________|
              EU Compliance: AI Act · GDPR · DSA · NIST CSF 2.0
```

---

## Demo Scenarios

### Oracle Anomaly Detector
| Scenario | Input | Expected Output |
|---|---|---|
| Normal market | inject_spike=False | AUTO_PASS, ~99% confidence |
| Synthetix KRW attack | inject_spike=True, 10× spike | CIRCUIT_BREAK, escalate to human |

### AI Content Classifier
| Scenario | Filename hint | Expected Output |
|---|---|---|
| Authentic photo | `family_photo.jpg` | LIKELY AUTHENTIC, AUTO_PASS |
| HK deepfake fraud | `corporate_videocall_ai_generated.jpg` | LIKELY SYNTHETIC, CIRCUIT_BREAK |
| Stripped metadata | `document_stripped.jpg` | INCONCLUSIVE, ESCALATE_TO_HUMAN |

---

## Smart Contract (Consensus Layer)

`contracts/TrustLayerVerdicts.sol` — deploy on Hardhat testnet:

```bash
npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox
npx hardhat init
# copy TrustLayerVerdicts.sol to contracts/
npx hardhat compile
npx hardhat node          # local testnet
npx hardhat run scripts/deploy.js --network localhost
```

Key functions:
- `recordVerdict()` — anchors AI pipeline result on-chain
- `castJuryVote()` — human juror submits reputation-weighted vote
- `_resolveJury()` — auto-resolves when quorum reached
- `updateReputation()` — Incentive Layer: reward/slash jurors

---

## Tech Stack
- **Python 3.11** · Flask · scikit-learn · NumPy · Pillow
- **Solidity 0.8.20** · Hardhat · ethers.js
- **Standards**: C2PA 2.4 · SynthID (Google DeepMind) · NIST AI 100-4
- **References**: Mango Markets (CFTC 2023) · Synthetix (2019) · HK deepfake (SCMP 2024)

---

## Key Design Decisions
1. **No GPU required** — pixel feature extraction uses interpretable statistics, not a heavy vision model. Production would swap in a HuggingFace fine-tuned model.
2. **C2PA as primary signal** — matches our Part 1 finding: SynthID/Gemini verification returns results only when credentials are present and intact.
3. **Fail-safe escalation** — the classifier never auto-approves ambiguous results. Inconclusive always → human review.
4. **Evidence hash on every verdict** — SHA-256 of the full result payload, ready for keccak256 on-chain anchoring.

---

*TrustLayer EU · Group 1 · IE Risk & Fraud Course · June 2026*
