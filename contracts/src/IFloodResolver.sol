// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// The only call a resolver, or a later vote contract, is allowed to make.
/// Uphold keeps the attester result. Reject cancels it. Nothing else.
interface IFloodResolver {
    function resolve(bytes32 id, bool upheld) external;
}
