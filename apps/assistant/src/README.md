# Assistant Source Boundary

The assistant remains one deployable modular monolith unless a documented need
creates a stronger isolation boundary.

```text
inbound adapters / node gateway
             |
        conversation
             |
        orchestrator
       /     |      \
  memory   policy   registry
             |
        tool proposal
             |
      policy decision
             |
          executor
             |
      outbound adapter
```

`modules/` owns domain behavior. `ports/` will own interfaces required by domain
code. `adapters/` will translate external provider or product APIs to those
ports. Domain modules must not import provider implementations.

No module may treat an LLM proposal as permission to execute. Sensitive actions
require a valid allow decision; an unavailable or malformed decision is denial.
