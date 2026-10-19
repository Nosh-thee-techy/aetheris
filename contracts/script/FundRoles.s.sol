// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";

/// Send the radar and rainfall keys enough testnet coin for a 0.01 bond plus gas.
/// Broadcast with the deployer key. The deployer is the resolver.
contract FundRoles is Script {
    function run() external {
        address radar = vm.envAddress("RADAR_ATTESTER");
        address rainfall = vm.envAddress("RAINFALL_ATTESTER");
        vm.startBroadcast();
        payable(radar).transfer(0.02 ether);
        payable(rainfall).transfer(0.02 ether);
        vm.stopBroadcast();
    }
}
