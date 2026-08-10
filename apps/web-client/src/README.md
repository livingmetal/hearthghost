# Web Client Source Boundary

The client is a presentation and node-I/O endpoint, not an execution authority.

```text
Application Shell
  |-- shared session state
  |-- visible privacy state
  |-- portrait layout
  |-- landscape layout
  `-- CharacterViewport
          |
     CharacterRenderer
       /           \
  Sprite          VRM
```

Both orientations consume the same semantic contracts and renderer-neutral
viewport. The client holds no Home Assistant or LLM provider credentials, and a
server connection alone cannot authorize camera or microphone access.

## Responsibilities

| Boundary | Responsibility |
| --- | --- |
| Application shell | Responsive portrait/landscape composition, navigation, captions, touch-to-wake, confirmations, and accessibility equivalents |
| Session state | One semantic conversation-state projection shared by both orientations and the CharacterViewport |
| Privacy presentation | Explicit text/icon presentation of camera, microphone/session, cloud-media, and node-trust state |
| Character | Renderer-neutral viewport and renderer interface, documented in `character/README.md` |

The shell remains character-first rather than becoming a Home Assistant
dashboard. Privacy UI reports policy state but cannot grant sensor or external
service access.
