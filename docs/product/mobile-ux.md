# Mobile UX

## Primary client assumption

The first HearthGhost client is expected to run on an Android phone or tablet. The device may be handheld or permanently docked in a room.

The UI must therefore treat portrait and landscape as first-class layouts rather than assuming a single fixed tablet orientation.

## Shared principles

Both orientations must preserve:

- a large renderer-neutral `CharacterViewport`
- visible privacy/security state
- touch-to-wake fallback
- conversation captions or status when useful
- minimal navigation during ordinary conversation
- no renderer-specific assumptions in the application shell

The UI should feel like interacting with a character, not operating a wall-mounted monitoring dashboard.

## Portrait mode

Primary use:

```text
handheld phone/tablet
personal interaction
close conversation
```

Preferred information hierarchy:

```text
Top      -> identity + privacy indicator
Center   -> CharacterViewport
Bottom   -> conversation status / caption / primary interaction
Secondary information -> below or in drawers/sheets
```

Character presentation should dominate the screen. Context panels and smart-home controls should not permanently squeeze the character into a small card.

## Landscape mode

Primary use:

```text
docked living-room tablet
always-visible household companion
character + selected context
```

Preferred information hierarchy:

```text
Left / center -> CharacterViewport
Edge / side   -> privacy, schedule, context, optional quick actions
Bottom        -> caption / interaction
```

Landscape may show more passive context than portrait, but the character remains the visual anchor.

## Orientation preference

The client should eventually support:

```text
Auto
Portrait locked
Landscape locked
```

This allows a living-room tablet to remain docked in landscape while a spare phone may be configured vertically.

## Character renderer neutrality

The viewport must support both:

- 2D sprite/animation renderers, including assets produced by tools such as PNGAL
- VRM 3D characters

UI cards, captions, buttons, and side panels should stay near edges and avoid assuming where a particular avatar's face or body will be.

## Privacy visibility

At a glance, users should be able to understand security-sensitive states such as:

```text
camera disabled / active
microphone local-only / active conversation session
cloud media blocked / explicitly enabled
node trust state
```

A privacy indicator should remain visible in ordinary UI, with more detailed explanation available through a dedicated Privacy Shield screen.

## Interaction states

The UI should visually distinguish at least:

```text
sleeping
listening
thinking
speaking
engaged
```

These are conversation states, not character emotions. Emotion is rendered separately by the CharacterRenderer.

## Touch interaction

Voice is primary, but touch remains a deliberate fallback for:

- wake / start conversation
- dismiss / stop
- privacy status
- explicit confirmations
- settings and device administration

Critical confirmations should not rely solely on subtle character animation.

## Accessibility and motion

Do not require animation to understand security or conversation state. Text/icon equivalents should exist. Respect reduced-motion preferences where practical.

## Avoid dashboard creep

Do not place every available Home Assistant entity, sensor value, device status, and system metric on the main screen. Detailed administration belongs in secondary views. The primary screen is a character interaction surface.
