// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {FloodTrigger} from "../src/FloodTrigger.sol";
import {PayoutEscrow} from "../src/PayoutEscrow.sol";

/// Deploy only after config/rule.yaml is frozen.
/// RULE_ID is keccak256 of the rule_id string.
/// THRESHOLDS_HASH is keccak256 of the rule file bytes.
/// SEASON_END is a unix time after which the funder may reclaim unspent escrow.
contract Deploy is Script {
    function run() external returns (FloodTrigger trigger, PayoutEscrow escrow) {
        bytes32 ruleId = vm.envBytes32("RULE_ID");
        bytes32 thresholdsHash = vm.envBytes32("THRESHOLDS_HASH");
        address resolver = vm.envAddress("RESOLVER");
        address radar = vm.envAddress("RADAR_ATTESTER");
        address rainfall = vm.envAddress("RAINFALL_ATTESTER");
        address pool = vm.envAddress("POOL");
        address funder = vm.envAddress("FUNDER");
        uint64 seasonEnd = uint64(vm.envUint("SEASON_END"));

        address[] memory corroborators = new address[](1);
        corroborators[0] = rainfall;

        vm.startBroadcast();
        trigger = new FloodTrigger(ruleId, thresholdsHash, resolver, radar, corroborators, pool);
        escrow = new PayoutEscrow(address(trigger), funder, seasonEnd);
        vm.stopBroadcast();
    }
}
