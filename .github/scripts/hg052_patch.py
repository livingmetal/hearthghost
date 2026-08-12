from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    if old not in content:
        raise RuntimeError(f"missing patch anchor in {path}: {old[:120]!r}")
    write(path, content.replace(old, new, 1))


# CharacterExperience exposes only semantic emotion, not renderer values.
replace_once(
    "apps/web-client/src/character/experience.ts",
    '''  performGestures(gestures: readonly CharacterGesture[]): void {\n    for (const gesture of gestures) {\n      this.performGesture(gesture);\n    }\n  }\n\n  wakeByTouch(): void {\n''',
    '''  performGestures(gestures: readonly CharacterGesture[]): void {\n    for (const gesture of gestures) {\n      this.performGesture(gesture);\n    }\n  }\n\n  express(emotion: CharacterEmotion): void {\n    this.setEmotion(emotion);\n  }\n\n  wakeByTouch(): void {\n''',
)

# Response reveal publishes monotonic visible-text progress for the dialogue performance timeline.
replace_once(
    "apps/web-client/src/response-reveal.ts",
    '''import {\n  RESPONSE_REVEAL_DONE_EVENT,\n  RESPONSE_REVEAL_START_EVENT,\n  type ResponseRevealDetail,\n} from "./character/performance-events.js";\n''',
    '''import {\n  RESPONSE_REVEAL_DONE_EVENT,\n  RESPONSE_REVEAL_PROGRESS_EVENT,\n  RESPONSE_REVEAL_START_EVENT,\n  type ResponseRevealDetail,\n  type ResponseRevealProgressDetail,\n} from "./character/performance-events.js";\n''',
)
replace_once(
    "apps/web-client/src/response-reveal.ts",
    '''export { RESPONSE_REVEAL_DONE_EVENT, RESPONSE_REVEAL_START_EVENT };\nexport type { ResponseRevealDetail };\n''',
    '''export {\n  RESPONSE_REVEAL_DONE_EVENT,\n  RESPONSE_REVEAL_PROGRESS_EVENT,\n  RESPONSE_REVEAL_START_EVENT,\n};\nexport type { ResponseRevealDetail, ResponseRevealProgressDetail };\n''',
)
replace_once(
    "apps/web-client/src/response-reveal.ts",
    '''  private activeUtteranceId: string | null = null;\n  private hasSpeechRange = false;\n''',
    '''  private activeUtteranceId: string | null = null;\n  private hasSpeechRange = false;\n  private lastProgressEnd = 0;\n''',
)
replace_once(
    "apps/web-client/src/response-reveal.ts",
    '''      this.activeUtteranceId = null;\n      this.hasSpeechRange = false;\n      this.host?.setAttribute("aria-busy", "false");\n''',
    '''      this.activeUtteranceId = null;\n      this.hasSpeechRange = false;\n      this.lastProgressEnd = 0;\n      this.host?.setAttribute("aria-busy", "false");\n''',
)
replace_once(
    "apps/web-client/src/response-reveal.ts",
    '''    this.fullText = text.trim();\n    this.offsets = graphemeOffsets(this.fullText);\n    this.fallbackIndex = 0;\n''',
    '''    this.fullText = text.trim();\n    this.offsets = graphemeOffsets(this.fullText);\n    this.fallbackIndex = 0;\n    this.lastProgressEnd = 0;\n''',
)
replace_once(
    "apps/web-client/src/response-reveal.ts",
    '''    this.hostObserver.disconnect();\n    this.host.textContent = text;\n    this.observeHost();\n''',
    '''    this.hostObserver.disconnect();\n    this.host.textContent = text;\n    this.observeHost();\n    if (this.fullText !== "" && text.length > this.lastProgressEnd) {\n      this.lastProgressEnd = text.length;\n      window.dispatchEvent(new CustomEvent<ResponseRevealProgressDetail>(\n        RESPONSE_REVEAL_PROGRESS_EVENT,\n        { detail: { text: this.fullText, end: text.length } },\n      ));\n    }\n''',
)

# Shared Android/web entry installs one performance timeline and lets reveal completion own speaking -> engaged.
replace_once(
    "apps/web-client/src/main.ts",
    '''import { CharacterExperienceController } from "./character/experience.js";\n''',
    '''import { DialoguePerformanceController } from "./character/dialogue-performance.js";\nimport { CharacterExperienceController } from "./character/experience.js";\n''',
)
replace_once(
    "apps/web-client/src/main.ts",
    '''const character = new CharacterExperienceController(viewport);\nconst conversation = androidPlatform === null\n''',
    '''const character = new CharacterExperienceController(viewport);\nconst dialoguePerformance = new DialoguePerformanceController(character);\ndialoguePerformance.install();\nconst conversation = androidPlatform === null\n''',
)
replace_once(
    "apps/web-client/src/main.ts",
    '''    character.beginSpeaking();\n    await voiceOutput.speak(text, VOICE_LOCALE, voiceProfile);\n    character.engage();\n    showSnapshot();\n''',
    '''    await voiceOutput.speak(text, VOICE_LOCALE, voiceProfile);\n    showSnapshot();\n''',
)
replace_once(
    "apps/web-client/src/main.ts",
    '''      if (response !== null) {\n        response.textContent = reply;\n      }\n      character.engage();\n      if (notice !== null) {\n''',
    '''      if (response !== null) {\n        response.textContent = reply;\n      }\n      if (reply === "") {\n        character.engage();\n      }\n      if (notice !== null) {\n''',
)
replace_once(
    "apps/web-client/src/main.ts",
    '''        const spoken = reply !== "" && await speakReplyLocally(reply);\n        if (!spoken) {\n          character.engage();\n        }\n''',
    '''        const spoken = reply !== "" && await speakReplyLocally(reply);\n        if (!spoken && reply === "") {\n          character.engage();\n        }\n''',
)
replace_once(
    "apps/web-client/src/main.ts",
    '''window.addEventListener("pagehide", () => {\n  window.clearInterval(attentionTimer);\n  clearSessionHistory();\n''',
    '''window.addEventListener("pagehide", () => {\n  window.clearInterval(attentionTimer);\n  dialoguePerformance.dispose();\n  clearSessionHistory();\n''',
)

# Windows shares the exact same local timeline instead of a separate reveal-done state hook.
replace_once(
    "apps/web-client/src/windows-main.ts",
    '''import { CharacterExperienceController } from "./character/experience.js";\n''',
    '''import { DialoguePerformanceController } from "./character/dialogue-performance.js";\nimport { CharacterExperienceController } from "./character/experience.js";\n''',
)
replace_once(
    "apps/web-client/src/windows-main.ts",
    '''import {\n  RESPONSE_REVEAL_DONE_EVENT,\n  type ResponseRevealDetail,\n} from "./response-reveal.js";\n''',
    '''import "./response-reveal.js";\n''',
)
replace_once(
    "apps/web-client/src/windows-main.ts",
    '''const character = new CharacterExperienceController(viewport);\nconst conversation = new TextConversationController(\n''',
    '''const character = new CharacterExperienceController(viewport);\nconst dialoguePerformance = new DialoguePerformanceController(character);\ndialoguePerformance.install();\nconst conversation = new TextConversationController(\n''',
)
replace_once(
    "apps/web-client/src/windows-main.ts",
    '''    historyView.render(history.append("assistant", reply));\n    character.beginSpeaking();\n    response.textContent = reply;\n''',
    '''    historyView.render(history.append("assistant", reply));\n    response.textContent = reply;\n''',
)
old_listener = '''\nconst onResponseRevealDone = (event: CustomEvent<ResponseRevealDetail>): void => {\n  if (\n    viewport.snapshot().state === "speaking"\n    && response.textContent?.trim() === event.detail.text.trim()\n  ) {\n    character.engage();\n  }\n};\nwindow.addEventListener(RESPONSE_REVEAL_DONE_EVENT, onResponseRevealDone as EventListener);\n'''
replace_once("apps/web-client/src/windows-main.ts", old_listener, "\n")
replace_once(
    "apps/web-client/src/windows-main.ts",
    '''window.addEventListener("pagehide", () => {\n  window.removeEventListener(RESPONSE_REVEAL_DONE_EVENT, onResponseRevealDone as EventListener);\n  history.clear();\n''',
    '''window.addEventListener("pagehide", () => {\n  dialoguePerformance.dispose();\n  history.clear();\n''',
)

# Include pure dialogue performance tests in the packaged no-network client test run.
replace_once(
    "apps/web-client/package.json",
    '''tests/vrm-expression-composer.test.mjs tests/presence-performance.test.mjs tests/conversation-controller.test.mjs''',
    '''tests/vrm-expression-composer.test.mjs tests/presence-performance.test.mjs tests/dialogue-performance.test.mjs tests/conversation-controller.test.mjs''',
)
