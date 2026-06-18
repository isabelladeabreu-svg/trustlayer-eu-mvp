# TrustLayer EU MVP V2

## 1. Project overview

TrustLayer EU is an oracle-integrity-first operational control MVP for Group 1:
Operational Risk and Technology Risk.

The demo shows how a financial platform can monitor external market data, detect
oracle integrity failures, trigger a control decision, escalate high-risk cases
to a human reviewer, and store a tamper-evident verdict trail.

The core story is:

```text
external data risk -> anomaly detection -> control decision -> human escalation -> verdict ledger
```

The synthetic-content module remains in the MVP, but it is positioned as a
secondary extension that demonstrates how the same layered architecture could be
used for other trust signals.

## 2. Why the MVP is oracle-first

For this phase, the strongest business-plan narrative is operational risk around
external data dependency. DeFi, payments, lending, settlement, and insurance
systems can fail when the data they rely on is manipulated, stale, unavailable,
or insufficiently redundant.

The MVP therefore makes the Oracle Integrity Monitor the primary dashboard
module. It focuses on:

- data integrity failure
- stale data
- reduced source redundancy
- low source diversity
- single-source dependency
- manipulation risk
- circuit-break and human escalation logic

## 3. Architecture overview

TrustLayer EU is presented as a layered trust-control platform:

1. Data layer: collects or simulates oracle feed inputs and content inputs.
2. AI/control layer: applies transparent anomaly or triage heuristics.
3. Human layer: lets a reviewer approve, reject, escalate, or annotate flagged cases.
4. Consensus/ledger layer: records evidence hashes and verdict metadata.

In this MVP, the ledger is in memory. The included Solidity contract shows the
intended production direction for on-chain anchoring.

## 4. Oracle Integrity Monitor

The Oracle Integrity Monitor is the primary module. It simulates ETH/USD feeds
from independent sources and evaluates whether the data is fresh, diverse,
redundant, and close to the market median.

Each oracle verdict includes:

- scenario name
- feeds used
- median price
- maximum deviation
- stale feeds
- active and healthy source counts
- source diversity score
- redundancy status
- risk level: LOW, MEDIUM, HIGH, or CRITICAL
- failure mode
- recommended control
- business impact hint
- system action
- confidence score
- evidence hash
- escalation flag
- layer path

## 5. Oracle scenarios

The dashboard includes five demo scenarios:

1. Normal market conditions: all sources are active, fresh, and close to median.
2. Manipulated spike: one feed is inflated to simulate price manipulation.
3. Stale feed: one source is active but older than the freshness threshold.
4. Reduced source redundancy / degraded fallback: multiple sources are unavailable.
5. Combined risk scenario: stale data, anomalous pricing, and source outage occur together.

The purpose is to show operational and technology risk controls, not only a
generic anomaly score.

## 6. Synthetic Content Triage Module

The Synthetic Content Triage Module is a secondary extension module. It remains
in the project to show that TrustLayer can reuse the same layered verification
pattern for other risk domains.

It checks:

- byte-statistics heuristics
- MVP-level C2PA-style provenance signals
- simulated SynthID-style watermark signals

This module is intentionally labeled as triage. It is not a benchmarked
production deepfake detector.

## 7. Human Review Flow

When a verdict is flagged, the dashboard creates a visible review case. A
simulated reviewer can submit:

- APPROVE
- ESCALATE
- REJECT
- ADD_NOTE

The review event is linked back to the original system verdict. The UI shows the
original system decision, whether human review happened, and the final reviewed
status.

## 8. Verdict Ledger

The MVP ledger is an in-memory audit log. It records:

- verdict id
- pipeline
- scenario name
- failure mode
- risk level
- recommended control
- action
- escalation status
- human review status
- evidence hash
- timestamp

Production would anchor evidence hashes on-chain through a contract such as
`contracts/TrustLayerVerdicts.sol`, while storing full evidence payloads in a
secure off-chain evidence store.

## 9. Governance / Threshold Configuration

The dashboard includes session-level governance settings:

- divergence threshold
- stale threshold
- minimum active sources
- circuit-break threshold
- minimum source diversity score

These settings are in memory for the MVP. They demonstrate that the control
policy is governed and adjustable rather than hidden in hardcoded logic.

## 10. What is simulated vs real in the MVP

Real in the MVP:

- Flask dashboard and API endpoints
- scenario-based oracle control pipeline
- explainable risk-level and control-decision logic
- in-memory verdict ledger
- linked human review records
- evidence hash generation
- session-level threshold updates

Simulated or simplified:

- external oracle feeds are simulated
- on-chain anchoring is represented by evidence hashes and the Solidity contract
- C2PA handling is an MVP metadata demonstration
- SynthID verification is simulated
- the content module uses heuristics, not a trained forensic model
- there is no authentication or production reviewer identity system

## 11. Limitations

This is a university MVP, not a production deployment. Main limitations:

- no real market-data API integrations
- no signed oracle messages
- no persistent database
- no authentication, authorization, or reviewer workflow controls
- no deployed blockchain anchoring
- no model validation or benchmark report for content triage
- no production incident management integration

The MVP is designed to be credible, explainable, and pitch-ready while staying
honest about what is simulated.

## 12. How to run the app

Run everything from PowerShell in this order:

1. Open the project folder:

```powershell
cd "C:\Users\alvde\Desktop\MASTER\TERM 3\RISK AND FRAUD ANALYTICS\trustlayer-eu-mvp"
```

2. Start the Flask app with the project virtual environment:

```powershell
.\RiskFraud\Scripts\python.exe app.py
```

3. When the terminal shows that Flask is running, open this URL in the browser:

```text
http://127.0.0.1:5050
```

4. To stop the app after the demo, return to the terminal and press `Ctrl + C`.

If port `5050` is already in use, run the app on another port:

```powershell
$env:TRUSTLAYER_PORT="5051"
.\RiskFraud\Scripts\python.exe app.py
```

Then open `http://127.0.0.1:5051`.

## 13. Demo walkthrough

For a 12-minute class demo:

1. Open the dashboard and explain that the primary use case is oracle integrity.
2. Run "Normal market conditions" and show LOW risk, proceed control, and ledger entry.
3. Run "Manipulated spike" and show price deviation, failure mode, circuit-break action, and evidence hash.
4. Run "Reduced source redundancy / degraded fallback" and explain fallback weakness.
5. Run "Combined risk scenario" and show why the case requires human review.
6. Use the Human Review Console to approve, reject, escalate, or annotate the flagged case.
7. Open the MVP Verdict Ledger and show the final reviewed status.
8. Adjust a governance threshold and rerun a scenario to show policy control.
9. Run the Synthetic Content Triage Module and explain it as an extensible secondary use case.
10. Close by explaining that production would use real feeds, signed data, persistent storage, and on-chain anchoring.

## 14. Possible next production steps

- integrate real oracle and market-data providers
- require signed source attestations
- persist verdicts and review events in a database
- deploy the verdict anchoring contract to a testnet
- add authentication and role-based review permissions
- connect to incident management tooling
- add model validation for any content verification pipeline
- implement provider-level service health monitoring
- add audit export for risk and compliance teams
