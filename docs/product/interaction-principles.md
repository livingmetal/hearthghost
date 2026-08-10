# Interaction Principles

## Product identity

HearthGhost is a character-based household companion and personal secretary. Smart-home control is one capability among many, not the primary definition of the product.

The experience should support:

- ordinary conversation
- jokes and character-driven responses
- questions and explanations
- memory-backed continuity
- calendar, reminders, notes, and assistant work
- smart-home actions when appropriate
- future perception and robot capabilities

## Conversation first

Do not force every utterance into a device-command intent.

Examples:

```text
"오늘 힘들었다."
-> conversation

"내일 일정 알려줘."
-> secretary capability

"거실 불 꺼줘."
-> explicit physical action

"좀 어둡네."
-> observation; not automatically a command
```

Ambiguous observations should prefer conversation or clarification over unwanted physical action.

## Attention before response

HearthGhost should not join unrelated household conversations or respond to television dialogue simply because speech was audible.

Default principle:

> If Ghost was not addressed, Ghost remains quiet.

After an explicit wake event, bounded natural follow-up conversation may continue without repeating the character name for every sentence.

## Proactive behavior

A companion may occasionally initiate interaction, but excessive interruption destroys the experience.

Default proactive posture is conservative:

```yaml
proactive:
  frequency: low
  interrupt_household_conversation: false
  interrupt_tv: false
  physical_action_without_request: restricted
```

Useful proactive cases may include important reminders or meaningful safety/context events. Merely detecting a person entering the room is not sufficient reason to speak every time.

## Behavior preferences

Users should be able to teach Ghost how they prefer to interact through conversation.

Examples:

- "농담 좀 더 해."
- "답을 짧게 해."
- "대화 끝난 것 같아도 조금 더 기다려."
- "별일 아니면 먼저 말 걸지 마."

The LLM interprets these requests but does not directly edit runtime files. Typed preference updates pass through the Policy Manager.

## Policy scopes

The design should support different preference scopes.

```text
Character scope
  "너는 농담을 조금 더 하는 성격으로 해."

User scope
  "나한테는 설명을 자세히 해."

Household scope
  "밤 11시 이후에는 먼저 말 걸지 마."

Security scope
  only through authorized security/admin controls
```

## Multi-user direction

Future user classes may include:

```text
administrator
household member
guest
unknown
```

Personal schedules and private memories should be distinguishable from shared household context. The first MVP may use a simpler household model, but code should avoid assuming one universal human identity forever.

## Character consistency

Persona should influence tone, humor, initiative, and conversational style, but should not override security policy or invent permissions.

Character personality is presentation and interaction behavior; authorization belongs to Policy.

## Success criterion

The first meaningful product milestone is not "the light can be turned off by voice."

A stronger criterion is:

> A person can spend several minutes naturally talking with HearthGhost, including ordinary conversation and humor, while the system remains quiet when not addressed and uses tools only when they are genuinely needed.
