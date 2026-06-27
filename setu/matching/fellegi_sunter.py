"""Fellegi-Sunter probabilistic record linkage — the explainable scorer.

For each comparison field we hold two probabilities:
  m = P(fields agree | the pair is a true match)
  u = P(fields agree | the pair is NOT a match)
The per-field "match weight" when fields AGREE is log2(m/u); when they DISAGREE
it is log2((1-m)/(1-u)). The total match weight is the sum across fields, in
bits of evidence. We convert it to a probability with a logistic on the bits.

This is exactly the model Splink fits — we implement it by hand so every weight
is inspectable and the agent's explanation is GROUNDED in real numbers, not
hallucinated. Swapping in a Splink-trained model means replacing the m/u table
below; the `score()` interface and the explanation shape stay identical.

The m/u values here are reasoned priors calibrated against the synthetic dataset
(see tests/test_cascade.py). In production they would be EM-trained by Splink.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import config
from ..schema import PersonRecord
from . import names as name_mod

# m/u priors per reliable field. CRITICAL: `u` here is P(agree | non-match) for
# pairs that ALREADY PASSED BLOCKING — not over the whole population. Blocking
# requires same-language-or-same-state, age compatibility and zone adjacency, so
# among blocked non-matches these fields agree OFTEN. That makes their `u` high
# and their per-field weight small — which is correct: in a crowd of elderly
# Bihari Maithili pilgrims, "both speak Maithili" is weak evidence. The real
# discriminators are EXACT zone, EXACT time, name, free-text and face.
#
# language and home_state are highly correlated in this population (language
# largely predicts origin state), so we deliberately give BOTH a high `u`: the
# pair must not be rewarded twice for what is essentially one regional signal.
MU = {
    "age_band":   {"m": 0.90, "u": 0.40},   # coarse bands, elderly-clustered
    "sex":        {"m": 0.97, "u": 0.50},
    "language":   {"m": 0.95, "u": 0.70},   # conditional on blocking: weak
    "home_state": {"m": 0.95, "u": 0.65},   # correlated with language: weak
    "zone_exact": {"m": 0.65, "u": 0.15},   # SAME zone (beyond adjacency): strong
    "time_close": {"m": 0.80, "u": 0.30},   # last-seen within ~2h: strong
}

# Name contributions (only applied when BOTH names present). Deliberately bounded
# so a name can sway but never dominate the reliable-field evidence.
NAME_WEIGHT_EXACT = 4.0
NAME_WEIGHT_PHONETIC = 2.5
NAME_WEIGHT_CONFLICT = -3.0  # both present but phonetically different -> evidence against


def _agree_weight(field_key: str) -> float:
    p = MU[field_key]
    return math.log2(p["m"] / p["u"])


def _disagree_weight(field_key: str) -> float:
    p = MU[field_key]
    return math.log2((1 - p["m"]) / (1 - p["u"]))


@dataclass
class WeightTerm:
    field: str
    agreed: bool
    weight: float
    reason: str


@dataclass
class MatchScore:
    total_weight: float                  # bits of evidence
    probability: float                   # logistic(total_weight)
    terms: list[WeightTerm] = field(default_factory=list)
    name_present: bool = False

    def positive_terms(self) -> list[WeightTerm]:
        return sorted([t for t in self.terms if t.weight > 0],
                      key=lambda t: -t.weight)

    def negative_terms(self) -> list[WeightTerm]:
        return sorted([t for t in self.terms if t.weight < 0],
                      key=lambda t: t.weight)


def _logistic(bits: float) -> float:
    # Map total bits of evidence to a (0,1) probability. The /2 keeps the curve
    # gentle so 6 bits ~ 0.95, matching the high-confidence threshold.
    return 1.0 / (1.0 + math.exp(-bits / 2.0))


def _time_close(a: PersonRecord, b: PersonRecord, hours: float = 2.0) -> bool | None:
    import datetime as dt

    def parse(s):
        try:
            return dt.datetime.fromisoformat(s) if s else None
        except ValueError:
            return None

    ta, tb = parse(a.last_seen_time), parse(b.last_seen_time)
    if ta is None or tb is None:
        return None
    if ta.tzinfo and not tb.tzinfo:
        tb = tb.replace(tzinfo=ta.tzinfo)
    if tb.tzinfo and not ta.tzinfo:
        ta = ta.replace(tzinfo=tb.tzinfo)
    return abs((ta - tb).total_seconds()) <= hours * 3600


def score(a: PersonRecord, b: PersonRecord) -> MatchScore:
    """Score a candidate pair on reliable fields + optional name signal.

    Returns a MatchScore whose `terms` list is a full, human-readable
    accounting of every bit of evidence — this is what the agent surfaces."""
    terms: list[WeightTerm] = []

    def add(field_key: str, agreed: bool, label_agree: str, label_disagree: str):
        w = _agree_weight(field_key) if agreed else _disagree_weight(field_key)
        terms.append(WeightTerm(field_key, agreed,
                                round(w, 3),
                                label_agree if agreed else label_disagree))

    # age_band: compatible (within slack) counts as agreement.
    age_ok = config.age_bands_compatible(a.age_band, b.age_band)
    add("age_band", age_ok,
        f"age band {a.age_band}≈{b.age_band}",
        f"age bands differ ({a.age_band} vs {b.age_band})")

    if a.sex in ("F", "M") and b.sex in ("F", "M"):
        add("sex", a.sex == b.sex,
            f"both {a.sex}", f"sex differs ({a.sex} vs {b.sex})")

    if a.language and b.language:
        add("language", a.language == b.language,
            f"both speak {a.language}", f"language differs ({a.language} vs {b.language})")

    if a.home_state and b.home_state:
        add("home_state", a.home_state == b.home_state,
            f"both from {a.home_state}", f"home state differs")

    # zone_exact is a one-sided bonus: same exact zone is extra evidence on top
    # of the adjacency that blocking already required. Adjacent-but-not-equal
    # gets no penalty (blocking already vouched for proximity).
    if a.last_seen_zone and b.last_seen_zone and a.last_seen_zone == b.last_seen_zone:
        add("zone_exact", True, f"same zone ({a.last_seen_zone})", "")

    tc = _time_close(a, b)
    if tc is not None:
        add("time_close", tc, "last seen within ~2h", "last seen hours apart")

    # --- Name signal: ONLY if both names present (name-optional invariant) ---
    name_info = name_mod.name_agreement(a.full_name, b.full_name)
    if name_info["present"]:
        if name_info["exact"]:
            terms.append(WeightTerm("name", True, NAME_WEIGHT_EXACT,
                                    f"names match exactly ({a.full_name}≈{b.full_name})"))
        elif name_info["phonetic"]:
            terms.append(WeightTerm("name", True, NAME_WEIGHT_PHONETIC,
                                    f"names phonetically equal "
                                    f"({name_info['key_a']})"))
        else:
            terms.append(WeightTerm("name", False, NAME_WEIGHT_CONFLICT,
                                    f"names differ ({a.full_name} vs {b.full_name})"))

    total = round(sum(t.weight for t in terms), 3)
    return MatchScore(
        total_weight=total,
        probability=round(_logistic(total), 4),
        terms=terms,
        name_present=name_info["present"],
    )
