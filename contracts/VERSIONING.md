# Contract Versioning

## Compatibility rule

- `v1` is the major contract family; the schemas currently accept the immutable
  initial revision `contract_version: "1.0"`.
- A future compatible minor revision is published alongside the prior revision
  in the same major family and receives a distinct schema identifier. Existing
  revision shapes are not silently rewritten.
- Unknown properties are rejected. This is deliberate for security-sensitive
  input: forward compatibility requires explicit version negotiation and a
  coordinated consumer update, not permissive parsing.
- Adding an optional field or enum value therefore requires a new minor revision,
  consumer review, and contract validation updates.
- Removing or renaming a field, changing its meaning, or tightening accepted
  input requires a new major directory.
- Schema, documentation, fixtures, and tests change together.

## Boundary rule

Adapters translate provider and vendor payloads into these contracts. Provider
objects must not become public contracts. A tool proposal remains untrusted
input until Policy returns an explicit allow decision; missing or invalid policy
results are interpreted as denial by future execution code.

JSON event messages carry metadata and references only. Raw or Base64-encoded
media does not belong in generic event payloads.
