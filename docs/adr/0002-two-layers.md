# ADR 0002: Two Layers

## Status

Accepted

## Context

There are two honest questions about tool-call repair. The narrow one: given a malformed model output, does a repairer recover the intended call? The broad one: does adding a repairer to a real agent loop make tasks succeed more often? The first can be answered hermetically. The second requires running models on real hardware and is noisy, slow, and non-deterministic. Mixing them would let live-hardware flakiness gate the citable result.

## Decision

The repo has two clearly separated layers.

The offline corpus is canonical. It is a frozen set of real raw model outputs, each labeled with a gold tool call or `no_tool`, scored with no network, GPU, time, or randomness. It runs in CI in seconds and gates merges.

The online harness is secondary and explicitly labeled live and hardware-bound. It runs end-to-end agentic tasks with and without a repairer. It is currently stubbed and never gates a merge.

## Consequences

The thing people cite stays deterministic and cheap to verify, and a green CI run means the offline benchmark passed, nothing more. The online harness can grow, change, or stay stubbed without putting the canonical artifact at risk. Anyone reading a result must know which layer produced it; the offline numbers are the ones that travel.
