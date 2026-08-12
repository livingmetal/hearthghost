from apps.assistant.src.modules.orchestrator import HEARTHGHOST_INSTRUCTIONS


def test_prompt_describes_supported_visible_avatar_gestures_without_device_authority():
    prompt = HEARTHGHOST_INSTRUCTIONS

    assert "visible on-screen avatar" in prompt
    assert "raise either hand" in prompt
    assert "turn left or right once" in prompt
    assert "Do not say that you lack arms" in prompt
    assert "Prefer a short natural acknowledgement" in prompt
    assert "Do not claim real-world physical movement" in prompt
    assert "pending Policy" in prompt
