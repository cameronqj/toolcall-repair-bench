# ADR 0003: Precision And Recall

## Status

Accepted

## Context

It is easy to make a repairer look good by reporting recall alone: count how many real tool calls it recovers and ignore what it does to everything else. A repairer that emits a call whenever it sees a requested tool name will recover almost every real call and score near-perfect recall. It will also fabricate calls on plain prose, where the right answer was to call nothing at all. A single accuracy number hides this entirely.

## Decision

The benchmark reports precision and recall, not one blended score. Cases labeled `no_tool` are first-class and carry equal weight with cases that call a tool, because correctly emitting nothing is a real outcome the repairer must get right.

The headline result is the precision/recall frontier across adapters. A maximalist repairer can sit at high recall and low precision; a strict one at high precision and lower recall. Where each adapter lands on that frontier is the point of the project, not a footnote to a leaderboard rank.

## Consequences

Contributors must supply `no_tool` cases, not only positive ones, or the precision axis is meaningless. The leaderboard shows both numbers so a reader can pick the operating point that fits their use. Fabrication is visible and penalized rather than averaged away, which is the behavior the benchmark exists to surface.
