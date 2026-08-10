# Node Enrollment and Administration Boundary

## Purpose

HG-003 adds a privileged registry mutation boundary while preserving:

```text
Node credential authenticated
  != Node enrolled
  != Node trusted
  != capability granted
  != Policy-approved action
  != node-local sensor permission
```

The boundary performs no networking, administrator login, persistence, or
device execution. Those implementations remain behind explicit ports.

## Enrollment and trust

Enrollment is an explicit administrator action. It creates revision `1` with:

```text
trust_state = untrusted
granted_capabilities = empty
```

An authenticated Node or discovered device cannot invoke enrollment as an
administrator. Trust requires a separate action-specific authorization and a
matching expected revision. Node revocation is terminal in HG-003: the boundary
does not provide an un-revoke convenience path.

## Capability grants

Advertisements and grants remain independent. A grant is accepted only when the
Node currently advertises the capability and an administrator is specifically
authorized for `node.capability.grant`. Revocation of a grant remains possible
even after a Node stops advertising it.

A grant changes registry state only. It is not current Policy approval, Tool
execution permission, a device command, or a node-local camera/microphone allow.

## Revisions and idempotency

Every command carries:

```text
operation_id
correlation_id
node_id
action
expected_revision
```

Enrollment expects revision `0`; later mutations expect the current positive
revision. The storage adapter must compare and update the revision atomically.
A stale revision is a conflict and makes no state or audit change.

`operation_id` is the idempotency key. Retrying the identical authorized command
returns the stored result without a second revision or audit event. Reusing the
same operation ID with different content is a conflict. Desired-state requests
that are already satisfied are successful no-ops and do not increment revision.

## Audit atomicity

Every actual privileged change produces metadata compatible with audit-event
v1, including a trusted timestamp, correlation ID, administrator ID, action,
Node ID, and optional capability. It contains no credential proof, key, token,
or private household content.

The administration storage port owns one atomic operation covering:

```text
idempotency check
  + expected revision check
  + Node state update
  + audit event persistence
```

If durable audit cannot be written, state must not change. A later datastore may
implement this with one transaction or a transactional outbox, but HG-003 does
not select that technology.

The runtime registry adapter must project committed administration trust and
grant state into the `NodeRepository` view used by the Node Gateway. It must not
maintain a permissive second copy that can drift from the revisioned
administration record.

## Deferred work

- administrator identity provider and login/session mechanism;
- persistent Node registry, idempotency, and audit implementation;
- enrollment recovery and credential issuance workflow;
- binding registry state into a network transport adapter;
- Policy evaluation and action execution;
- node-local camera/microphone authorization.
