# Project Constitution

`toolcall-repair-bench` measures how well repair libraries recover the tool call a local model meant to make from the malformed output it actually emitted.

## 1. Neutrality First

No entrant is privileged. The maintainer also wrote `local-tool-proxy`, and it is just one adapter here with zero special treatment. If a baseline beats it on the corpus, the leaderboard says so in plain numbers and nothing is hand-tuned to hide that.

## 2. Reproducibility Is The Product

The offline corpus is hermetic and deterministic. Scoring touches no network, needs no GPU, and reads no clock or random source. The same corpus and the same adapter produce the same numbers on any machine, which is the only reason a result here is worth citing.

## 3. Provenance And Sanitization

Every case records where its raw output came from and is stripped of secrets, local paths, credentials, and private source before it enters the corpus. Captured model output can carry any of these by accident, so sanitization is a precondition for inclusion, not a cleanup step. Treat every committed case as published forever.

## 4. Precision Is First-Class

Fabricating a tool call from ordinary prose is a failure, not a near-miss. A repairer that invents calls to win recall is penalized for it, and `no_tool` cases carry equal weight with cases that do call a tool. The benchmark exists to expose exactly this trade-off.

## 5. Gold Labels Are Auditable

Each gold answer must be defensible from the `raw_output` alone, without access to the model, the prompt history, or the contributor's intent. When a case is genuinely ambiguous, it gets a recorded `note` explaining the call, not a confident guess. A label nobody can re-derive does not belong in the corpus.

## 6. Honest Reporting Over A Flattering Table

The README reports the frontier as it is, including the cases where every adapter fails. We do not drop hard cases, round away losses, or frame the numbers to favor one approach. A table that flatters the project is worth less than one a skeptic can trust.

## 7. Adapters Import, Never Fork

An adapter wraps the upstream tool it evaluates by importing it. Reimplementing or forking that tool's parser into this repo is out of scope, because then the benchmark would be scoring our copy instead of the real library. If the upstream cannot be imported, the adapter reports itself unavailable.

## 8. Code And Corpus Are Licensed Separately

The code is MIT. The corpus is CC-BY-4.0. The two are distinct artifacts with distinct obligations, and contributors agree to both when they add cases or adapters.

## 9. Small, Inspectable Code; No Silent Caps

The scorer stays small enough to read in one sitting. When cases are dropped, deduped, or skipped, that is logged, not hidden. Nothing is silently truncated, capped, or sampled away behind the headline number.
