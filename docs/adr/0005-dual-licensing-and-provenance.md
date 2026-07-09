# ADR 0005: Dual Licensing And Provenance

## Status

Accepted

## Context

This repo contains two different kinds of work with two different licensing needs. The scorer, adapters, and tooling are software. The corpus is data: real raw model outputs labeled with gold answers, redistributed to everyone who clones the repo. A single license fits neither well, and data that is captured rather than authored carries a real risk of containing secrets, local paths, or private source that must never be republished.

## Decision

The code is licensed MIT. The corpus is licensed CC-BY-4.0. The two licenses live in `LICENSE` and `corpus/LICENSE` respectively, and contributors agree to both.

Every contribution is made under a Developer Certificate of Origin sign-off (`git commit -s`). By signing off, the contributor attests that they have the right to share each case under CC-BY-4.0 and that the case has been sanitized of secrets, credentials, local paths, and private code. Provenance fields on each case record where the raw output came from.

## Consequences

Downstream users can reuse the code and the corpus under terms appropriate to each, with attribution for the data. The DCO gives a clear, lightweight record that each case was knowingly and lawfully contributed. The burden is on contributors to sanitize before committing, because a leak in a CC-BY-4.0 corpus is published and redistributed forever; see `SECURITY.md` for the handling process.
