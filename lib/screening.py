"""Prolific eligibility 사전 스크리닝 프리셋."""

from __future__ import annotations


SCREENING_PRESETS: dict[str, list[dict]] = {
    "korean_speakers": [
        {"category": "country", "values": ["KR"]},
        {"category": "first_language", "values": ["ko"]},
    ],
    "korean_workers": [
        {"category": "country", "values": ["KR"]},
        {"category": "first_language", "values": ["ko"]},
        {"category": "employment_status", "values": ["full_time", "part_time"]},
    ],
    "us_english_speakers": [
        {"category": "country", "values": ["US"]},
        {"category": "first_language", "values": ["en"]},
    ],
    "japanese_speakers": [
        {"category": "country", "values": ["JP"]},
        {"category": "first_language", "values": ["ja"]},
    ],
}


def build_eligibility(
    preset: str | None,
    custom_filters: list[dict],
) -> list[dict]:
    """프리셋 + 커스텀 필터 합쳐 Prolific eligibility_requirements 형식."""
    out: list[dict] = []
    if preset:
        if preset not in SCREENING_PRESETS:
            raise ValueError(
                f"알 수 없는 프리셋: '{preset}'. "
                f"허용: {list(SCREENING_PRESETS)}"
            )
        out.extend(SCREENING_PRESETS[preset])
    if custom_filters:
        out.extend(custom_filters)
    return out
