// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IFloodResolver} from "./IFloodResolver.sol";

/// A flood trigger finalizes only when the radar attester and at least one
/// corroborator have signed, and a challenge either never arrives or expires
/// without the resolver rejecting it.
///
/// triggerId = keccak256(zoneId, eventWeek, ruleId, thresholdsHash).
/// Signing it means "this payout rule fired", not "I observed something".
/// Silence is a no. Each attester stores its own evidence hash. There is no
/// second boolean on the same id.
///
/// The demo resolver is one named key, not a vote. IFloodResolver is the
/// single function a later vote would call. The resolver cannot open a
/// trigger, add a signature, or change an evidence hash.
///
/// Unaudited. Testnet only.
contract FloodTrigger is IFloodResolver {
    uint256 public constant CHALLENGE_WINDOW = 24 hours;
    uint256 public constant RESOLVE_WINDOW = 48 hours;
    uint256 public constant CHALLENGE_STAKE = 0.01 ether;
    uint256 public constant ATTESTER_BOND = 0.01 ether;

    /// Why a trigger finalized. Rejected triggers do not use this.
    uint8 public constant REASON_UNCHALLENGED = 1;
    uint8 public constant REASON_UPHELD = 2;
    uint8 public constant REASON_EXPIRY = 3;

    bytes32 public immutable ruleId;
    bytes32 public immutable thresholdsHash;
    address public immutable resolver;
    address public immutable radarAttester;
    address public immutable pool;

    mapping(address => bool) public isCorroborator;

    enum State { None, Proposed, Challenged, Finalized, Rejected }

    struct Trigger {
        bytes32 zoneId;
        bytes32 eventWeek;
        uint64 windowStart;
        uint64 resolveDeadline;
        State state;
        address challenger;
        uint256 challengerStake;
        bool radarSigned;
        uint8 corroboratorCount;
        uint8 finalizationReason;
    }

    mapping(bytes32 => Trigger) private _triggers;
    mapping(bytes32 => address[]) private _signers;
    mapping(bytes32 => mapping(address => bool)) public hasSigned;
    mapping(bytes32 => mapping(address => bytes32)) public evidenceOf;
    mapping(bytes32 => mapping(address => uint256)) public bondOf;
    mapping(address => uint256) public withdrawable;

    event Attested(bytes32 indexed id, address indexed attester, bytes32 evidenceHash, bool radar);
    event WindowOpened(bytes32 indexed id, uint64 windowStart);
    event Challenged(bytes32 indexed id, address indexed challenger);
    event Finalized(bytes32 indexed id, uint8 reason);
    event Rejected(bytes32 indexed id, address indexed challenger);

    error ZeroAddress();
    error ResolverIsAttester();
    error RadarIsCorroborator();
    error NoCorroborator();
    error DuplicateCorroborator();
    error BadWindow();
    error EmptyRule();
    error EmptyEvidence();
    error NotAttester();
    error AlreadySigned();
    error Closed();
    error BondRequired();
    error NotChallengeable();
    error ChallengeWindowClosed();
    error WrongStake();
    error NotResolver();
    error NoChallenge();
    error ResolveWindowOver();
    error ResolveWindowOpen();
    error NotReady();
    error ChallengeWindowOpen();
    error NothingToWithdraw();
    error TransferFailed();

    /// Binds the frozen rule. Reverts if the resolver is also an attester.
    constructor(
        bytes32 _ruleId,
        bytes32 _thresholdsHash,
        address _resolver,
        address _radarAttester,
        address[] memory corroborators,
        address _pool
    ) {
        if (_resolver == address(0) || _radarAttester == address(0) || _pool == address(0)) {
            revert ZeroAddress();
        }
        if (_ruleId == bytes32(0) || _thresholdsHash == bytes32(0)) revert EmptyRule();
        if (corroborators.length == 0) revert NoCorroborator();

        for (uint256 i = 0; i < corroborators.length; i++) {
            address corroborator = corroborators[i];
            if (corroborator == address(0)) revert ZeroAddress();
            if (corroborator == _radarAttester) revert RadarIsCorroborator();
            if (corroborator == _resolver || _radarAttester == _resolver) revert ResolverIsAttester();
            if (isCorroborator[corroborator]) revert DuplicateCorroborator();
            isCorroborator[corroborator] = true;
        }

        ruleId = _ruleId;
        thresholdsHash = _thresholdsHash;
        resolver = _resolver;
        radarAttester = _radarAttester;
        pool = _pool;
    }

    /// The id a signature commits to. Same bytes the escrow uses as a fingerprint.
    function computeId(bytes32 zoneId, bytes32 eventWeek) public view returns (bytes32) {
        return keccak256(abi.encode(zoneId, eventWeek, ruleId, thresholdsHash));
    }

    /// Full trigger record. Empty id returns the zero struct.
    function getTrigger(bytes32 id) external view returns (Trigger memory) {
        return _triggers[id];
    }

    /// The parts the escrow needs, without taking a dependency on Trigger layout.
    function claimParts(bytes32 id) external view returns (bytes32 zoneId, bytes32 eventWeek, uint8 state) {
        Trigger storage t = _triggers[id];
        return (t.zoneId, t.eventWeek, uint8(t.state));
    }

    /// Addresses that posted a bond on this id, in the order they signed.
    function signersOf(bytes32 id) external view returns (address[] memory) {
        return _signers[id];
    }

    /// True only after radar and at least one corroborator have signed.
    function quorumReached(bytes32 id) public view returns (bool) {
        Trigger storage t = _triggers[id];
        return t.radarSigned && t.corroboratorCount >= 1;
    }

    /// An attester posts a bond and evidence that this frozen rule fired.
    /// A second signature from the same attester reverts, whatever the evidence.
    function attest(bytes32 zoneId, bytes32 eventWeek, bytes32 evidenceHash) external payable {
        if (msg.value != ATTESTER_BOND) revert BondRequired();
        if (evidenceHash == bytes32(0)) revert EmptyEvidence();
        if (eventWeek == bytes32(0)) revert BadWindow();

        bool radar = msg.sender == radarAttester;
        if (!radar && !isCorroborator[msg.sender]) revert NotAttester();

        bytes32 id = computeId(zoneId, eventWeek);
        Trigger storage t = _triggers[id];
        if (t.state != State.None && t.state != State.Proposed) revert Closed();
        if (hasSigned[id][msg.sender]) revert AlreadySigned();

        if (t.state == State.None) {
            t.state = State.Proposed;
            t.zoneId = zoneId;
            t.eventWeek = eventWeek;
        }

        hasSigned[id][msg.sender] = true;
        evidenceOf[id][msg.sender] = evidenceHash;
        bondOf[id][msg.sender] = msg.value;
        _signers[id].push(msg.sender);

        if (radar) t.radarSigned = true;
        else t.corroboratorCount += 1;

        emit Attested(id, msg.sender, evidenceHash, radar);

        if (t.windowStart == 0 && t.radarSigned && t.corroboratorCount >= 1) {
            t.windowStart = uint64(block.timestamp);
            emit WindowOpened(id, t.windowStart);
        }
    }

    /// Stake during the open window to freeze a trigger that has reached quorum.
    function challenge(bytes32 id) external payable {
        Trigger storage t = _triggers[id];
        if (t.state != State.Proposed || !quorumReached(id)) revert NotChallengeable();
        if (block.timestamp >= uint256(t.windowStart) + CHALLENGE_WINDOW) revert ChallengeWindowClosed();
        if (msg.value != CHALLENGE_STAKE) revert WrongStake();

        t.state = State.Challenged;
        t.challenger = msg.sender;
        t.challengerStake = msg.value;
        t.resolveDeadline = uint64(block.timestamp) + uint64(RESOLVE_WINDOW);
        emit Challenged(id, msg.sender);
    }

    /// Resolver upholds the attesters or rejects the trigger. No other outcome.
    function resolve(bytes32 id, bool upheld) external {
        if (msg.sender != resolver) revert NotResolver();
        Trigger storage t = _triggers[id];
        if (t.state != State.Challenged) revert NoChallenge();
        if (block.timestamp >= uint256(t.resolveDeadline)) revert ResolveWindowOver();

        if (upheld) {
            _finalize(id, REASON_UPHELD);
            _credit(pool, t.challengerStake);
            t.challengerStake = 0;
            _refundBonds(id);
        } else {
            t.state = State.Rejected;
            uint256 payout = t.challengerStake + _bondTotal(id);
            t.challengerStake = 0;
            _clearBonds(id);
            _credit(t.challenger, payout);
            emit Rejected(id, t.challenger);
        }
    }

    /// A silent resolver cannot hold the trigger. Expiry finalizes and returns the stake.
    function expire(bytes32 id) external {
        Trigger storage t = _triggers[id];
        if (t.state != State.Challenged) revert NoChallenge();
        if (block.timestamp < uint256(t.resolveDeadline)) revert ResolveWindowOpen();

        address challenger = t.challenger;
        uint256 stake = t.challengerStake;
        t.challengerStake = 0;
        _finalize(id, REASON_EXPIRY);
        _credit(challenger, stake);
        _refundBonds(id);
    }

    /// Finalize after the challenge window when nobody challenged.
    function finalize(bytes32 id) external {
        Trigger storage t = _triggers[id];
        if (t.state != State.Proposed || !quorumReached(id)) revert NotReady();
        if (block.timestamp < uint256(t.windowStart) + CHALLENGE_WINDOW) revert ChallengeWindowOpen();

        _finalize(id, REASON_UNCHALLENGED);
        _refundBonds(id);
    }

    /// Pull a refunded bond, a returned stake, or a slashed bond.
    function withdraw() external {
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        withdrawable[msg.sender] = 0;
        (bool ok,) = msg.sender.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    /// Move a trigger to Finalized and record why. Does not move ether.
    function _finalize(bytes32 id, uint8 reason) internal {
        Trigger storage t = _triggers[id];
        t.state = State.Finalized;
        t.finalizationReason = reason;
        emit Finalized(id, reason);
    }

    /// Return every attester bond for this id through the pull balance.
    function _refundBonds(bytes32 id) internal {
        address[] storage signers = _signers[id];
        for (uint256 i = 0; i < signers.length; i++) {
            address signer = signers[i];
            uint256 bond = bondOf[id][signer];
            if (bond == 0) continue;
            bondOf[id][signer] = 0;
            _credit(signer, bond);
        }
    }

    /// Drop bond balances without paying them. Used when the challenger is paid.
    function _clearBonds(bytes32 id) internal {
        address[] storage signers = _signers[id];
        for (uint256 i = 0; i < signers.length; i++) {
            bondOf[id][signers[i]] = 0;
        }
    }

    /// Sum of bonds still recorded on this id.
    function _bondTotal(bytes32 id) internal view returns (uint256 total) {
        address[] storage signers = _signers[id];
        for (uint256 i = 0; i < signers.length; i++) {
            total += bondOf[id][signers[i]];
        }
    }

    /// Add to a pull-payment balance. Zero is a no-op.
    function _credit(address to, uint256 amount) internal {
        if (amount == 0) return;
        withdrawable[to] += amount;
    }
}
