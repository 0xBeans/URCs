---
urc: 5
title: Token Venue Policy
status: Draft
author: 0xBeans
created: 2026-09-15
---

## Abstract

Some ERC-20 tokens restrict which liquidity venues they can be transferred into or out of, typically to steer trading through one hooked Uniswap v4 pool. Today that restriction is invisible to routers, aggregators, and frontends until a transfer reverts or a user is stuck in a pool the token does not support. This proposal defines `IVenuePolicy`, a small interface the token implements to declare its canonical v4 pools and answer venue-permission queries, one standard error for policy refusals, and consumer rules that make the declaration effective: route only through declared venues, do not offer add-liquidity on undeclared pools, and quote liquidity removals by simulation.

## Motivation

Hooks make it practical for a token to require that all trading pass through a specific pool. The token enforces this in its transfer logic by refusing transfers to or from other venues. Nothing on-chain tells a consumer that the policy exists, so consumers discover it the hard way:

- A router simulates a route through a v3 or hookless v4 pool for the token. The simulation reverts on the token transfer, and the router either drops the token or interprets a generic revert as an RPC problem.
- A pool indexer lists a copycat pool for the token. Users add liquidity and then find they cannot trade against it, or cannot withdraw because the token blocks the pool.
- A frontend quotes an LP withdrawal from the canonical pool using a fixed slippage default. The hook charges an exit fee through return deltas, the received amount is lower than the position's principal, and the position manager reverts on slippage.

Each of these has been resolved bilaterally between individual token teams and individual routers. That does not scale: token launches are not slowing down, and v4 will only grow. The fix should be a discovery rule that a launchpad can adopt once and every consumer can honor once.

[URC-3](./urc-3.md) already establishes the pattern: a contract self-reports something a consumer cannot infer from state, and consumers agree on how to use the report. This proposal applies the same pattern to venue policy.

## Specification

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" are to be interpreted as described in RFC 2119.

### Scope

This proposal covers ERC-20 tokens whose transfer logic refuses transfers to or from some liquidity venues (a "venue-gated token"). It defines how such a token declares its policy and how routers, aggregators, frontends, and pool indexers (together, "consumers") use the declaration.

A "venue" is the address that holds a token balance on behalf of a pool: a Uniswap v2 pair, a v3 pool, or the v4 `PoolManager`. Because every v4 pool settles through one `PoolManager`, a v4 venue is identified by the pair `(PoolManager address, PoolId)`. Non-v4 venues carry a `PoolId` of zero.

Every `PoolKey` in this proposal refers to the canonical Uniswap v4 `PoolManager` on the chain the token is deployed on. Consumers resolve that address from the chain id, as they do for URC-3 and URC-4.

Transfer-time enforcement is outside the scope of this proposal. V4 settles balances per currency rather than per pool, so a token generally cannot identify the pool behind a `PoolManager` transfer. Multi-hop routes can net out the token's balance changes without transferring it.

### Where the declaration lives

The token MUST be the contract that implements `IVenuePolicy`. The token is the contract that enforces the restriction, it is the key consumers index by, and it can have several canonical pools (an ETH pair and a stable pair) or none on v4 at all. A hook can serve many pools but cannot speak for the token's v2 or v3 venues, and a hook that is not the token's own has no authority over the token's policy.

Consumers MUST NOT treat an `IVenuePolicy` implementation on any contract other than the token as a declaration for that token.

### Interface

```solidity
// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.0;

import {PoolKey} from "@uniswap/v4-core/src/types/PoolKey.sol";

/// @notice Declares which venues a venue-gated token trades in.
///         ERC-165 interface id: `type(IVenuePolicy).interfaceId`, which is
///         `canonicalPools.selector ^ venueAllowed.selector`.
interface IVenuePolicy {
    /// @notice Emitted when the canonical pool set or its order changes.
    ///         Consumers re-read `canonicalPools()`.
    event CanonicalPoolsChanged();

    /// @notice Emitted when a venue's declared permission changes in one
    ///         direction. Consumers re-read `venueAllowed` for that venue.
    /// @param venue The balance-holding address (v2 pair, v3 pool, or v4 PoolManager).
    /// @param poolId The v4 pool id, or zero for non-v4 venues.
    /// @param inbound True for transfers into the venue, false for out of it.
    /// @param allowed The new declared permission for that direction.
    event VenueStatusChanged(address indexed venue, bytes32 indexed poolId, bool inbound, bool allowed);

    /// @notice The v4 pools this token is meant to trade in, most preferred
    ///         first, on the canonical PoolManager of this chain.
    /// @dev Full keys, not ids, so a caller can build a route without an indexer.
    ///      Empty means the token declares no v4 venue.
    function canonicalPools() external view returns (PoolKey[] memory);

    /// @notice Whether the token's declared policy permits a transfer into
    ///         (`inbound`) or out of a venue. A statement of policy, not a
    ///         guarantee that a specific transfer will succeed.
    /// @param venue The balance-holding address (v2 pair, v3 pool, or v4 PoolManager).
    /// @param poolId The v4 pool id, or zero for non-v4 venues.
    /// @param inbound True for a transfer into the venue, false for out of it.
    function venueAllowed(address venue, bytes32 poolId, bool inbound) external view returns (bool);
}

/// @notice The only error a venue-gated token reverts with when a transfer is
///         refused because of venue policy.
/// @dev Declared at file level so any contract can select on it without
///      inheriting the interface.
/// @param venue The venue the transfer was refused for.
/// @param poolId The v4 pool id when the token can identify it, otherwise zero.
/// @param inbound True if the refused transfer was into the venue.
error VenueNotAllowed(address venue, bytes32 poolId, bool inbound);
```

Three views (`canonicalPools`, `venueAllowed`, and ERC-165 `supportsInterface`), two events, one error.

### Token requirements

- A token that implements `IVenuePolicy` MUST implement ERC-165 and MUST return true from `supportsInterface(type(IVenuePolicy).interfaceId)`.
- `canonicalPools()` MUST return every v4 pool the token's policy permits trading in, ordered most preferred first. The order SHOULD be stable and SHOULD change only when preference changes.
- `venueAllowed` MUST reflect the token's declared policy. It MUST NOT return true for a venue and direction that the policy refuses, and MAY return true for a transfer that would still fail for a reason unrelated to venue policy (for example a holding cap or a paused state). Tokens are not required to enumerate venues: a blocklist token satisfies this by returning true for any venue it does not block.
- For the v4 `PoolManager`, `venueAllowed(poolManager, poolId, inbound)` MUST return true when `poolId` is the id of a key in `canonicalPools()`, for both values of `inbound`, and MUST return false for any other `poolId` unless the token's policy permits that pool.
- When a transfer is refused because of venue policy, the token MUST revert with `VenueNotAllowed` and MUST NOT revert with any other error for that reason. If the token cannot identify the v4 pool behind a `PoolManager` transfer, it MUST pass zero as `poolId`. Refusals for other reasons are out of scope.
- The token MUST emit `CanonicalPoolsChanged` in the same transaction as any change to the set or order returned by `canonicalPools()`, and MUST emit `VenueStatusChanged` in the same transaction as any change to a venue's declared permission in either direction.
- A token whose policy is immutable still MUST implement the events; they are simply never emitted.

### Consumer rules

Routers and aggregators:

1. If a token implements `IVenuePolicy`, the candidate v4 pools for that token are exactly `canonicalPools()`. A consumer MUST NOT route through any other v4 pool for that token, even when a simulation of that route succeeds. A swap that succeeds into an undeclared pool is a swap into liquidity that may not be withdrawable.
2. A non-v4 venue is a candidate for a given direction only if `venueAllowed(venue, 0, inbound)` returns true for that direction. Selling into a venue is inbound; buying out of it is outbound.
3. A revert carrying the `VenueNotAllowed` selector on a candidate path means the path is not permitted. The consumer SHOULD drop the path and SHOULD NOT count the revert as a token failure, an RPC failure, or a reason to blacklist the token. The `PoolManager` wraps failed outbound transfers in `WrappedError(address target, bytes4 selector, bytes reason, bytes details)`; consumers SHOULD match the selector on the inner `reason` as well as on the outer revert data. Some execution paths discard the original revert data, so absence of the selector does not prove the failure was unrelated to policy.
4. Consumers SHOULD re-read `canonicalPools()` on `CanonicalPoolsChanged` and re-read `venueAllowed` for the named venue on `VenueStatusChanged`, rather than polling.

Frontends and pool indexers:

5. A consumer MUST NOT offer add-liquidity on a v4 pool for a venue-gated token unless the pool is in `canonicalPools()`, and MUST NOT offer it on a non-v4 venue unless `venueAllowed(venue, 0, true)` returns true. Undeclared pools SHOULD be hidden or badged as unsupported.
6. For remove-liquidity on a canonical pool with a hook, a consumer SHOULD simulate the removal to establish the expected amounts and then apply the user's slippage tolerance to those amounts. The `PositionManager` validates `amount0Min` and `amount1Min` against the principal delta, which is the returned `liquidityDelta` minus `feesAccrued`, so minima SHOULD be derived from that component of the simulation rather than from total wallet receipts. A known exit fee is not a reason to widen the tolerance.
7. Removing a pool from `canonicalPools()`, or a venue becoming disallowed, MUST NOT by itself cause a consumer to hide remove-liquidity for existing positions in that pool or venue.

Tokens that do not implement `IVenuePolicy` are unaffected. Consumers treat them exactly as they do today.

### Token list extension

Non-upgradeable tokens deployed before this proposal cannot add the interface. For those, and as an off-chain mirror for everything else, the same data MAY be carried in a token list entry's `extensions` field. The token list schema allows nested objects up to three levels and no arrays, so pools are keyed `pool0`, `pool1`, and so on, in preference order:

```json
{
  "address": "0x88ad8DdF1E3898412146a534538d418c6F8A9062",
  "chainId": 4663,
  "symbol": "STANDARD",
  "extensions": {
    "venuePolicy": {
      "pool0": {
        "currency0": "0x0000000000000000000000000000000000000000",
        "currency1": "0x88ad8DdF1E3898412146a534538d418c6F8A9062",
        "fee": 0,
        "tickSpacing": 60,
        "hooks": "0xF1eE073811B14359D850825E48d200483200eDcd"
      }
    }
  }
}
```

The keys refer to the canonical `PoolManager` for `chainId`. A `venuePolicy` object with no `poolN` entries declares no v4 venue. The extension has no equivalent of `venueAllowed`, so for a token listed this way consumers apply the v4 portions of rules 1 and 5, plus rules 6 and 7, and treat non-v4 venues as they do today.

Which token lists a consumer trusts is the consumer's choice, as it is for every other list-sourced attribute. When both on-chain data and a token list extension exist for a token, on-chain data wins.

### Conformance

A token conforms if it implements `IVenuePolicy`, meets the token requirements above, and reverts with `VenueNotAllowed` for policy refusals. A consumer conforms if it follows rules 1 through 7 for every token that reports the interface via ERC-165, and the v4 portions of rules 1 and 5 plus rules 6 and 7 for every token carrying the extension in a list the consumer trusts.

## Rationale

### Token, not hook

Early discussion put the declaration on the hook, mirroring URC-3. The token is the better home for three reasons. The token is what enforces the policy, so it is the only contract that can speak for it. Consumers index by token address, so a token-level view needs no discovery step. And a token may have canonical venues across versions and pairs, which a hook cannot describe.

Allowing a hook to declare on the token's behalf was considered and rejected. A copycat hook could implement the interface and claim a legacy token, and nothing on-chain would contradict it. Tokens that cannot implement the interface use the token list extension instead.

### Canonical `PoolManager` by convention

`PoolKey` carries no manager address. Adding one to every entry would diverge from URC-3 and URC-4, which take bare keys. This proposal follows them and fixes the manager by chain convention.

### Full `PoolKey`s, not ids

Returning `PoolId` values would force every consumer to run an indexer to recover the key. Returning keys lets a router build the route from the view alone.

### An ordered list, not a single pool

Most tokens will return one pool. Allowing several supports tokens that want both an ETH pair and a stable pair.

### One error

Simulation-based routers already classify reverts by selector. A single standard error lets them recognise a policy refusal without parsing token-specific errors or guessing from generic reverts. Making it a file-level error rather than an interface member means a router can import the selector without depending on the interface. Because v4 wraps outbound transfer failures, the rule tells consumers to look inside `WrappedError` too.

### Preflight queries

`venueAllowed` provides a cheap check for routers filtering candidate paths and frontends deciding which liquidity forms to render. Keeping the query limited to venue policy avoids duplicating the token's transfer logic. Consumers must still simulate the transaction.

### Direction on `VenueStatusChanged`

A token can block inbound transfers to a venue while leaving outbound open so that positions can be withdrawn. Without a direction the event could not describe that change, so it carries `inbound` and mirrors the shape of `venueAllowed`.

### Events instead of polling

`canonicalPools()` changes rarely. An event lets consumers cache the result indefinitely and refresh on change, which matters for aggregators that index thousands of tokens.

### Why consumer rules and not just an interface

These rules keep consumers from routing through unsupported pools.

## Backwards Compatibility

Tokens that do not implement `IVenuePolicy` are unaffected. Consumers that ignore this proposal continue to work as they do today, with the failure modes described in Motivation.

Non-upgradeable deployed tokens cannot add the interface. The token list extension carries the same data for them until their next token version.

The `VenueNotAllowed` error is new. Tokens already deployed with their own policy errors cannot change them; consumers MAY additionally recognise those errors on a per-token basis, but this proposal does not require it.

## Test Cases

Given a token `T` implementing `IVenuePolicy` with `canonicalPools()` returning one key `K` on `PoolManager` `PM`, a copycat pool `K'` for the same pair with a different hook, and a v3 pool `P` the token blocks inbound only:

| Case | Call | Expected |
|---|---|---|
| ERC-165 | `T.supportsInterface(type(IVenuePolicy).interfaceId)` | `true` |
| Canonical inbound | `T.venueAllowed(PM, K.toId(), true)` | `true` |
| Canonical outbound | `T.venueAllowed(PM, K.toId(), false)` | `true` |
| Copycat declared | `T.venueAllowed(PM, K'.toId(), true)` | `false` |
| Copycat inbound refusal | `T` refuses a transfer into `PM` on policy grounds during a swap into `K'` | Reverts with `VenueNotAllowed(PM, id, true)` where `id` is `K'.toId()` or zero. Whether the token sees a transfer at all depends on how the swap settles |
| Copycat outbound refusal | `T` refuses a transfer out of `PM` on policy grounds during a swap out of `K'` | Reverts with `WrappedError` whose `reason` carries `VenueNotAllowed(PM, id, false)` |
| Blocked v3 inbound | `T.venueAllowed(P, 0, true)` | `false` |
| Blocked v3 outbound | `T.venueAllowed(P, 0, false)` | `true` |
| Blocked v3 transfer | `T.transfer(P, amount)` | Reverts with `VenueNotAllowed(P, 0, true)` |
| Set change | Token adds a second canonical pool | `CanonicalPoolsChanged` emitted in the same transaction; `canonicalPools()` length is 2 |
| Venue change | Token blocks `P` inbound | `VenueStatusChanged(P, 0, true, false)` emitted in the same transaction |
| Router candidates | Router asked to route `T` with `K`, `K'`, and `P` liquid | `K` is a candidate; `K'` is not; `P` is a candidate for buys only |
| Frontend add-liquidity | User opens add-liquidity on `K'` or `P` | Add-liquidity disabled or omitted; optionally badged unsupported |
| Frontend remove-liquidity | Token removes `K` from `canonicalPools()` | Existing positions in `K` still show remove-liquidity |

## Reference Implementation

A minimal token with one immutable canonical pool and an owner-managed blocklist for non-v4 venues. Enforcement of the v4 side is out of scope and omitted; the point is the interface surface.

```solidity
// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.0;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC165} from "@openzeppelin/contracts/utils/introspection/ERC165.sol";
import {PoolKey} from "@uniswap/v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "@uniswap/v4-core/src/types/PoolId.sol";
import {IVenuePolicy, VenueNotAllowed} from "./IVenuePolicy.sol";

contract VenueGatedToken is ERC20, ERC165, IVenuePolicy {
    using PoolIdLibrary for PoolKey;

    address public immutable poolManager;
    address public immutable owner;
    PoolKey internal canonical;
    mapping(address venue => bool) public blockedInbound;

    constructor(address poolManager_, PoolKey memory canonical_) ERC20("Gated", "GATED") {
        poolManager = poolManager_;
        owner = msg.sender;
        canonical = canonical_;
    }

    function supportsInterface(bytes4 id) public view override returns (bool) {
        return id == type(IVenuePolicy).interfaceId || super.supportsInterface(id);
    }

    function canonicalPools() external view returns (PoolKey[] memory keys) {
        keys = new PoolKey[](1);
        keys[0] = canonical;
    }

    function venueAllowed(address venue, bytes32 poolId, bool inbound) public view returns (bool) {
        if (venue == poolManager) return poolId == PoolId.unwrap(canonical.toId());
        return !(inbound && blockedInbound[venue]);
    }

    /// @notice Block or unblock an external venue. The PoolManager is
    ///         governed by the canonical pool declaration, not the blocklist,
    ///         so blocking it here would contradict `venueAllowed`.
    function setBlockedInbound(address venue, bool blocked) external {
        require(msg.sender == owner);
        require(venue != address(0) && venue != poolManager);
        blockedInbound[venue] = blocked;
        emit VenueStatusChanged(venue, bytes32(0), true, !blocked);
    }

    function _update(address from, address to, uint256 value) internal override {
        // The v4 side needs a mechanism the token can trust to authorise an
        // aggregate amount moving to or from the PoolManager in this
        // transaction, for example a transient budget set by the canonical
        // hook. The token cannot tell which pool the transfer belongs to, so
        // when that check fails it reverts VenueNotAllowed(poolManager, 0, inbound).
        if (blockedInbound[to]) revert VenueNotAllowed(to, bytes32(0), true);
        super._update(from, to, value);
    }
}
```

## Security Considerations

- **Self-reported data.** `canonicalPools()` and `venueAllowed` are claims made by the token. A malicious token can list a pool it later blocks, or declare a venue allowed and refuse it. Consumers MUST still simulate before executing. Frontends SHOULD use `venueAllowed` to decide what to render.
- **Copycat hooks.** A hook or any other contract can implement `IVenuePolicy`. It has no authority over a token that does not itself implement the interface, and consumers MUST NOT read it as such. Only the token, or a trusted token list, speaks for the token.
- **Policy changes.** A token whose policy is mutable can change `canonicalPools()` between a quote and execution. Consumers that cache the list SHOULD subscribe to `CanonicalPoolsChanged` and SHOULD treat a `VenueNotAllowed` revert at execution time as a signal to refresh. Tokens SHOULD make policy changes rare and, where possible, immutable.
- **Empty canonical set.** A token that returns an empty list from `canonicalPools()` is telling consumers it has no declared v4 venue. Under rule 1 a router will not route it on v4; non-v4 venues are still governed by rule 2. A token that returns an empty list by mistake becomes unroutable on v4 until it emits `CanonicalPoolsChanged`.
- **Event spam.** A token could emit `CanonicalPoolsChanged` on every block to force consumers to re-read. Consumers SHOULD rate-limit re-reads per token.
- **Error selector collisions and wrapping.** `VenueNotAllowed(address,bytes32,bool)` has a fixed selector. A non-conforming contract could revert with the same selector for unrelated reasons. Consumers use the selector to prune routes, never to grant permission, so a collision can only cause a route to be dropped. Conversely, some execution paths discard revert data, so consumers cannot rely on the selector to catch every policy refusal.
- **Token list trust.** The extension lets any list author declare venues for any token. A consumer that trusts a list is trusting its author on this attribute as on every other. On-chain data overrides the extension whenever both exist.

## Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
