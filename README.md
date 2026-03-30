# Uniswap Improvement Proposals (UIPs)

Uniswap Improvement Proposals (UIPs) describe standards, interfaces, and processes for the Uniswap ecosystem. This repository is the canonical home for all UIP documents.

## What is a UIP?

A UIP is a design document providing information to the Uniswap ecosystem, or describing a new standard, interface, or process related to Uniswap. UIPs provide a clear technical description of the proposed change together with its rationale. See [UIP-1](UIPs/uip-1.md) for the full process specification.

## How to Submit a UIP

1. **Copy the template.** Use [`uip-template.md`](uip-template.md) as your starting point.
2. **Write your proposal.** Fill in all required sections. Set the status to `Draft`.
3. **Open a pull request.** Add your proposal as `UIPs/uip-N.md` where N is the next available number. Place any assets in `assets/uip-N/`.
4. **Request review.** A UIP editor will review your submission for completeness.
5. **Start discussion.** When ready for community feedback, update the status to `Discussion` and post your proposal in the [UIP Discussion category](https://gov.uniswap.org/) on the governance forum.

## UIP Lifecycle

```
Draft → Discussion → Last Call (14 days) → Final
                                              ↓
                                          Superseded

Draft or Discussion → Withdrawn
Last Call → Discussion (if normative changes arise)
```

See [UIP-1](UIPs/uip-1.md) for complete status definitions and transition rules.

## Links

- [UIP-1: Process Specification](UIPs/uip-1.md)
- [UIP Template](uip-template.md)
- [Uniswap Governance Forum](https://gov.uniswap.org/)
