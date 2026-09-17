---
urc: 5
title: Token Venue Policy
status: Draft
author: 0xBeans
created: 2026-09-15
---

## Abstract

ERC-20 tokens may recommend primary liquidity venues or restrict trading to specific venues, often hooked Uniswap v4 pools. Routers and frontends need to distinguish those preferences from restrictions before constructing transactions. This proposal defines `IVenuePolicy` to declare canonical v4 pools, distinguish preferred from exclusive venue policies, and expose external-venue permissions through both bulk and point queries. It also defines a standard policy-refusal error and consumer rules for routing, liquidity provision, and simulated withdrawal quotes.

## Motivation

Hooks make it practical for a token to require that all trading pass through a specific pool. The token enforces this in its transfer logic by refusing transfers to or from other venues. Nothing on-chain tells a consumer that the policy exists, so consumers discover it the hard way:

- A router simulates a route through a v3 or hookless v4 pool for the token. The simulation reverts on the token transfer, and the router either drops the token or interprets a generic revert as an RPC problem.
- A pool indexer lists a copycat pool for the token. Users add liquidity and then find they cannot trade against it, or cannot withdraw because the token blocks the pool.
- A frontend quotes an LP withdrawal from the canonical pool using a fixed slippage default. The hook charges an exit fee through return deltas, the received amount is lower than the position's principal, and the position manager reverts on slippage.
- A token allows trading anywhere but keeps its primary liquidity in a hooked pool. It needs a way to make that pool discoverable without excluding other working venues.

Each of these has been resolved bilaterally between individual token teams and individual routers. That does not scale: token launches are not slowing down, and v4 will only grow. The fix should be a discovery rule that a launchpad can adopt once and every consumer can honor once.

[URC-3](./urc-3.md) already establishes the pattern: a contract self-reports something a consumer cannot infer from state, and consumers agree on how to use the report. This proposal applies the same pattern to venue policy.

## Specification

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" are to be interpreted as described in RFC 2119.

### Scope

This proposal covers ERC-20 tokens that declare preferred liquidity venues or an exclusive venue policy. A token whose transfer logic refuses transfers to or from some venues is a "venue-gated token". The proposal defines how tokens declare their policy and how routers, aggregators, frontends, and pool indexers (together, "consumers") use it.

`Preferred` identifies recommended pools without imposing venue restrictions. `Exclusive` requires consumers to honor the declared restrictions on every route hop involving the token. The mode describes consumer obligations; it does not guarantee that the token can enforce them on-chain.

A "venue" is the address that holds a token balance on behalf of a pool: a Uniswap v2 pair, a v3 pool, or the v4 `PoolManager`. Because every v4 pool settles through one `PoolManager`, a v4 venue is identified by the pair `(PoolManager address, PoolId)`. Non-v4 venues carry a `PoolId` of zero.

Every `PoolKey` in this proposal refers to the canonical Uniswap v4 `PoolManager` on the chain the token is deployed on. Consumers resolve that address from the chain id, as they do for URC-3 and URC-4.

Transfer-time enforcement is outside the scope of this proposal. V4 settles balances per currency rather than per pool, so a token generally cannot identify the pool behind a `PoolManager` transfer. Multi-hop routes can net out the token's balance changes without transferring it.

### Where the declaration lives

The token MUST be the contract that implements `IVenuePolicy`. It is the authority for its venue preferences and restrictions, it is the key consumers index by, and it can have several canonical pools (an ETH pair and a stable pair) or none on v4 at all. A hook can serve many pools but cannot speak for the token's v2 or v3 venues, and a hook that is not the token's own has no authority over the token's policy.

Consumers MUST NOT treat an `IVenuePolicy` implementation on any contract other than the token as a declaration for that token.

### Interface

```solidity
// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.0;

import {PoolKey} from "@uniswap/v4-core/src/types/PoolKey.sol";

/// @notice Declares a token's preferred pools and venue restrictions.
///         ERC-165 interface id: `type(IVenuePolicy).interfaceId`, which is
///         `canonicalPools.selector ^ venueAllowed.selector ^
///          venueEnforcement.selector ^ externalVenues.selector`.
interface IVenuePolicy {
    enum VenueEnforcement {
        Preferred,
        Exclusive
    }

    enum ListKind {
        Allow,
        Block
    }

    struct ExternalVenue {
        address venue;
        // Membership in the corresponding directional allowlist or blocklist.
        bool inbound;
        bool outbound;
    }

    /// @notice Emitted when the mode changes. Consumers re-read the full policy.
    event VenueEnforcementChanged(VenueEnforcement enforcement);

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

    /// @notice Emitted when either external list kind or the returned list changes.
    ///         Consumers invalidate cached external-venue permissions.
    event ExternalVenuesChanged();

    /// @notice Whether canonical pools are preferred or exclusive.
    function venueEnforcement() external view returns (VenueEnforcement);

    /// @notice Canonical v4 pools, most preferred first, on this chain's
    ///         canonical PoolManager. Exhaustive only in Exclusive mode.
    /// @dev Full keys, not ids, so a caller can build a route without an indexer.
    ///      Empty means no preferred pools or, in Exclusive mode, no allowed v4 pools.
    function canonicalPools() external view returns (PoolKey[] memory);

    /// @notice Whether the token's declared policy permits a transfer into
    ///         (`inbound`) or out of a venue. A statement of policy, not a
    ///         guarantee that a specific transfer will succeed.
    /// @param venue The balance-holding address (v2 pair, v3 pool, or v4 PoolManager).
    /// @param poolId The v4 pool id, or zero for non-v4 venues.
    /// @param inbound True for a transfer into the venue, false for out of it.
    function venueAllowed(address venue, bytes32 poolId, bool inbound) external view returns (bool);

    /// @notice Complete non-v4 venue policy, with independent directional defaults.
    /// @dev For each direction, an absent venue has membership false.
    ///      Allow: membership true permits that direction; Block: it refuses it.
    function externalVenues()
        external
        view
        returns (ListKind inboundKind, ListKind outboundKind, ExternalVenue[] memory venues);
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

Five views including ERC-165 `supportsInterface`, four events, one error.

### Token requirements

- A token that implements `IVenuePolicy` MUST implement ERC-165 and MUST return true from `supportsInterface(type(IVenuePolicy).interfaceId)`.
- `venueEnforcement()` MUST return `Preferred` or `Exclusive`. In `Preferred` mode the token declares no venue restrictions: `venueAllowed` MUST return true for venue queries within this proposal's scope, and `externalVenues()` MUST return `(Block, Block, [])`. This does not promise that transfers succeed for reasons unrelated to venue policy.
- `canonicalPools()` MUST return the token's preferred v4 pools in `Preferred` mode and every permitted v4 pool in `Exclusive` mode, ordered most preferred first. Keys MUST be unique and include the declaring token as one currency. The order SHOULD be stable and SHOULD change only when preference changes.
- `venueAllowed` MUST reflect the token's declared policy, independently of any transaction-specific authorization needed to execute it. A true result does not guarantee transfer success; holding caps, paused state, or missing execution authorization can still cause failure.
- In `Exclusive` mode, `venueAllowed(poolManager, poolId, inbound)` MUST return true for both directions exactly when `poolId` identifies a key in `canonicalPools()`. Other v4 pool ids MUST return false. Non-v4 permissions MUST agree with `externalVenues()` as specified below.
- When a transfer is refused because of venue policy, the token MUST revert with `VenueNotAllowed` and MUST NOT revert with any other error for that reason. If the token cannot identify the v4 pool behind a `PoolManager` transfer, it MUST pass zero as `poolId`. Refusals for other reasons are out of scope.
- The token MUST emit `VenueEnforcementChanged` when its mode changes, `CanonicalPoolsChanged` when its canonical pool set or order changes, and `ExternalVenuesChanged` when either external list kind or the returned list changes. These events MUST be emitted in the transaction making the change.
- An individual external-venue permission change MUST also emit `VenueStatusChanged` for each affected direction. Mode switches, canonical-set changes, and external-default changes MAY use their aggregate events instead of emitting a per-venue event for every permission affected. A mode switch does not waive the events required for changes to the canonical or external lists themselves.
- A token whose policy is immutable still MUST implement the events; they are simply never emitted.

### External venue policy

`externalVenues()` MUST return a complete finite representation of the non-v4 policy. Each entry MUST have a unique, nonzero venue address other than the canonical `PoolManager`, and at least one membership flag MUST be true. Entry order has no preference meaning. Non-v4 point queries use `poolId = 0`.

For a venue and direction, let `member` be the corresponding flag in its entry, or false if the venue is absent. The declared permission is:

| Direction's list kind | Permission | Empty list |
|---|---|---|
| `Allow` | `member` | No venue permitted in that direction |
| `Block` | `!member` | Every venue permitted in that direction |

The inbound and outbound kinds are independent. For example, `(Allow, Block, [{venue: P, inbound: true, outbound: false}])` permits inbound transfers only to `P` while allowing outbound transfers from every external venue.

For every non-v4 venue, the bulk representation MUST produce the same answer as `venueAllowed(venue, 0, inbound)` at the same block. Both views SHOULD derive from the same stored policy. Consumers reading multiple views SHOULD pin them to one block. A partial list MUST NOT be presented as a complete policy.

### Consumer rules

Routers and aggregators:

1. Consumers MUST read `venueEnforcement()` before applying the canonical list. In `Preferred` mode, consumers MUST include canonical pools in candidate discovery when those pools meet the consumer's hook-support, execution, and safety requirements. They MAY route or split trades across other pools and SHOULD prefer canonical pools when otherwise equivalent routes tie. In `Exclusive` mode, consumers MUST restrict v4 candidates to `canonicalPools()` and MUST NOT route any hop involving the token through another v4 pool, even if simulation succeeds or the token's intermediate balance changes net to zero. Every token's policy on a route applies independently.
2. A non-v4 venue is a candidate for a given direction only if `venueAllowed(venue, 0, inbound)` returns true, or a complete cached `externalVenues()` policy gives the same answer. Selling into a venue is inbound; buying out of it is outbound. Consumers MAY bound the gas, response size, and list length accepted from the bulk query. If it fails, contains invalid kinds or entries, or exceeds those limits, they MUST use point queries or exclude the affected candidates; simulation alone MUST NOT substitute for missing permissions.
3. A revert carrying the `VenueNotAllowed` selector on a candidate path means the path is not permitted. The consumer SHOULD drop the path and SHOULD NOT count the revert as a token failure, an RPC failure, or a reason to blacklist the token. The `PoolManager` wraps failed outbound transfers in `WrappedError(address target, bytes4 selector, bytes reason, bytes details)`; consumers SHOULD match the selector on the inner `reason` as well as on the outer revert data. Some execution paths discard the original revert data, so absence of the selector does not prove the failure was unrelated to policy.
4. Consumers SHOULD refresh cached policy on its change events. `VenueEnforcementChanged` invalidates the full policy, `CanonicalPoolsChanged` invalidates the canonical list and cached v4 permissions, and `ExternalVenuesChanged` invalidates the external list and cached non-v4 permissions. `VenueStatusChanged` invalidates the named venue and direction. Consumers MUST NOT treat a failed mode query, unknown mode, or incomplete bulk response as permission to route. Existing-position withdrawals remain governed by rule 7.

Frontends and pool indexers:

5. In `Exclusive` mode, a consumer MUST NOT offer add-liquidity on a v4 pool unless it is in `canonicalPools()`, or on a non-v4 venue unless its inbound permission is true. Unsupported pools SHOULD be hidden or badged. In `Preferred` mode, consumers MAY offer add-liquidity on other pools and SHOULD identify those outside the canonical list as non-preferred. A failed or unknown mode query MUST NOT enable new liquidity provision. Normal execution and safety checks apply in both modes.
6. For remove-liquidity on a v4 pool with a hook, a consumer SHOULD simulate the removal to establish the expected amounts and then apply the user's slippage tolerance to those amounts. The `PositionManager` validates `amount0Min` and `amount1Min` against the principal delta, which is the returned `liquidityDelta` minus `feesAccrued`, so minima SHOULD be derived from that component of the simulation rather than from total wallet receipts. A known exit fee is not a reason to widen the tolerance.
7. Removing a pool from `canonicalPools()`, or a venue becoming disallowed, MUST NOT by itself cause a consumer to hide remove-liquidity for existing positions in that pool or venue.

Tokens with neither `IVenuePolicy` nor a trusted token-list declaration are unaffected.

### Token list extension

Non-upgradeable tokens deployed before this proposal cannot add the interface. For those, and as an off-chain mirror for everything else, the same data MAY be carried in a token list entry's `extensions` field. The token list schema allows nested objects up to three levels and no arrays, so pools are keyed `pool0`, `pool1`, and so on, in preference order:

```json
{
  "address": "0x88ad8DdF1E3898412146a534538d418c6F8A9062",
  "chainId": 4663,
  "name": "STANDARD",
  "symbol": "STANDARD",
  "decimals": 18,
  "extensions": {
    "venuePolicy": {
      "enforcement": "exclusive",
      "pool0": {
        "currency0": "0x0000000000000000000000000000000000000000",
        "currency1": "0x88ad8DdF1E3898412146a534538d418c6F8A9062",
        "fee": 10000,
        "tickSpacing": 200,
        "hooks": "0xF1eE073811B14359D850825E48d200483200eDcd"
      }
    }
  }
}
```

`enforcement` MUST be `"preferred"` or `"exclusive"`; if absent, it defaults to `"exclusive"`. Consumers MUST NOT interpret an unknown value as `"preferred"`. The keys refer to the canonical `PoolManager` for `chainId`. No `poolN` entries means no preferred pools in preferred mode, or no allowed v4 pools in exclusive mode. Pool indices MUST be consecutive from zero and are read in numeric order. With the explicit `enforcement` field, the token-list schema's ten-property limit leaves room for up to nine pool entries; a larger policy MUST NOT be silently truncated.

For extension-only tokens, `enforcement` and the `poolN` entries substitute for the `venueEnforcement()` and `canonicalPools()` reads; unknown modes have the same unavailable-policy handling. The extension has no non-v4 policy representation, so consumers apply the v4 portions of rules 1 and 5, plus rules 6 and 7, and treat non-v4 venues as they do today. It does not override an on-chain restriction on another token in the route.

Which token lists a consumer trusts is the consumer's choice, as it is for every other list-sourced attribute. When both on-chain data and a token list extension exist for a token, on-chain data wins.

### Conformance

A token conforms if it implements `IVenuePolicy`, meets the token requirements above, and reverts with `VenueNotAllowed` for policy refusals. A consumer conforms if it follows rules 1 through 7 for every token that reports the interface via ERC-165, and the v4 portions of rules 1 and 5 plus rules 6 and 7 for every token carrying the extension in a list the consumer trusts.

## Rationale

### Token, not hook

The token is the authority for its venue preferences and restrictions. Consumers index by token address, so a token-level view needs no discovery step, and a token may have canonical venues across versions and pairs, which a hook cannot describe.

Allowing a hook to declare on the token's behalf was considered and rejected. A copycat hook could implement the interface and claim a legacy token, and nothing on-chain would contradict it. Tokens that cannot implement the interface use the token list extension instead.

### Preferred and exclusive venues

A token can recommend its primary pool without forbidding other working liquidity. `Preferred` gives those pools a discovery path while leaving route selection open. `Exclusive` retains the restrictions needed by tokens whose supported integrations must use declared venues, including when an alternative route could execute successfully.

The enum values are fixed in this version. Adding a value is not assumed to be backward-compatible: older Solidity callers may reject a value outside the enum they were compiled with. Consumers treat an unsupported mode as unavailable policy.

### Bulk and point queries

`externalVenues()` lets off-chain consumers cache a complete policy, while `venueAllowed` remains useful for a single venue and as a fallback when a bulk read exceeds resource limits. Separate inbound and outbound list kinds let a token restrict deposits without restricting withdrawals. Aggregate events invalidate caches when a default changes for many venues at once.

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

Policy change events let consumers cache declarations and refresh them when the mode, canonical pools, or external permissions change. Aggregate events cover changes that affect more venues than a token can enumerate individually.

### Why consumer rules and not just an interface

These rules keep consumers from routing through unsupported pools in exclusive mode and make preferred pools discoverable without excluding other liquidity.

## Backwards Compatibility

Tokens with neither `IVenuePolicy` nor a trusted token-list declaration are unaffected. Consumers that ignore this proposal continue to work as they do today, with the failure modes described in Motivation.

Non-upgradeable deployed tokens cannot add the interface. The token list extension carries the same data for them until their next token version.

The `VenueNotAllowed` error is new. Tokens already deployed with their own policy errors cannot change them; consumers MAY additionally recognise those errors on a per-token basis, but this proposal does not require it.

The two additional views change the ERC-165 interface id from the earlier draft. Consumers MUST detect support for the full interface and MUST NOT interpret a missing `venueEnforcement()` view as `Preferred`. A legacy token-list declaration without `enforcement` retains exclusive behavior.

## Test Cases

Unless otherwise specified, these cases use a token `T` in `Exclusive` mode with `canonicalPools()` returning one key `K` on `PoolManager` `PM`, a copycat pool `K'` for the same pair with a different hook, and a v3 pool `P` the token blocks inbound only.

| Case | Call | Expected |
|---|---|---|
| ERC-165 | `T.supportsInterface(type(IVenuePolicy).interfaceId)` | `true` |
| Mode | `T.venueEnforcement()` | `Exclusive` |
| Canonical inbound | `T.venueAllowed(PM, K.toId(), true)` | `true` |
| Canonical outbound | `T.venueAllowed(PM, K.toId(), false)` | `true` |
| Copycat declared | `T.venueAllowed(PM, K'.toId(), true)` | `false` |
| Copycat inbound refusal | `T` refuses a transfer into `PM` on policy grounds during a swap into `K'` | Reverts with `VenueNotAllowed(PM, id, true)` where `id` is `K'.toId()` or zero. Whether the token sees a transfer at all depends on how the swap settles |
| Copycat outbound refusal | `T` refuses a transfer out of `PM` on policy grounds during a swap out of `K'` | Reverts with `WrappedError` whose `reason` carries `VenueNotAllowed(PM, id, false)` |
| Blocked v3 inbound | `T.venueAllowed(P, 0, true)` | `false` |
| Blocked v3 outbound | `T.venueAllowed(P, 0, false)` | `true` |
| Bulk external policy | `T.externalVenues()` | `(Block, Block, [{venue: P, inbound: true, outbound: false}])`; agrees with both point queries |
| Directional defaults | Policy is `(Allow, Block, [{venue: P, inbound: true, outbound: false}])` | Inbound permitted only for `P`; outbound permitted for `P` and unlisted venues |
| Empty allowlist | Both kinds are `Allow`, list is empty | No external venue permitted in either direction |
| Empty blocklist | Both kinds are `Block`, list is empty | All external venues permitted in both directions |
| Blocked v3 transfer | `T.transfer(P, amount)` | Reverts with `VenueNotAllowed(P, 0, true)` |
| Set change | Token adds a second canonical pool | `CanonicalPoolsChanged` emitted in the same transaction; `canonicalPools()` length is 2 |
| Venue change | Token blocks `P` inbound | `VenueStatusChanged(P, 0, true, false)` and `ExternalVenuesChanged` emitted in the same transaction |
| Default change | Token changes an external list kind | `ExternalVenuesChanged` emitted; consumers refresh external permissions without per-venue events for every affected address |
| Mode change | Token switches to `Preferred`, clearing external restrictions | `VenueEnforcementChanged(Preferred)` and any required list-change events emitted; consumers refresh the full policy |
| Router candidates | Router asked to route `T` with `K`, `K'`, and `P` liquid | `K` is a candidate; `K'` is not; `P` is a candidate for buys only |
| Exclusive intermediate hop | Route uses `T` only as a net-zero intermediary in `K'` | Route excluded even if simulation succeeds |
| Preferred discovery | A `Preferred` token declares `K`, while `K'` also has liquidity | `K` is considered subject to normal support and safety checks; `K'` may also be used |
| Preferred external policy | Query a `Preferred` token's external policy | `(Block, Block, [])`; point queries permit all external venues |
| Preferred add-liquidity | User opens add-liquidity on `K'` for a `Preferred` token | May be offered subject to normal checks, with a non-preferred badge |
| Unavailable bulk query | `externalVenues()` reverts or exceeds the consumer's size cap | Consumer uses `venueAllowed` or excludes affected candidates; does not infer permission from simulation |
| Unsupported mode | Mode query fails or returns an unknown value | No new route or add-liquidity offered based on that declaration; withdrawal controls remain available |
| Legacy list mode | Token-list declaration omits `enforcement` | Treated as `exclusive` |
| Frontend add-liquidity | User opens add-liquidity on `K'` or `P` | Add-liquidity disabled or omitted; optionally badged unsupported |
| Frontend remove-liquidity | Token removes `K` from `canonicalPools()` | Existing positions in `K` still show remove-liquidity |

## Reference Implementation

A minimal token in immutable `Exclusive` mode with one canonical pool and an owner-managed inbound blocklist for non-v4 venues. One enumerable set backs the bulk query, point query, and external transfer check. Enforcement of the v4 side is out of scope and omitted; the point is the interface surface.

```solidity
// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.20;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC165} from "@openzeppelin/contracts/utils/introspection/ERC165.sol";
import {EnumerableSet} from "@openzeppelin/contracts/utils/structs/EnumerableSet.sol";
import {PoolKey} from "@uniswap/v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "@uniswap/v4-core/src/types/PoolId.sol";
import {IVenuePolicy, VenueNotAllowed} from "./IVenuePolicy.sol";

contract VenueGatedToken is ERC20, ERC165, IVenuePolicy {
    using PoolIdLibrary for PoolKey;
    using EnumerableSet for EnumerableSet.AddressSet;

    address public immutable poolManager;
    address public immutable owner;
    PoolKey internal canonical;
    EnumerableSet.AddressSet private blockedInbound;

    constructor(address poolManager_, PoolKey memory canonical_) ERC20("Gated", "GATED") {
        poolManager = poolManager_;
        owner = msg.sender;
        canonical = canonical_;
    }

    function supportsInterface(bytes4 id) public view override returns (bool) {
        return id == type(IVenuePolicy).interfaceId || super.supportsInterface(id);
    }

    function venueEnforcement() external pure returns (VenueEnforcement) {
        return VenueEnforcement.Exclusive;
    }

    function canonicalPools() external view returns (PoolKey[] memory keys) {
        keys = new PoolKey[](1);
        keys[0] = canonical;
    }

    function externalVenues()
        external
        view
        returns (ListKind inboundKind, ListKind outboundKind, ExternalVenue[] memory venues)
    {
        inboundKind = ListKind.Block;
        outboundKind = ListKind.Block;
        uint256 count = blockedInbound.length();
        venues = new ExternalVenue[](count);
        for (uint256 i; i < count; ++i) {
            venues[i] = ExternalVenue({venue: blockedInbound.at(i), inbound: true, outbound: false});
        }
    }

    function venueAllowed(address venue, bytes32 poolId, bool inbound) public view returns (bool) {
        if (venue == poolManager) return poolId == PoolId.unwrap(canonical.toId());
        return !(inbound && blockedInbound.contains(venue));
    }

    /// @notice Block or unblock an external venue. The PoolManager is governed
    ///         by the canonical pool declaration rather than this blocklist.
    function setBlockedInbound(address venue, bool blocked) external {
        require(msg.sender == owner);
        require(venue != address(0) && venue != poolManager);
        bool changed = blocked ? blockedInbound.add(venue) : blockedInbound.remove(venue);
        if (changed) {
            emit VenueStatusChanged(venue, bytes32(0), true, !blocked);
            emit ExternalVenuesChanged();
        }
    }

    function _update(address from, address to, uint256 value) internal override {
        // V4 enforcement is omitted. A token may require a trusted hook to
        // authorise an aggregate PoolManager transfer, and reject missing
        // authorisation with VenueNotAllowed(poolManager, 0, inbound).
        if (blockedInbound.contains(to)) revert VenueNotAllowed(to, bytes32(0), true);
        super._update(from, to, value);
    }
}
```

## Security Considerations

- **Self-reported data.** Mode, pool lists, and permissions are claims made by the token. A malicious token can list a pool it later blocks, or declare a venue allowed and refuse it. Consumers MUST still simulate before executing. A policy refusal that conflicts with a cached `Preferred` declaration requires the consumer to refresh that declaration; it does not make the failed route safe. Frontends SHOULD use the declared permissions to decide what to render.
- **Copycat hooks.** A hook or any other contract can implement `IVenuePolicy`. It has no authority over a token that does not itself implement the interface, and consumers MUST NOT read it as such. Only the token, or a trusted token list, speaks for the token.
- **Policy changes.** Mutable modes, lists, and permissions can change between a quote and execution. Consumers SHOULD subscribe to the change events, pin related reads to the same block, and treat a `VenueNotAllowed` revert at execution time as a signal to refresh. Tokens SHOULD make policy changes rare and, where possible, immutable.
- **Empty canonical set.** In `Exclusive` mode an empty list excludes the token from v4 routing; external venues still follow rule 2. In `Preferred` mode it supplies no recommendations and imposes no venue restriction. Consumers MUST read the mode before interpreting an empty list.
- **Bulk-query limits.** A token can return an expensive or oversized external list. Consumers MAY cap read resources, but MUST NOT treat failure or truncation as an empty list. Rule 2 provides point queries as the fallback.
- **Event spam.** A token could emit policy-change events on every block to force consumers to re-read. Consumers SHOULD rate-limit re-reads per token.
- **Error selector collisions and wrapping.** `VenueNotAllowed(address,bytes32,bool)` has a fixed selector. A non-conforming contract could revert with the same selector for unrelated reasons. Consumers use the selector to prune routes, never to grant permission, so a collision can only cause a route to be dropped. Conversely, some execution paths discard revert data, so consumers cannot rely on the selector to catch every policy refusal.
- **Token list trust.** The extension lets any list author declare venues for any token. A consumer that trusts a list is trusting its author on this attribute as on every other. On-chain data overrides the extension whenever both exist.

## Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
