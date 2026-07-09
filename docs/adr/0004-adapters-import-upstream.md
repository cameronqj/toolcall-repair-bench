# ADR 0004: Adapters Import Upstream

## Status

Accepted

## Context

To score a repair library, the benchmark has to run that library's parsing logic. One way is to copy the relevant code into this repo and call our copy. That copy drifts from upstream the moment upstream changes, and then the leaderboard reports the behavior of a fork nobody ships, not the real library. The result stops meaning anything.

## Decision

An adapter is a thin wrapper that imports the upstream tool and calls it. It does not reimplement or fork that tool's parser. Each adapter exposes one function:

```
(raw_output: str, request_tools: list[str]) -> list[toolcall] | None
```

It receives the raw model output and the names of the tools the request offered, and returns the recovered tool calls, an empty list for a deliberate `no_tool`, or `None` when the adapter is unavailable. The adapter must be deterministic and must not touch the network or a GPU in the offline path.

If an upstream library cannot be imported in the offline environment, its adapter reports unavailable and is shown as such on the leaderboard; all other adapters still score.

## Consequences

The benchmark always scores the real library at its installed version, so results track upstream rather than a stale copy. Adapters stay small and easy to audit. The cost is a dependency edge: scoring an adapter requires installing its upstream, and a missing install reads as unavailable instead of as a failure to repair.
