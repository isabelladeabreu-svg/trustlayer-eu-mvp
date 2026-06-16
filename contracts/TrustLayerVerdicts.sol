// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * TrustLayer EU — On-Chain Verdict Anchoring
 * Consensus Layer MVP
 *
 * Records tamper-proof verification verdicts for:
 *   - Oracle anomaly check results
 *   - AI content classification results
 *   - Human jury votes
 *
 * Deployed on Hardhat local testnet for MVP demo.
 * Production: Polygon PoS or Ethereum L2 (EU-region nodes).
 */
contract TrustLayerVerdicts {

    // ── Enums ──────────────────────────────────────────────────────────────
    enum PipelineType  { ORACLE_ANOMALY, CONTENT_CLASSIFIER }
    enum ActionType    { AUTO_PASS, ALERT, ESCALATE_TO_HUMAN, CIRCUIT_BREAK }
    enum JuryDecision  { PENDING, AUTHENTIC, SYNTHETIC, INCONCLUSIVE }

    // ── Structs ────────────────────────────────────────────────────────────
    struct Verdict {
        uint256 id;
        PipelineType pipeline;
        ActionType   action;
        bytes32      evidenceHash;    // keccak256 of full result payload
        uint8        confidenceScore; // 0–100
        uint256      timestamp;
        address      submittedBy;
        bool         juryRequired;
        JuryDecision juryDecision;
        uint256      juryResolvedAt;
        string       memo;            // short human-readable summary
    }

    struct JuryVote {
        address juror;
        JuryDecision vote;
        uint256 reputationScore;      // juror's current reputation (0–100)
        uint256 timestamp;
        string  rationale;
    }

    // ── State ──────────────────────────────────────────────────────────────
    address public owner;
    uint256 public verdictCount;
    uint8   public constant QUORUM_REQUIRED = 3;   // min jury votes for resolution

    mapping(uint256 => Verdict)       public verdicts;
    mapping(uint256 => JuryVote[])    public juryVotes;
    mapping(address => uint256)       public jurorReputation;
    mapping(address => bool)          public authorisedSubmitters;
    mapping(address => bool)          public authorisedJurors;

    // ── Events ─────────────────────────────────────────────────────────────
    event VerdictRecorded(
        uint256 indexed id,
        PipelineType   pipeline,
        ActionType     action,
        bytes32        evidenceHash,
        uint8          confidenceScore,
        bool           juryRequired
    );

    event JuryVoteCast(
        uint256 indexed verdictId,
        address indexed juror,
        JuryDecision    vote,
        uint256         reputationScore
    );

    event JuryResolved(
        uint256 indexed verdictId,
        JuryDecision    finalDecision,
        uint256         resolvedAt
    );

    event ReputationUpdated(
        address indexed juror,
        uint256 oldScore,
        uint256 newScore
    );

    // ── Modifiers ──────────────────────────────────────────────────────────
    modifier onlyOwner()      { require(msg.sender == owner,                    "Not owner");     _; }
    modifier onlySubmitter()  { require(authorisedSubmitters[msg.sender],       "Not submitter"); _; }
    modifier onlyJuror()      { require(authorisedJurors[msg.sender],           "Not juror");     _; }

    // ── Constructor ────────────────────────────────────────────────────────
    constructor() {
        owner = msg.sender;
        authorisedSubmitters[msg.sender] = true;
        // Seed demo jurors with initial reputation
        authorisedJurors[msg.sender] = true;
        jurorReputation[msg.sender] = 75;
    }

    // ── Admin ──────────────────────────────────────────────────────────────
    function addSubmitter(address _addr) external onlyOwner {
        authorisedSubmitters[_addr] = true;
    }

    function addJuror(address _addr, uint256 _initialRep) external onlyOwner {
        authorisedJurors[_addr] = true;
        jurorReputation[_addr] = _initialRep;
    }

    // ── Core: record a verdict from AI pipeline ────────────────────────────
    function recordVerdict(
        PipelineType _pipeline,
        ActionType   _action,
        bytes32      _evidenceHash,
        uint8        _confidenceScore,
        string calldata _memo
    ) external onlySubmitter returns (uint256 verdictId) {
        require(_confidenceScore <= 100, "Score must be 0-100");

        verdictId = ++verdictCount;
        bool juryNeeded = (
            _action == ActionType.ESCALATE_TO_HUMAN ||
            _action == ActionType.CIRCUIT_BREAK
        );

        verdicts[verdictId] = Verdict({
            id:              verdictId,
            pipeline:        _pipeline,
            action:          _action,
            evidenceHash:    _evidenceHash,
            confidenceScore: _confidenceScore,
            timestamp:       block.timestamp,
            submittedBy:     msg.sender,
            juryRequired:    juryNeeded,
            juryDecision:    juryNeeded ? JuryDecision.PENDING : JuryDecision.INCONCLUSIVE,
            juryResolvedAt:  0,
            memo:            _memo
        });

        emit VerdictRecorded(
            verdictId, _pipeline, _action, _evidenceHash, _confidenceScore, juryNeeded
        );
    }

    // ── Human Layer: cast a jury vote ──────────────────────────────────────
    function castJuryVote(
        uint256      _verdictId,
        JuryDecision _vote,
        string calldata _rationale
    ) external onlyJuror {
        Verdict storage v = verdicts[_verdictId];
        require(v.id != 0,                           "Verdict not found");
        require(v.juryRequired,                      "No jury needed");
        require(v.juryDecision == JuryDecision.PENDING, "Already resolved");
        require(_vote != JuryDecision.PENDING,       "Invalid vote");

        // Prevent duplicate votes from same juror
        JuryVote[] storage votes = juryVotes[_verdictId];
        for (uint i = 0; i < votes.length; i++) {
            require(votes[i].juror != msg.sender, "Already voted");
        }

        uint256 rep = jurorReputation[msg.sender];
        votes.push(JuryVote({
            juror:           msg.sender,
            vote:            _vote,
            reputationScore: rep,
            timestamp:       block.timestamp,
            rationale:       _rationale
        }));

        emit JuryVoteCast(_verdictId, msg.sender, _vote, rep);

        // Check if quorum reached and auto-resolve
        if (votes.length >= QUORUM_REQUIRED) {
            _resolveJury(_verdictId);
        }
    }

    // ── Internal: reputation-weighted jury resolution ──────────────────────
    function _resolveJury(uint256 _verdictId) internal {
        JuryVote[] storage votes = juryVotes[_verdictId];

        uint256 syntheticWeight  = 0;
        uint256 authenticWeight  = 0;
        uint256 inconclusiveWeight = 0;

        for (uint i = 0; i < votes.length; i++) {
            uint256 w = votes[i].reputationScore; // weight by reputation
            if (votes[i].vote == JuryDecision.SYNTHETIC)    syntheticWeight  += w;
            if (votes[i].vote == JuryDecision.AUTHENTIC)    authenticWeight  += w;
            if (votes[i].vote == JuryDecision.INCONCLUSIVE) inconclusiveWeight += w;
        }

        JuryDecision decision;
        if (syntheticWeight > authenticWeight && syntheticWeight > inconclusiveWeight) {
            decision = JuryDecision.SYNTHETIC;
        } else if (authenticWeight > syntheticWeight && authenticWeight > inconclusiveWeight) {
            decision = JuryDecision.AUTHENTIC;
        } else {
            decision = JuryDecision.INCONCLUSIVE;
        }

        verdicts[_verdictId].juryDecision   = decision;
        verdicts[_verdictId].juryResolvedAt = block.timestamp;

        emit JuryResolved(_verdictId, decision, block.timestamp);
    }

    // ── Incentive Layer: update juror reputation ───────────────────────────
    function updateReputation(
        address _juror,
        bool    _accurate,        // did juror vote correctly?
        uint256 _delta            // how much to adjust (1–10)
    ) external onlyOwner {
        require(authorisedJurors[_juror], "Not a juror");
        uint256 old = jurorReputation[_juror];
        uint256 newRep;
        if (_accurate) {
            newRep = old + _delta > 100 ? 100 : old + _delta;
        } else {
            newRep = old < _delta ? 0 : old - _delta;
        }
        jurorReputation[_juror] = newRep;
        emit ReputationUpdated(_juror, old, newRep);
    }

    // ── View functions ─────────────────────────────────────────────────────
    function getVerdict(uint256 _id) external view returns (Verdict memory) {
        require(verdicts[_id].id != 0, "Not found");
        return verdicts[_id];
    }

    function getJuryVotes(uint256 _id) external view returns (JuryVote[] memory) {
        return juryVotes[_id];
    }

    function getVerdictCount() external view returns (uint256) {
        return verdictCount;
    }
}
