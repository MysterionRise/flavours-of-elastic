# ADR 0008: Stack Registry and a Dual-Track Course

Status: accepted
Date: 2026-10

## Decision

`scripts/stacks.py` is the single source of truth for the Docker stacks (compose file, URL, credentials,
version variable, licence, capabilities, course days). Validation, the CI matrix, `scripts.with_stack` and the
data loader's `--stack` all read it, and tooling runs stacks in isolated `foe-<purpose>-<stack>` projects. The
course runs on two tracks: Elasticsearch 8.19 (`elk-single`, `elk-ml`) and 9.5 (`elk-9`, `elk-ml-9`), and CI
executes every Dev Tools snippet of every day on both (`tests/course/`).

## Rationale

- 8.19 is supported until 2027-07; many students' employers run it, while 9.x is the future. Teaching one track
  would leave half the audience with examples that behave differently at work.
- Duplicated bash in CI and validation drifted from the compose files; one registry removes the duplication.
- Isolated compose projects keep tooling away from students' own stacks and data.

## Consequences

- Course snippets must pass on both tracks; real differences are taught explicitly (`track=` annotations,
  `> **`9.x`**` callouts), e.g. vector `_source` exclusion and default quantization.
- Docs cite minor versions only (`8.19.x`, `9.5.x`); exact versions live in `.env.example`, enforced
  by `scripts/check_doc_versions.py`.
- A new stack is one registry entry plus a compose file; CI picks it up automatically.
