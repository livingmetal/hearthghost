from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    content = target.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"missing anchor in {path}: {old[:120]!r}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    "apps/web-client/src/main.ts",
    '''      await voiceOutput?.stop();\n      character.beginListening();\n      await voiceInput.start(VOICE_LOCALE);\n''',
    '''      await voiceOutput?.stop();\n      dialoguePerformance.cancel();\n      if (response !== null) response.textContent = "";\n      character.beginListening();\n      await voiceInput.start(VOICE_LOCALE);\n''',
)

replace_once(
    "apps/web-client/src/main.ts",
    '''      await ensureConversationCharacter();\n      character.beginThinking();\n      const snapshot = await conversation.submit(submittedText);\n''',
    '''      await ensureConversationCharacter();\n      if (response !== null) response.textContent = "";\n      dialoguePerformance.beginUserTurn(submittedText);\n      const snapshot = await conversation.submit(submittedText);\n''',
)

replace_once(
    "apps/web-client/src/main.ts",
    '''      voiceStatus = voiceStatus === null ? null : { ...voiceStatus, listening: false };\n      character.beginThinking();\n      try {\n        await ensureConversationCharacter();\n        const snapshot = await voiceConversation.acceptTranscript(event);\n''',
    '''      voiceStatus = voiceStatus === null ? null : { ...voiceStatus, listening: false };\n      try {\n        await ensureConversationCharacter();\n        if (response !== null) response.textContent = "";\n        dialoguePerformance.beginUserTurn(event.text);\n        const snapshot = await voiceConversation.acceptTranscript(event);\n''',
)

replace_once(
    "apps/web-client/src/main.ts",
    '''  character.sleep();\n  clearSessionHistory();\n  showSnapshot();\n''',
    '''  dialoguePerformance.cancel();\n  character.sleep();\n  clearSessionHistory();\n  showSnapshot();\n''',
)

replace_once(
    "apps/web-client/src/main.ts",
    '''  if (document.visibilityState === "hidden") {\n    attention.sleep();\n    character.sleep();\n''',
    '''  if (document.visibilityState === "hidden") {\n    attention.sleep();\n    dialoguePerformance.cancel();\n    character.sleep();\n''',
)

replace_once(
    "apps/web-client/src/windows-main.ts",
    '''  response.textContent = "";\n  await ensureConversationOpen();\n  character.beginThinking();\n  const snapshot = await conversation.submit(normalized);\n''',
    '''  dialoguePerformance.cancel();\n  response.textContent = "";\n  await ensureConversationOpen();\n  dialoguePerformance.beginUserTurn(normalized);\n  const snapshot = await conversation.submit(normalized);\n''',
)
