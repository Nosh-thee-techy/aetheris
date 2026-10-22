// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// The FloodTrigger views this escrow reads. State 3 is Finalized.
interface IFloodClaims {
    function ruleId() external view returns (bytes32);
    function thresholdsHash() external view returns (bytes32);
    function claimParts(bytes32 id) external view returns (bytes32 zoneId, bytes32 eventWeek, uint8 state);
}

/// Pays the beneficiaries committed before the season, and only after a
/// trigger is Finalized. The same zone-week-rule fingerprint can be paid once.
///
/// The funder can take back only what was never credited, and only after
/// seasonEnd. There is no admin withdrawal during the season. Payouts are
/// pull payments. This contract does not call M-PESA.
///
/// Unaudited. Testnet ETH only.
contract PayoutEscrow {
    uint8 public constant FINALIZED = 3;

    address public immutable trigger;
    address public immutable funder;
    uint64 public immutable seasonEnd;

    bool public policyLocked;
    bytes32 public policyHash;
    uint256 public deposited;
    uint256 public outstanding;

    struct Grant {
        address beneficiary;
        uint256 amount;
    }

    bytes32[] private _zones;
    mapping(bytes32 => Grant[]) private _grants;
    mapping(bytes32 => bool) private _seenZone;
    mapping(bytes32 => bool) public fingerprintPaid;
    mapping(address => uint256) public withdrawable;

    event PolicyCommitted(bytes32 policyHash);
    event Deposited(address indexed from, uint256 amount);
    event Released(bytes32 indexed triggerId, bytes32 indexed fingerprint, uint256 amount);
    event Reclaimed(uint256 amount);

    error NotFunder();
    error PolicyLocked();
    error PolicyOpen();
    error EmptyPolicy();
    error ZeroAddress();
    error ZeroAmount();
    error SeasonOver();
    error SeasonOpen();
    error NotFinalized();
    error AlreadyPaid();
    error FingerprintMismatch();
    error NoBeneficiary();
    error InsufficientPool();
    error NothingToWithdraw();
    error TransferFailed();

    /// `trigger` is the FloodTrigger that owns the claims. `seasonEnd` is unix time.
    constructor(address _trigger, address _funder, uint64 _seasonEnd) {
        if (_trigger == address(0) || _funder == address(0)) revert ZeroAddress();
        if (_seasonEnd <= block.timestamp) revert SeasonOver();
        trigger = _trigger;
        funder = _funder;
        seasonEnd = _seasonEnd;
    }

    /// Add one beneficiary for a zone. Reverts once the policy is committed.
    function addGrant(bytes32 zoneId, address beneficiary, uint256 amount) external {
        if (msg.sender != funder) revert NotFunder();
        if (policyLocked) revert PolicyLocked();
        if (beneficiary == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (!_seenZone[zoneId]) {
            _seenZone[zoneId] = true;
            _zones.push(zoneId);
        }
        _grants[zoneId].push(Grant(beneficiary, amount));
    }

    /// Freeze the table. Later grants revert. The hash is the commitment.
    function commitPolicy() external {
        if (msg.sender != funder) revert NotFunder();
        if (policyLocked) revert PolicyLocked();
        if (_zones.length == 0) revert EmptyPolicy();
        policyLocked = true;
        policyHash = _hashPolicy();
        emit PolicyCommitted(policyHash);
    }

    /// Fund the pool after the policy is locked, and only during the season.
    function deposit() external payable {
        if (!policyLocked) revert PolicyOpen();
        if (block.timestamp >= seasonEnd) revert SeasonOver();
        if (msg.value == 0) revert ZeroAmount();
        deposited += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    /// Pay the committed beneficiaries of the trigger's zone, once.
    /// Anyone may call this. A rejected or open trigger pays nothing.
    function release(bytes32 triggerId) external {
        if (!policyLocked) revert PolicyOpen();
        (bytes32 zoneId, bytes32 eventWeek, uint8 state) = IFloodClaims(trigger).claimParts(triggerId);
        if (state != FINALIZED) revert NotFinalized();

        bytes32 fingerprint = keccak256(
            abi.encode(zoneId, eventWeek, IFloodClaims(trigger).ruleId(), IFloodClaims(trigger).thresholdsHash())
        );
        if (fingerprint != triggerId) revert FingerprintMismatch();
        if (fingerprintPaid[fingerprint]) revert AlreadyPaid();

        Grant[] storage grants = _grants[zoneId];
        if (grants.length == 0) revert NoBeneficiary();

        uint256 total;
        for (uint256 i = 0; i < grants.length; i++) {
            total += grants[i].amount;
        }
        if (address(this).balance - outstanding < total) revert InsufficientPool();

        fingerprintPaid[fingerprint] = true;
        for (uint256 i = 0; i < grants.length; i++) {
            _credit(grants[i].beneficiary, grants[i].amount);
        }
        emit Released(triggerId, fingerprint, total);
    }

    /// Funder recovers only ether that was never credited to a beneficiary.
    function reclaim() external {
        if (msg.sender != funder) revert NotFunder();
        if (block.timestamp < seasonEnd) revert SeasonOpen();
        uint256 unspent = address(this).balance - outstanding;
        if (unspent == 0) revert NothingToWithdraw();
        _credit(funder, unspent);
        emit Reclaimed(unspent);
    }

    /// Beneficiary or funder pulls what release or reclaim credited.
    function withdraw() external {
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        withdrawable[msg.sender] = 0;
        outstanding -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    /// Grants currently committed for a zone. Empty before any addGrant.
    function grantsOf(bytes32 zoneId) external view returns (Grant[] memory) {
        return _grants[zoneId];
    }

    function _hashPolicy() internal view returns (bytes32) {
        bytes memory blob;
        for (uint256 z = 0; z < _zones.length; z++) {
            bytes32 zoneId = _zones[z];
            Grant[] storage grants = _grants[zoneId];
            for (uint256 i = 0; i < grants.length; i++) {
                blob = abi.encodePacked(blob, zoneId, grants[i].beneficiary, grants[i].amount);
            }
        }
        return keccak256(blob);
    }

    function _credit(address to, uint256 amount) internal {
        withdrawable[to] += amount;
        outstanding += amount;
    }
}
