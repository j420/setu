"""Name handling: transliteration + Indic phonetic key.

CRITICAL DESIGN RULE: a name is a *signal*, never a *gate*. 15% of real cases
have no name at all, and names arrive in 10 scripts, romanised inconsistently
(Sita / Seeta / Sitadevi). So:

  * blocking NEVER uses the name (see blocking.py);
  * the cascade calls `name_agreement()` only when BOTH records have a name;
  * the result raises or lowers the Fellegi-Sunter score, it cannot create or
    veto a match on its own.

Two steps, mirroring the production stack:
  1. Transliterate any Indic-script name to a Latin form. Production uses
     AI4Bharat IndicXlit; here `transliterate()` is a labelled mock that applies
     a deterministic Devanagari/common-script -> Latin map. The CONTRACT
     (str in native script -> romanised str) matches IndicXlit so it can be
     swapped in directly.
  2. Reduce the romanised name to an Indic phonetic key — a Soundex-style code
     tuned for Indian names (collapses aa/a, v/w, retroflex/dental t/d, drops
     trailing honorifics like 'devi'/'kumar'). Two names with the same key are
     phonetically equivalent.
"""

from __future__ import annotations

import re

# --- Step 1: transliteration (IndicXlit-contract mock) ---------------------
# Minimal Devanagari->Latin table. Real IndicXlit covers all 10 scripts; this
# covers the demo's Devanagari-family names and is clearly labelled MOCK.
_DEVANAGARI_MAP = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ं": "n", "ः": "h",
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "च": "ch", "छ": "chh",
    "ज": "j", "झ": "jh", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
    "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y",
    "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s",
    "ह": "h", "ळ": "l", "क्ष": "ksh", "ज्ञ": "gy",
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "े": "e",
    "ै": "ai", "ो": "o", "ौ": "au", "ृ": "ri", "्": "",
}


def transliterate(name: str) -> str:
    """MOCK of AI4Bharat IndicXlit. Native-script name -> romanised lowercase.
    Latin input passes through unchanged. Contract matches IndicXlit exactly."""
    if not name:
        return ""
    if name.isascii():
        return name.strip().lower()
    out = []
    for ch in name:
        out.append(_DEVANAGARI_MAP.get(ch, ch if ch.isascii() else ""))
    return "".join(out).strip().lower()


# --- Step 2: Indic phonetic key --------------------------------------------
# Honorifics / common suffixes that carry no identifying signal for matching.
_HONORIFICS = {
    "devi", "kumar", "kumari", "bai", "ben", "lal", "ji", "das", "ram",
    "singh", "khan", "begum", "shri", "smt", "sri",
}

# Phonetic folding rules applied in order to the romanised string.
_FOLD = [
    (r"[^a-z]", ""),       # strip non-letters
    (r"aa+", "a"), (r"ee+", "i"), (r"oo+", "u"),  # long vowels -> short
    (r"ph", "f"), (r"bh", "b"), (r"gh", "g"), (r"dh", "d"),
    (r"th", "t"), (r"kh", "k"), (r"chh", "c"), (r"ch", "c"),
    (r"sh", "s"), (r"v", "w"),                     # v/w merge
    (r"(.)\1+", r"\1"),                            # collapse doubles
]


def phonetic_key(name: str) -> str:
    """Soundex-style key for an (already transliterated) Indian name.
    Strips honorifics, folds common variant spellings, keeps a vowel-skeleton."""
    roman = transliterate(name)
    # Drop honorific tokens, then concatenate remaining tokens.
    tokens = [t for t in re.split(r"\s+", roman) if t and t not in _HONORIFICS]
    s = "".join(tokens) if tokens else roman.replace(" ", "")
    for pat, rep in _FOLD:
        s = re.sub(pat, rep, s)
    # Retroflex/dental t and d already merged above; final key is the folded
    # consonant+vowel skeleton, truncated for stability.
    return s[:8]


def name_agreement(name_a: str | None, name_b: str | None) -> dict:
    """Compare two (optional) names. Returns a dict the scorer can fold in:
      {present, exact, phonetic, key_a, key_b}
    `present` is False when either name is missing — the scorer then applies NO
    name adjustment at all (name-optional invariant)."""
    if not name_a or not name_b:
        return {"present": False, "exact": False, "phonetic": False,
                "key_a": None, "key_b": None}
    ra, rb = transliterate(name_a), transliterate(name_b)
    ka, kb = phonetic_key(name_a), phonetic_key(name_b)
    return {
        "present": True,
        "exact": ra == rb and ra != "",
        "phonetic": ka == kb and ka != "",
        "key_a": ka,
        "key_b": kb,
    }
