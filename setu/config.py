"""SETU canonical configuration: centers, zones, languages, age bands, thresholds.

Everything that the matching cascade treats as a "reliable field" is defined here
so the design choices (driven by the real Kumbh data) live in one auditable place.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Centers (the 10 real lost-and-found / control nodes).
# Each center is an edge node holding a full replica. The `domain` is the PFIF
# record-id prefix so a record's origin is always self-describing.
# ---------------------------------------------------------------------------
CENTERS: dict[str, dict] = {
    "adgaon":          {"name": "Adgaon",                     "domain": "adgaon.setu"},
    "rajur_bahula":    {"name": "Rajur Bahula",               "domain": "rajurbahula.setu"},
    "panchavati":      {"name": "Panchavati",                 "domain": "panchavati.setu"},
    "ramkund":         {"name": "Ramkund",                    "domain": "ramkund.setu"},
    "bharat_bharati":  {"name": "Bharat Bharati Control Room","domain": "bharatbharati.setu"},
    "trimbakeshwar":   {"name": "Trimbakeshwar",              "domain": "trimbakeshwar.setu"},
    "central_control": {"name": "Central Control Room",       "domain": "central.setu"},
    "nashik_road":     {"name": "Nashik Road",                "domain": "nashikroad.setu"},
    "sadhugram":       {"name": "Sadhugram",                  "domain": "sadhugram.setu"},
    "police_control":  {"name": "Police Main Control Room",   "domain": "police.setu"},
}

# ---------------------------------------------------------------------------
# Zones + adjacency. The cascade blocks on zone-ADJACENCY (not equality) because
# an elder who went missing at Ramkund is plausibly found at Panchavati next door.
# Adjacency is an undirected graph; a zone is always adjacent to itself.
# Zones map onto the geographic areas around the centers plus the ghats.
# ---------------------------------------------------------------------------
ZONES: list[str] = [
    "ramkund", "panchavati", "tapovan", "sadhugram", "trimbakeshwar",
    "adgaon", "rajur_bahula", "nashik_road", "gangapur", "kalaram",
]

# Undirected adjacency. Kept deliberately conservative: only walking-distance
# neighbours, so blocking stays tight (good recall without exploding candidates).
_ADJACENCY: dict[str, set[str]] = {
    "ramkund":       {"panchavati", "kalaram", "gangapur"},
    "panchavati":    {"ramkund", "kalaram", "tapovan"},
    "kalaram":       {"ramkund", "panchavati"},
    "tapovan":       {"panchavati", "sadhugram"},
    "sadhugram":     {"tapovan", "adgaon"},
    "adgaon":        {"sadhugram", "nashik_road"},
    "nashik_road":   {"adgaon", "gangapur"},
    "gangapur":      {"ramkund", "nashik_road", "rajur_bahula"},
    "rajur_bahula":  {"gangapur", "trimbakeshwar"},
    "trimbakeshwar": {"rajur_bahula"},
}


def zones_adjacent(a: str, b: str) -> bool:
    """True if zones a and b are the same or walking-distance neighbours."""
    if a == b:
        return True
    return b in _ADJACENCY.get(a, set()) or a in _ADJACENCY.get(b, set())


# ---------------------------------------------------------------------------
# The 10 languages (even split in the real data). `script` is the native script
# used for PA announcements; `pa_locale` is the Bhashini locale code.
# ---------------------------------------------------------------------------
LANGUAGES: dict[str, dict] = {
    "hindi":    {"name": "Hindi",    "native": "हिन्दी",   "pa_locale": "hi-IN"},
    "bengali":  {"name": "Bengali",  "native": "বাংলা",    "pa_locale": "bn-IN"},
    "kannada":  {"name": "Kannada",  "native": "ಕನ್ನಡ",    "pa_locale": "kn-IN"},
    "maithili": {"name": "Maithili", "native": "मैथिली",   "pa_locale": "mai-IN"},
    "gujarati": {"name": "Gujarati", "native": "ગુજરાતી",  "pa_locale": "gu-IN"},
    "telugu":   {"name": "Telugu",   "native": "తెలుగు",   "pa_locale": "te-IN"},
    "bhojpuri": {"name": "Bhojpuri", "native": "भोजपुरी",  "pa_locale": "bho-IN"},
    "awadhi":   {"name": "Awadhi",   "native": "अवधी",     "pa_locale": "awa-IN"},
    "tamil":    {"name": "Tamil",    "native": "தமிழ்",    "pa_locale": "ta-IN"},
    "marathi":  {"name": "Marathi",  "native": "मराठी",    "pa_locale": "mr-IN"},
}

# ---------------------------------------------------------------------------
# Age bands. The real data is 58% elderly (61+), 11.5% children — so the bands
# are deliberately finer at the top end where most cases concentrate.
# ---------------------------------------------------------------------------
AGE_BANDS: list[str] = ["0-12", "13-17", "18-30", "31-45", "46-60", "61-75", "76+"]
CHILD_BANDS = {"0-12", "13-17"}
ELDERLY_BANDS = {"61-75", "76+"}

# Adjacent age bands can still match (intake age is an estimate for elders).
_BAND_INDEX = {b: i for i, b in enumerate(AGE_BANDS)}


def age_bands_compatible(a: str, b: str, slack: int = 1) -> bool:
    """Bands within `slack` positions are considered compatible for blocking."""
    if a not in _BAND_INDEX or b not in _BAND_INDEX:
        return False
    return abs(_BAND_INDEX[a] - _BAND_INDEX[b]) <= slack


# Indian states / UTs we draw home_state from (pan-India origins).
HOME_STATES: list[str] = [
    "Bihar", "West Bengal", "Karnataka", "Uttar Pradesh", "Gujarat",
    "Telangana", "Jharkhand", "Tamil Nadu", "Maharashtra", "Madhya Pradesh",
    "Rajasthan", "Odisha", "Assam", "Punjab", "Andhra Pradesh",
]

# Sex values used across the schema.
SEXES = ("F", "M", "U")  # U = unknown / unrecorded

# ---------------------------------------------------------------------------
# Matching thresholds (on Fellegi-Sunter total match weight, in log2 "bits").
#   >= HIGH  -> push to human verification queue
#   <  LOW   -> discard
#   between  -> keep record "warm", auto re-match on every new record
# These are tuned against the synthetic dataset; see tests/test_cascade.py.
# ---------------------------------------------------------------------------
THRESHOLD_HIGH = 6.0
THRESHOLD_LOW = 0.0

# Dedup uses a higher bar than cross-stream matching: a duplicate is the *same*
# person reported twice, so it should agree on more fields.
DEDUP_THRESHOLD = 9.0

# Default consent-driven retention for a record before auto-purge (days).
DEFAULT_RETENTION_DAYS = 30

# Face re-rank is deliberately capped low: it can only nudge an already-strong
# textual match, never create or confirm one (Rule: face is never sufficient).
FACE_MAX_WEIGHT_CONTRIBUTION = 1.5
