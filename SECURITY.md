# Security

The security boundary in `toolcall-repair-bench` is data, not network. The scorer runs offline with no network and no GPU, so there is little to attack there. The real risk is the corpus: it is made of captured model outputs, and a captured output can carry whatever was in the model's context when it was produced.

## What A Case May Contain

A case is a real raw model output. If that output was captured from real work, it can embed things that have no business being public:

- Local filesystem paths that reveal a machine, a user, or a project layout.
- Credentials, API keys, or tokens the model echoed back.
- Private or proprietary source code the model was reasoning over.
- Internal hostnames, URLs, or identifiers.

None of this is hypothetical. Models repeat their input, and tool-call attempts often quote it.

## Sanitization Is Mandatory

Every case is sanitized before it is committed: secrets, credentials, local paths, and private code removed, with provenance still recorded. This is a precondition for inclusion, not a follow-up task.

**Treat every committed case as PUBLISHED FOREVER.** The corpus is redistributed under CC-BY-4.0 to everyone who clones the repo, and it lives in git history. A leak cannot be quietly deleted later. If you are unsure whether a case is clean, do not commit it.

## Reporting A Case That Leaks Data

If you find a case that contains secrets, credentials, private code, or other sensitive data, report it privately to the repo owner. **Do not open a public issue that quotes the leak**, and do not paste the sensitive content into a comment or pull request; that only spreads it further.

The maintainer will scrub the case, rewrite history where needed, and re-tag the affected corpus release. Quiet, private reporting is what limits the damage.
