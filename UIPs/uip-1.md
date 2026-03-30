---
uip: 1
title: Uniswap Improvement Proposal Process
author: Daniel Gretzke (@gretzke)
status: Final
created: 2026-03-30
---

## Abstract

A Uniswap Improvement Proposal (UIP) is a design document providing information to the Uniswap ecosystem, or describing a new standard, interface, or process related to Uniswap. A UIP should provide a clear technical description of the proposed change together with its rationale.

This document defines the UIP process and specifies how proposals are authored, discussed, and finalized.

## Motivation

The Uniswap ecosystem produces widely used smart contracts and interfaces that are depended upon by a broad range of participants, including protocol developers, application builders, infrastructure providers, and external integrators.

Design discussions for such systems often occur within the teams responsible for implementation, code reviews, and informal conversations. The UIP process provides a dedicated, durable format for capturing these discussions as structured public design documents. This allows architectural decisions, assumptions, and tradeoffs to be discussed openly and referenced independently of any specific implementation.

The goal of the UIP process is to extend building in public to the design phase, enabling shared understanding and long-term reference for standards that are intended to be reused, extended, or relied upon by others.

## Specification

### Scope

A UIP can describe process changes, meta-standards, organizational conventions, smart-contract standards, interfaces, execution models, or protocol-adjacent architectural patterns that are specific to the Uniswap ecosystem.

### Status

Each UIP has a status which reflects its stage in the process:

- **Draft** – The proposal is under active development.
- **Discussion** – The proposal is considered complete enough for broad review.
- **Last Call** – The proposal is believed to be ready for finalization and is open for final feedback.
- **Final** – The proposal is complete and no longer subject to change.
- **Superseded** – The proposal has been replaced by a newer proposal; a reference to the superseding proposal is added once it reaches Final status.
- **Withdrawn** – The proposal has been withdrawn by its author(s).

Once a proposal reaches Final, it is immutable. Any changes require a new proposal that explicitly supersedes the earlier one.

### Proposal Format

Each UIP is a design document with a standardized structure intended to make proposals easy to read, discuss, and reference over time.

#### Preamble

The preamble consists of YAML frontmatter containing metadata about the proposal. Required fields:

- `uip` – The proposal number.
- `title` – A short descriptive title. Must not include the proposal number.
- `author` – Author name and GitHub handle.
- `status` – Current status.
- `created` – Date of creation in YYYY-MM-DD format.

Optional fields:

- `extends` – Indicates that the proposal builds upon or refines one or more earlier proposals. Extended proposals remain valid unless explicitly superseded.
- `supersedes` – Indicates that the proposal replaces one or more earlier proposals. When a proposal is superseded, its status must be updated and a reference to the superseding proposal is added once that proposal has reached Final status.
- `last-call-deadline` – Set by a UIP editor when the proposal enters Last Call status. Specifies the end date of the 14-day review window.

#### Abstract

A short technical summary describing the proposal at a high level. It should provide enough information for a reader to understand the general intent and scope without reading the full document.

#### Motivation (optional)

Explains why the proposal is necessary. Describes the problem being addressed and why existing processes, conventions, or designs are insufficient. May be omitted if the motivation is self-evident.

#### Specification

Describes the proposal in sufficient detail to allow it to be clearly understood and evaluated. The specification should focus on what is required, not how it is implemented.

#### Rationale

Explains the reasoning behind the proposal. Describes alternative approaches that were considered, tradeoffs that were made, and concerns raised during discussion.

#### Backwards Compatibility (optional)

If the proposal introduces backwards-incompatible changes, this section must describe those incompatibilities and their consequences.

#### Test Cases (optional)

Test cases may be included where they meaningfully aid understanding of the proposal.

#### Reference Implementation (optional)

A reference or example implementation may be included to assist readers in understanding the proposal. Inclusion does not imply endorsement or required adoption.

#### Security Considerations

Proposals must include a section discussing relevant security considerations, including security assumptions, risks, and design decisions.

#### Copyright

All UIPs must be released under CC0 1.0. The copyright section must include the standard CC0 waiver text.

## Rationale

The UIP process is intended to provide a consistent way to document and evaluate design decisions that affect the Uniswap ecosystem. Although these proposals are primarily written for use within the Uniswap ecosystem, some designs may prove broadly useful and evolve into widely reused infrastructure, such as Permit2. For this reason, the process emphasizes open discussion of design choices and tradeoffs. Making these considerations explicit allows proposals to be evaluated on their technical merits and, where applicable, adopted or extended by a wider audience.

This approach ensures that design decisions are recorded transparently and can serve both immediate ecosystem needs and longer-term reuse.

## Security Considerations

This proposal defines a documentation and design process and does not introduce direct security risks, but clearer and more transparent design discussions may help surface security-relevant assumptions and risks earlier in the development lifecycle.

## Copyright

Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
