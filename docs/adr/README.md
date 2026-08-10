# Architecture Decision Records

Use this directory for decisions that intentionally change or lock important architecture, security, privacy, runtime, or dependency choices.

An ADR is appropriate when a decision would be costly or risky to reverse, especially for:

- node authentication model
- cloud media processing
- continuous camera or microphone streaming
- Hard Policy design
- critical physical capabilities
- new inbound network listeners
- new datastores or service boundaries
- renderer architecture changes
- major runtime/platform dependencies
- breaking contract changes

Suggested filename:

```text
0001-short-decision-title.md
```

Suggested structure:

```markdown
# ADR-0001: Title

## Status
Proposed | Accepted | Superseded

## Context
What problem or constraint requires a decision?

## Decision
What are we choosing?

## Consequences
What becomes easier, harder, safer, or more constrained?

## Alternatives considered
What other options were considered and why were they not selected?

## Security / Privacy impact
What trust boundary, data flow, capability, or attack surface changes?
```

Do not use ADRs for trivial implementation details that can be changed locally without affecting system contracts or trust boundaries.
