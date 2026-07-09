# ADR 0001: Project Scope

## Status

Accepted

## Context

Local models can attempt tool calls but often emit them in a shape a client cannot parse. Several libraries try to repair these outputs, and there is no shared, neutral way to compare them. There is also a temptation to grow a benchmark into the thing it measures: a router that picks the best repairer, a proxy that applies the repair, or an agent that runs the recovered call.

## Decision

`toolcall-repair-bench` is scoped to one job: measuring how well repair libraries recover the intended tool call from a malformed local-model output.

It is a dataset plus a scorer. It will not become:

- A tool, proxy, or router that performs repair in production.
- A tool executor or agent that runs recovered calls.
- A model server or anything that requires a GPU to score.

Repair libraries are evaluated through thin adapters that import them. The corpus and the scorer are the product; everything else is an adapter or a doc.

## Consequences

The repo stays small and inspectable, and a result here means one specific thing rather than an opaque end-to-end score. Users who want to apply repairs in a live system should use a proxy such as `local-tool-proxy`, which appears here only as one entrant. The online harness (see ADR 0002) is deliberately kept secondary so the project does not drift into being an agent runtime.
