"""Bhashini ASR/TTS adapter — voice intake and PA output across 10 languages.

Voice is the primary interface: 58% of cases are elderly, many non-literate and
not speaking the local language. Intake and output must be spoken.

This is a MOCK against the real Bhashini API contract. The real service exposes a
pipeline endpoint that takes {sourceLanguage, audio|text, task: asr|tts} and
returns {text} or {audioContent}. The functions below mirror that shape exactly,
so wiring a live key means replacing the bodies, not the call sites. When no key
is configured we (a) for ASR, return a pre-canned transcript keyed to a clip id,
and (b) for TTS, return a deterministic pseudo-audio descriptor. Everything is
clearly labelled MOCK.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from . import config

BHASHINI_API_KEY = os.environ.get("BHASHINI_API_KEY")  # absent in the demo
LIVE = bool(BHASHINI_API_KEY)

# Pre-recorded clip transcripts for the demo (clip_id -> (language, transcript)).
# These stand in for real audio the way the hackathon brief allows.
_CLIP_LIBRARY = {
    "sita_intake_maithili": (
        "maithili",
        "हमर सासु हेरा गेली अछि। उमेर करीब अड़सठ बरख। रामकुंड लग देखने रही, "
        "करीब चालीस मिनट पहिने। बिहार सँ छी।",
        # gloss: "My mother-in-law is lost. Age about 68. Last seen near Ramkund,
        #         about 40 minutes ago. We are from Bihar."
    ),
    "son_search_maithili": (
        "maithili",
        "हम अपन माय के तकैत छी। ओ मैथिली बजैत छथि, बिहार सँ। पंचवटी मे छी।",
    ),
}


@dataclass
class ASRResult:
    language: str
    transcript: str
    is_mock: bool
    confidence: float


@dataclass
class TTSResult:
    language: str
    pa_locale: str
    text: str
    audio_ref: str         # path/descriptor of synthesised audio
    is_mock: bool


def asr(*, audio_clip_id: str, source_language: str | None = None) -> ASRResult:
    """Speech-to-text. Contract mirrors Bhashini ASR task.
    In the demo, resolves a pre-recorded clip id to its transcript."""
    if LIVE:  # pragma: no cover - needs a live key
        raise NotImplementedError("wire live Bhashini ASR pipeline here")
    if audio_clip_id in _CLIP_LIBRARY:
        lang, text = _CLIP_LIBRARY[audio_clip_id][0], _CLIP_LIBRARY[audio_clip_id][1]
        return ASRResult(language=lang, transcript=text, is_mock=True, confidence=0.94)
    return ASRResult(
        language=source_language or "hindi",
        transcript="[MOCK ASR: no clip registered for this id]",
        is_mock=True, confidence=0.0,
    )


def tts(*, text: str, language: str) -> TTSResult:
    """Text-to-speech. Contract mirrors Bhashini TTS task.
    In the demo, returns a deterministic pseudo-audio reference."""
    lang = language if language in config.LANGUAGES else "hindi"
    locale = config.LANGUAGES[lang]["pa_locale"]
    if LIVE:  # pragma: no cover
        raise NotImplementedError("wire live Bhashini TTS pipeline here")
    digest = hashlib.sha1(f"{locale}:{text}".encode("utf-8")).hexdigest()[:10]
    return TTSResult(
        language=lang, pa_locale=locale, text=text,
        audio_ref=f"mock-audio://{locale}/{digest}.wav", is_mock=True,
    )
