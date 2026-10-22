// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {FloodTrigger} from "../src/FloodTrigger.sol";

contract FloodTriggerTest is Test {
    bytes32 constant RULE_ID = keccak256("nyando-open-water-v1");
    bytes32 constant OTHER_RULE = keccak256("other-rule");
    bytes32 constant THRESHOLDS = keccak256("thresholds-v1");
    bytes32 constant OTHER_THRESHOLDS = keccak256("other-thresholds");
    bytes32 constant ZONE = keccak256("nyando-ward-1");
    bytes32 constant WEEK = keccak256("2024-05-04/2024-05-06");
    bytes32 constant EVIDENCE = keccak256("scene");
    bytes32 constant RAIN_EVIDENCE = keccak256("chirps");

    FloodTrigger trigger;
    address resolver = makeAddr("resolver");
    address radar = makeAddr("radar");
    address rainfall = makeAddr("rainfall");
    address pool = makeAddr("pool");
    address stranger = makeAddr("stranger");
    uint256 bond;
    uint256 stake;

    function setUp() public {
        address[] memory corroborators = new address[](1);
        corroborators[0] = rainfall;
        trigger = new FloodTrigger(RULE_ID, THRESHOLDS, resolver, radar, corroborators, pool);
        bond = trigger.ATTESTER_BOND();
        stake = trigger.CHALLENGE_STAKE();
        vm.deal(radar, 1 ether);
        vm.deal(rainfall, 1 ether);
        vm.deal(stranger, 1 ether);
        vm.deal(resolver, 1 ether);
    }

    function _attestRadar() internal {
        vm.prank(radar);
        trigger.attest{value: bond}(ZONE, WEEK, EVIDENCE);
    }

    function _attestRain() internal {
        vm.prank(rainfall);
        trigger.attest{value: bond}(ZONE, WEEK, RAIN_EVIDENCE);
    }

    function _openWindow() internal returns (bytes32 id) {
        _attestRadar();
        _attestRain();
        id = trigger.computeId(ZONE, WEEK);
    }

    function test_radarAloneDoesNotOpenWindow() public {
        _attestRadar();
        bytes32 id = trigger.computeId(ZONE, WEEK);
        assertFalse(trigger.quorumReached(id));
        FloodTrigger.Trigger memory t = trigger.getTrigger(id);
        assertEq(t.windowStart, 0);
        assertEq(uint256(t.state), uint256(FloodTrigger.State.Proposed));
    }

    function test_rainfallAloneDoesNotOpenWindow() public {
        _attestRain();
        bytes32 id = trigger.computeId(ZONE, WEEK);
        assertFalse(trigger.quorumReached(id));
        assertEq(trigger.getTrigger(id).windowStart, 0);
    }

    function test_radarPlusRainfallOpensWindow() public {
        bytes32 id = _openWindow();
        assertTrue(trigger.quorumReached(id));
        FloodTrigger.Trigger memory t = trigger.getTrigger(id);
        assertGt(t.windowStart, 0);
        assertEq(t.corroboratorCount, 1);
        assertTrue(t.radarSigned);
        assertEq(trigger.evidenceOf(id, radar), EVIDENCE);
        assertEq(trigger.evidenceOf(id, rainfall), RAIN_EVIDENCE);
    }

    function test_idChangesWithRuleHash() public {
        address[] memory corroborators = new address[](1);
        corroborators[0] = rainfall;
        FloodTrigger other = new FloodTrigger(RULE_ID, OTHER_THRESHOLDS, resolver, radar, corroborators, pool);
        assertTrue(trigger.computeId(ZONE, WEEK) != other.computeId(ZONE, WEEK));
    }

    function test_strangerCannotAttest() public {
        vm.prank(stranger);
        vm.expectRevert(FloodTrigger.NotAttester.selector);
        trigger.attest{value: bond}(ZONE, WEEK, EVIDENCE);
    }

    function test_resolverCannotAttest() public {
        vm.prank(resolver);
        vm.expectRevert(FloodTrigger.NotAttester.selector);
        trigger.attest{value: bond}(ZONE, WEEK, EVIDENCE);
    }

    function test_wrongBondReverts() public {
        vm.prank(radar);
        vm.expectRevert(FloodTrigger.BondRequired.selector);
        trigger.attest{value: 1}(ZONE, WEEK, EVIDENCE);
    }

    function test_cannotDoubleSign() public {
        _attestRadar();
        vm.prank(radar);
        vm.expectRevert(FloodTrigger.AlreadySigned.selector);
        trigger.attest{value: bond}(ZONE, WEEK, EVIDENCE);
    }

    function test_conflictingClaimIsBlocked() public {
        _attestRadar();
        vm.prank(radar);
        vm.expectRevert(FloodTrigger.AlreadySigned.selector);
        trigger.attest{value: bond}(ZONE, WEEK, keccak256("other-scene"));
    }

    function test_idChangesWithRuleId() public {
        address[] memory corroborators = new address[](1);
        corroborators[0] = rainfall;
        FloodTrigger other = new FloodTrigger(OTHER_RULE, THRESHOLDS, resolver, radar, corroborators, pool);
        assertTrue(trigger.computeId(ZONE, WEEK) != other.computeId(ZONE, WEEK));
    }

    function test_constructorRejectsResolverAsAttester() public {
        address[] memory corroborators = new address[](1);
        corroborators[0] = rainfall;
        vm.expectRevert(FloodTrigger.ResolverIsAttester.selector);
        new FloodTrigger(RULE_ID, THRESHOLDS, radar, radar, corroborators, pool);
    }

    function test_constructorRejectsRadarAsCorroborator() public {
        address[] memory corroborators = new address[](1);
        corroborators[0] = radar;
        vm.expectRevert(FloodTrigger.RadarIsCorroborator.selector);
        new FloodTrigger(RULE_ID, THRESHOLDS, resolver, radar, corroborators, pool);
    }

    function test_unchallengedFinalizeReturnsBonds() public {
        bytes32 id = _openWindow();
        vm.warp(uint256(trigger.getTrigger(id).windowStart) + trigger.CHALLENGE_WINDOW());
        trigger.finalize(id);

        FloodTrigger.Trigger memory t = trigger.getTrigger(id);
        assertEq(uint256(t.state), uint256(FloodTrigger.State.Finalized));
        assertEq(t.finalizationReason, trigger.REASON_UNCHALLENGED());

        vm.prank(radar);
        trigger.withdraw();
        assertEq(radar.balance, 1 ether);
    }

    function test_cannotFinalizeDuringWindow() public {
        bytes32 id = _openWindow();
        vm.expectRevert(FloodTrigger.ChallengeWindowOpen.selector);
        trigger.finalize(id);
    }

    function test_upholdSlashesChallengerAndReturnsBonds() public {
        bytes32 id = _openWindow();
        vm.prank(stranger);
        trigger.challenge{value: stake}(id);

        vm.prank(resolver);
        trigger.resolve(id, true);

        assertEq(uint256(trigger.getTrigger(id).state), uint256(FloodTrigger.State.Finalized));
        assertEq(trigger.getTrigger(id).finalizationReason, trigger.REASON_UPHELD());
        assertEq(trigger.withdrawable(pool), trigger.CHALLENGE_STAKE());
        assertEq(trigger.withdrawable(radar), trigger.ATTESTER_BOND());
        assertEq(trigger.withdrawable(stranger), 0);
    }

    function test_rejectPaysBondsToChallenger() public {
        bytes32 id = _openWindow();
        vm.prank(stranger);
        trigger.challenge{value: stake}(id);

        vm.prank(resolver);
        trigger.resolve(id, false);

        assertEq(uint256(trigger.getTrigger(id).state), uint256(FloodTrigger.State.Rejected));
        assertEq(trigger.withdrawable(stranger), trigger.CHALLENGE_STAKE() + 2 * trigger.ATTESTER_BOND());
        assertEq(trigger.withdrawable(radar), 0);
        assertEq(trigger.withdrawable(rainfall), 0);
        assertEq(trigger.withdrawable(pool), 0);
    }

    function test_expiryFinalizesAndReturnsStake() public {
        bytes32 id = _openWindow();
        vm.prank(stranger);
        trigger.challenge{value: stake}(id);

        uint64 deadline = trigger.getTrigger(id).resolveDeadline;
        vm.warp(deadline);
        trigger.expire(id);

        FloodTrigger.Trigger memory t = trigger.getTrigger(id);
        assertEq(uint256(t.state), uint256(FloodTrigger.State.Finalized));
        assertEq(t.finalizationReason, trigger.REASON_EXPIRY());
        assertEq(trigger.withdrawable(stranger), trigger.CHALLENGE_STAKE());
        assertEq(trigger.withdrawable(radar), trigger.ATTESTER_BOND());
        assertEq(trigger.withdrawable(pool), 0);
    }

    function test_resolverCannotResolveAfterDeadline() public {
        bytes32 id = _openWindow();
        vm.prank(stranger);
        trigger.challenge{value: stake}(id);
        vm.warp(trigger.getTrigger(id).resolveDeadline);

        vm.prank(resolver);
        vm.expectRevert(FloodTrigger.ResolveWindowOver.selector);
        trigger.resolve(id, false);
    }

    function test_cannotExpireBeforeDeadline() public {
        bytes32 id = _openWindow();
        vm.prank(stranger);
        trigger.challenge{value: stake}(id);
        vm.expectRevert(FloodTrigger.ResolveWindowOpen.selector);
        trigger.expire(id);
    }

    function test_rainfallCannotBeChallengedAlone() public {
        _attestRain();
        bytes32 id = trigger.computeId(ZONE, WEEK);
        vm.prank(stranger);
        vm.expectRevert(FloodTrigger.NotChallengeable.selector);
        trigger.challenge{value: stake}(id);
    }

    function test_laterSignatureDoesNotResetWindow() public {
        address ground = makeAddr("ground");
        address[] memory corroborators = new address[](2);
        corroborators[0] = rainfall;
        corroborators[1] = ground;
        FloodTrigger wider = new FloodTrigger(RULE_ID, THRESHOLDS, resolver, radar, corroborators, pool);
        vm.deal(radar, 1 ether);
        vm.deal(rainfall, 1 ether);
        vm.deal(ground, 1 ether);
        uint256 widerBond = wider.ATTESTER_BOND();

        vm.prank(radar);
        wider.attest{value: widerBond}(ZONE, WEEK, EVIDENCE);
        vm.prank(rainfall);
        wider.attest{value: widerBond}(ZONE, WEEK, RAIN_EVIDENCE);

        bytes32 id = wider.computeId(ZONE, WEEK);
        uint64 opened = wider.getTrigger(id).windowStart;

        vm.warp(block.timestamp + 1 hours);
        vm.prank(ground);
        wider.attest{value: widerBond}(ZONE, WEEK, keccak256("ground"));

        assertEq(wider.getTrigger(id).windowStart, opened);
        assertEq(wider.getTrigger(id).corroboratorCount, 2);
    }

    function test_resolverCannotChangeEvidence() public {
        bytes32 id = _openWindow();
        vm.prank(stranger);
        trigger.challenge{value: stake}(id);
        vm.prank(resolver);
        trigger.resolve(id, true);
        assertEq(trigger.evidenceOf(id, radar), EVIDENCE);
        assertEq(trigger.evidenceOf(id, rainfall), RAIN_EVIDENCE);
    }
}
