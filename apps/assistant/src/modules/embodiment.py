"""Deterministic first-person guard for supported avatar gestures."""

from __future__ import annotations

import re


_SUPPORTED_GESTURE_REQUESTS = (
    re.compile(r"(?:손|팔).{0,20}(?:흔들|들어|올려)", re.IGNORECASE),
    re.compile(r"(?:오른쪽|왼쪽|우측|좌측).{0,20}(?:돌|회전)", re.IGNORECASE),
    re.compile(r"고개.{0,16}(?:끄덕|젓|저어|흔들)", re.IGNORECASE),
    re.compile(r"(?:허리|고개).{0,16}(?:숙|인사|절)", re.IGNORECASE),
    re.compile(r"(?:앞으로|뒤로|왼쪽|오른쪽|가까이|멀리).{0,20}(?:와|오|가|다가|물러|이동|옮겨|걸어)", re.IGNORECASE),
    re.compile(r"\b(?:wave|raise|turn|spin|nod|bow|move|step|come closer|step back)\b", re.IGNORECASE),
)

_DISEMBODIED_REPLY = re.compile(
    r"(?:"
    r"아바타|화면\s*속|동작을?\s*(?:제안|요청|실행시키)|"
    r"직접.{0,16}(?:못|할\s*수\s*없)|(?:몸|팔|손).{0,16}(?:없|못)|"
    r"\bavatar\b|\bclient\b|\bon-screen\s+(?:avatar|character)\b|"
    r"\b(?:cannot|can't|unable to).{0,24}(?:body|move|turn|gesture)|"
    r"\bpropos(?:e|ing).{0,24}(?:animation|gesture|movement)"
    r")",
    re.IGNORECASE,
)


def enforce_first_person_embodiment(
    user_text: str,
    response_text: str,
    *,
    formality: str = "casual",
) -> str:
    """Replace disowned-body wording only for the typed supported gesture set."""
    if not any(pattern.search(user_text) for pattern in _SUPPORTED_GESTURE_REQUESTS):
        return response_text
    if _DISEMBODIED_REPLY.search(response_text) is None:
        return response_text
    if re.search(r"[가-힣]", user_text):
        return "응, 이렇게 할게." if formality == "casual" else "네, 이렇게 할게요."
    return "Sure—like this."
