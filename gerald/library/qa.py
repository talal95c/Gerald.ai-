from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import urllib.request

from gerald import USER_AGENT
from gerald.library.search import Hit

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[Hit]


def _profile_text(profile) -> str:
    if profile is None:
        return "No learner profile is available."
    if isinstance(profile, dict):
        name = profile.get("name", "")
        level = profile.get("level")
        subjects = profile.get("subjects", [])
    else:
        name = profile.name
        level = profile.level
        subjects = profile.subjects
    lines = [f"Name: {name}"]
    if level:
        lines.append(f"Level: {level}")
    if subjects:
        lines.append(f"Subjects: {', '.join(subjects)}")
    return "\n".join(lines)


def answer(
    question: str,
    hits: list[Hit],
    history: list[dict],
    profile,
    api_key: str,
    model: str | None = None,
) -> Answer:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    selected_model = (model or os.getenv("GERALD_CHAT_MODEL") or "gpt-5.4-mini").strip()
    system_text = (
        "You are a patient tutor. Answer in the user's language and adapt explanations "
        "to the learner's level. Use numbered document sources only when relevant and "
        "cite them inline as [1], [2], etc. Say clearly when the documents do not cover "
        "the question; you may then answer from general knowledge, explicitly labeled "
        "as general knowledge. Never invent source citations.\n\n"
        "LEARNER PROFILE\n"
        f"{_profile_text(profile)}"
    )
    messages = [
        {
            "role": item["role"],
            "content": item["text"],
        }
        for item in history[-10:]
        if item.get("role") in {"user", "assistant"} and isinstance(item.get("text"), str)
    ]
    source_lines = []
    for index, hit in enumerate(hits, start=1):
        page = f", page {hit.page}" if hit.page is not None else ""
        source_lines.append(
            f"[{index}] {hit.document}{page} (course: {hit.course_title}): {hit.text}"
        )
    source_text = "\n\n".join(source_lines) if source_lines else "No document passages were found."
    messages.append(
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                "Relevant passages from the learner's documents:\n"
                f"{source_text}"
            ),
        }
    )
    payload = {
        "model": selected_model,
        "instructions": system_text,
        "input": messages,
    }
    if selected_model.casefold().startswith("gpt-5"):
        payload["reasoning"] = {"effort": "low"}
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read())
    text = "".join(
        part.get("text", "")
        for item in result.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str)
    ).strip()
    cited_numbers = {
        int(number)
        for number in re.findall(r"\[(\d+)\]", text)
        if 1 <= int(number) <= len(hits)
    }
    cited_sources = [hit for index, hit in enumerate(hits, start=1) if index in cited_numbers]
    return Answer(text, cited_sources)
