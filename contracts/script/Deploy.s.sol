// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {FloodTrigger} from "../src/FloodTrigger.sol";

/// Deploy only after backtest/rule.toml is frozen.
/// RULE_HASH must be the hash of that frozen file.
contract Deploy is Script {
    function run() external returns (FloodTrigger trigger) {
        bytes32 ruleHash = vm.envBytes32("RULE_HASH");
        address resolver = vm.envAddress("RESOLVER");
        address radar = vm.envAddress("RADAR_ATTESTER");
        address rainfall = vm.envAddress("RAINFALL_ATTESTER");
        address pool = vm.envAddress("POOL");

        address[] memory corroborators = new address[](1);
        corroborators[0] = rainfall;

        vm.startBroadcast();
        trigger = new FloodTrigger(ruleHash, resolver, radar, corroborators, pool);
        vm.stopBroadcast();
    }
}
