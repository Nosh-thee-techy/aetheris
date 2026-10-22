// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {FloodTrigger} from "../src/FloodTrigger.sol";
import {PayoutEscrow} from "../src/PayoutEscrow.sol";

/// Escrow pays only a Finalized trigger, once, to the committed beneficiary.
contract PayoutEscrowTest is Test {
    bytes32 constant RULE_ID = keccak256("nyando-open-water-v1");
    bytes32 constant THRESHOLDS = keccak256("thresholds-v1");
    bytes32 constant ZONE = keccak256("kabonyo-kanyagwal");
    bytes32 constant OTHER_ZONE = keccak256("ahero");
    bytes32 constant WEEK = keccak256("2024-05-04/2024-05-06");
    bytes32 constant EVIDENCE = keccak256("scene");
    bytes32 constant RAIN_EVIDENCE = keccak256("chirps");

    FloodTrigger trigger;
    PayoutEscrow escrow;
    address funder = makeAddr("funder");
    address resolver = makeAddr("resolver");
    address radar = makeAddr("radar");
    address rainfall = makeAddr("rainfall");
    address pool = makeAddr("pool");
    address beneficiary = makeAddr("beneficiary");
    address otherBeneficiary = makeAddr("other");
    uint256 bond;
    uint256 grantAmount = 0.05 ether;

    function setUp() public {
        address[] memory corroborators = new address[](1);
        corroborators[0] = rainfall;
        trigger = new FloodTrigger(RULE_ID, THRESHOLDS, resolver, radar, corroborators, pool);
        escrow = new PayoutEscrow(address(trigger), funder, uint64(block.timestamp + 30 days));
        bond = trigger.ATTESTER_BOND();
        vm.deal(radar, 1 ether);
        vm.deal(rainfall, 1 ether);
        vm.deal(funder, 1 ether);
        vm.prank(funder);
        escrow.addGrant(ZONE, beneficiary, grantAmount);
        vm.prank(funder);
        escrow.addGrant(OTHER_ZONE, otherBeneficiary, grantAmount);
        vm.prank(funder);
        escrow.commitPolicy();
        vm.prank(funder);
        escrow.deposit{value: 0.2 ether}();
    }

    function _finalize() internal returns (bytes32 id) {
        vm.prank(radar);
        trigger.attest{value: bond}(ZONE, WEEK, EVIDENCE);
        vm.prank(rainfall);
        trigger.attest{value: bond}(ZONE, WEEK, RAIN_EVIDENCE);
        id = trigger.computeId(ZONE, WEEK);
        vm.warp(uint256(trigger.getTrigger(id).windowStart) + trigger.CHALLENGE_WINDOW());
        trigger.finalize(id);
    }

    function test_releaseBeforeFinalizedReverts() public {
        vm.prank(radar);
        trigger.attest{value: bond}(ZONE, WEEK, EVIDENCE);
        vm.prank(rainfall);
        trigger.attest{value: bond}(ZONE, WEEK, RAIN_EVIDENCE);
        bytes32 id = trigger.computeId(ZONE, WEEK);
        vm.expectRevert(PayoutEscrow.NotFinalized.selector);
        escrow.release(id);
    }

    function test_releasePaysTheCommittedBeneficiaryOnce() public {
        bytes32 id = _finalize();
        escrow.release(id);
        assertEq(escrow.withdrawable(beneficiary), grantAmount);
        assertEq(escrow.withdrawable(otherBeneficiary), 0);

        vm.prank(beneficiary);
        escrow.withdraw();
        assertEq(beneficiary.balance, grantAmount);

        vm.expectRevert(PayoutEscrow.AlreadyPaid.selector);
        escrow.release(id);
    }

    function test_wrongBeneficiaryCannotBePaid() public {
        bytes32 id = _finalize();
        escrow.release(id);
        assertEq(escrow.withdrawable(otherBeneficiary), 0);
        vm.prank(otherBeneficiary);
        vm.expectRevert(PayoutEscrow.NothingToWithdraw.selector);
        escrow.withdraw();
    }

    function test_rejectedTriggerReleasesNothing() public {
        vm.prank(radar);
        trigger.attest{value: bond}(ZONE, WEEK, EVIDENCE);
        vm.prank(rainfall);
        trigger.attest{value: bond}(ZONE, WEEK, RAIN_EVIDENCE);
        bytes32 id = trigger.computeId(ZONE, WEEK);
        vm.deal(address(this), 1 ether);
        trigger.challenge{value: trigger.CHALLENGE_STAKE()}(id);
        vm.prank(resolver);
        trigger.resolve(id, false);

        vm.expectRevert(PayoutEscrow.NotFinalized.selector);
        escrow.release(id);
        assertEq(escrow.withdrawable(beneficiary), 0);
    }

    function test_funderCannotWithdrawMidSeason() public {
        uint256 before = address(escrow).balance;
        vm.prank(funder);
        vm.expectRevert(PayoutEscrow.SeasonOpen.selector);
        escrow.reclaim();
        assertEq(address(escrow).balance, before);

        vm.prank(funder);
        vm.expectRevert(PayoutEscrow.PolicyLocked.selector);
        escrow.addGrant(ZONE, funder, 1);
    }

    function test_funderReclaimsUnspentAfterSeasonEnd() public {
        bytes32 id = _finalize();
        escrow.release(id);
        vm.warp(escrow.seasonEnd());
        vm.prank(funder);
        escrow.reclaim();
        uint256 unspent = 0.2 ether - grantAmount;
        assertEq(escrow.withdrawable(funder), unspent);
        vm.prank(funder);
        escrow.withdraw();
        assertEq(funder.balance, 1 ether - 0.2 ether + unspent);
    }
}
