# ADR 0003: Local Docker-First Reviewer Experience

## Decision

Prioritize a local Docker-first reviewer path over a hosted cloud demo.

## Rationale

Local Docker gives reproducibility, avoids cloud credentials, and keeps reviewer instructions stable. A hosted demo can be added later, but it introduces cost, uptime, and security maintenance that do not improve the core engineering evidence as much as reliable local execution.

## Consequences

- `make demo` is the primary reviewer command.
- `.env.example` provides non-secret local defaults.
- Cloud deployment is deferred until the local path is consistently green.
