from apps.assistant.src.modules.embodiment import enforce_first_person_embodiment


def test_supported_gesture_disembodiment_is_replaced_with_first_person_reply():
    response = enforce_first_person_embodiment(
        "오른쪽으로 90도 돌아봐",
        "내가 직접 몸을 돌리진 못하지만, 화면 속 아바타를 오른쪽으로 돌리는 동작을 제안할게.",
    )

    assert response == "응, 이렇게 할게."
    assert "아바타" not in response
    assert "제안" not in response


def test_natural_first_person_gesture_reply_is_preserved():
    response = "응, 오른쪽으로 돌아볼게."

    assert enforce_first_person_embodiment("오른쪽으로 돌아봐", response) == response


def test_guard_respects_non_casual_formality():
    assert enforce_first_person_embodiment(
        "고개를 끄덕여봐",
        "화면 속 아바타의 동작을 제안할게요.",
        formality="formal",
    ) == "네, 이렇게 할게요."


def test_guard_does_not_rewrite_unrelated_conversation():
    response = "게임 아바타 설정을 설명해 줄게."

    assert enforce_first_person_embodiment("아바타가 뭐야?", response) == response


def test_english_supported_gesture_uses_first_person_fallback():
    assert enforce_first_person_embodiment(
        "move closer",
        "I cannot move, but I can propose an avatar animation.",
    ) == "Sure—like this."
