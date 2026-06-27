"""Synthetic Kumbh case generator — SYNTHETIC DATA, clearly labelled.

The hackathon's real 2,500-case dataset is not bundled here. This generator
produces a synthetic stand-in that reproduces the distributions the real data
proves, because those distributions drive every design choice:

  * 58% elderly (61+), 11.5% children, rest working-age
  * 10 languages in an even split
  * 15% of records carry NO name
  * 8% duplicate reports (same person logged at two centers)
  * pan-India home states, last seen across the zone graph
  * physical_description present but NOISY/low-trust (quarantined downstream)

It also plants a controllable number of TRUE missing<->found pairs so the
cascade has correct answers to find (including no-name pairs). Deterministic
under a fixed seed for reproducible demos and tests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
from dataclasses import dataclass, field

from setu import config
from setu.schema import RECORD_FOUND, RECORD_MISSING, PersonRecord, new_id
from setu.store import Store


@dataclass
class Dataset:
    """Generated records plus GROUND TRUTH kept strictly OUT of the matching path
    (so metrics can be measured honestly, never asserted).

      records       : list of (center_key, PersonRecord)
      truth         : person_record_id -> truth_group_id (same group == same
                      real person; links true missing<->found pairs and dupes)
      duplicate_ids : person_record_ids that are redundant duplicate reports
    """
    records: list = field(default_factory=list)
    truth: dict = field(default_factory=dict)
    duplicate_ids: set = field(default_factory=set)

# Small per-language name pools (native + a couple of romanised variants) so the
# transliteration/phonetic path has realistic material. SYNTHETIC.
_NAMES = {
    "maithili": ["सीता देवी", "राम बाबू", "सुनीता", "गंगा देवी", "मोहन झा"],
    "hindi":    ["रमेश", "गीता देवी", "श्याम लाल", "कमला", "सुरेश कुमार"],
    "bhojpuri": ["राजू", "फूलमती", "बिरजू", "सरिता", "हरि"],
    "awadhi":   ["रामखेलावन", "सावित्री", "बैजनाथ", "कौशल्या"],
    "bengali":  ["অমিত", "রিনা", "সুবল", "মমতা দেবী"],
    "gujarati": ["રમેશભાઈ", "જયા બેન", "મનુ", "કોકિલા"],
    "marathi":  ["विठ्ठल", "लक्ष्मीबाई", "साईनाथ", "मंगल"],
    "kannada":  ["ರಮೇಶ", "ಗೌರಮ್ಮ", "ಶಿವಣ್ಣ", "ಲಕ್ಷ್ಮಿ"],
    "telugu":   ["వెంకట్", "లక్ష్మమ్మ", "రాజు", "సరళ"],
    "tamil":    ["முருகன்", "கமலா", "செல்வம்", "மீனா"],
}

# Language tends to correlate with home state (origin clusters). SYNTHETIC map.
_LANG_STATE = {
    "maithili": "Bihar", "bhojpuri": "Bihar", "awadhi": "Uttar Pradesh",
    "hindi": "Madhya Pradesh", "bengali": "West Bengal", "gujarati": "Gujarat",
    "marathi": "Maharashtra", "kannada": "Karnataka", "telugu": "Telangana",
    "tamil": "Tamil Nadu",
}

_DESCRIPTORS = [
    "wearing a green saree", "white kurta and dhoti", "carrying a cloth bag",
    "red shawl, walking with a stick", "blue blouse", "barefoot, orange scarf",
    "spectacles, grey hair", "yellow sari with gold border",
]


def _age_band(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.115:                       # 11.5% children
        return rng.choice(["0-12", "13-17"])
    if r < 0.115 + 0.58:               # 58% elderly
        return rng.choice(["61-75", "76+"])
    return rng.choice(["18-30", "31-45", "46-60"])  # working age


# Distinctive landmark details a family and a finder might BOTH mention. A true
# pair shares one of these; coincidental records rarely do — so free-text becomes
# a genuine discriminator (mirrors "she had a green trunk near the Hanuman temple").
_DETAILS = [
    "green tin trunk", "red walking stick", "yellow cloth bundle",
    "Hanuman temple side", "near the blue water tank", "by the marigold stalls",
    "carrying a brass pot", "torn jute bag", "saffron headscarf",
    "near the south gate", "by the tea stall", "missing one slipper",
]


def _mk_person(rng, *, record_type, language, age_band, zone, seen_time,
               with_name=True, photo=False):
    state = _LANG_STATE[language]
    name = rng.choice(_NAMES[language]) if with_name else None
    seen = seen_time.isoformat()
    desc = rng.choice(_DESCRIPTORS)  # noisy/low-trust
    free = rng.choice([
        f"last seen near the {zone} ghat steps",
        f"got separated in the crowd at {zone}",
        f"was resting near the water tank at {zone}",
        None,
    ])
    return PersonRecord(
        person_record_id="",  # filled by caller (needs a domain)
        source_date=dt.datetime.now(dt.timezone.utc).isoformat(),
        record_type=record_type,
        origin_domain="",
        age_band=age_band,
        sex=rng.choice(["F", "M"]),
        home_state=state,
        language=language,
        last_seen_zone=zone,
        last_seen_time=seen,
        full_name=name,
        physical_description=desc,
        free_text=free,
        photo_ref=(f"photo://synthetic/{rng.randint(1000,9999)}.jpg" if photo else None),
        photo_consented=photo,
        consent_match=True,
        consent_pa=rng.random() < 0.6,
        is_minor=age_band in ("0-12", "13-17"),
        expiry_date=(dt.datetime.now(dt.timezone.utc)
                     + dt.timedelta(days=config.DEFAULT_RETENTION_DAYS)).isoformat(),
        author="synthetic-seed",
    )


def generate(n: int = 2500, *, seed: int = 42,
             true_pair_fraction: float = 0.25) -> Dataset:
    """Return a Dataset (records + ground truth) ready to seed across nodes.

    `true_pair_fraction` of cases become a genuine missing<->found pair (the
    cascade's correct answers). Of those pairs, ~15% will have a missing name on
    at least one side to exercise no-name matching. ~8% of records are duplicate
    reports of an existing FOUND record."""
    rng = random.Random(seed)
    centers = list(config.CENTERS.keys())
    langs = list(_NAMES.keys())
    ds = Dataset()
    out = ds.records
    group_seq = 0

    # Events are spread across a realistic 36-hour window so that "last seen
    # within ~2h" is a genuine discriminator (not something almost every pair
    # shares). This is what makes the honest precision/recall meaningful.
    window_start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=36)
    WINDOW_MIN = 36 * 60
    n_pairs = int(n * true_pair_fraction / 2)
    produced = 0

    def rand_time():
        return window_start + dt.timedelta(minutes=rng.randint(0, WINDOW_MIN))

    def assign(center_key: str, rec: PersonRecord, group: str) -> PersonRecord:
        domain = config.CENTERS[center_key]["domain"]
        rec.origin_domain = domain
        rec.person_record_id = new_id(domain)
        ds.truth[rec.person_record_id] = group
        return rec

    # 1) True missing<->found pairs (same underlying person, two centers).
    for _ in range(n_pairs):
        group_seq += 1
        group = f"g{group_seq}"
        lang = rng.choice(langs)
        ab = _age_band(rng)
        zone = rng.choice(config.ZONES)
        # the found report sometimes lands in an adjacent zone (realistic drift),
        # but mostly the SAME zone — exact zone is what makes the pair findable.
        found_zone = zone if rng.random() < 0.7 else rng.choice(
            list(config._ADJACENCY.get(zone, {zone})) or [zone])
        no_name = rng.random() < 0.15  # 15% of pairs have a missing name somewhere
        photo = rng.random() < 0.3

        # the person goes missing at t; the finder logs them 5-90 min later.
        t_missing = rand_time()
        t_found = t_missing + dt.timedelta(minutes=rng.randint(5, 90))
        detail = rng.choice(_DETAILS)  # the distinctive shared cue

        missing = _mk_person(rng, record_type=RECORD_MISSING, language=lang,
                             age_band=ab, zone=zone, seen_time=t_missing,
                             with_name=not (no_name and rng.random() < 0.5),
                             photo=False)
        found = _mk_person(rng, record_type=RECORD_FOUND, language=lang,
                           age_band=ab, zone=found_zone, seen_time=t_found,
                           with_name=not (no_name and rng.random() < 0.5),
                           photo=photo)
        # give the pair a shared real name when both named (so it can agree) and
        # a shared DISTINCTIVE detail so the semantic signal can separate them
        # from coincidental same-demographic records.
        if missing.full_name and found.full_name:
            shared = rng.choice(_NAMES[lang])
            missing.full_name = shared
            found.full_name = shared
        missing.free_text = f"separated near {zone}, {detail}"
        found.free_text = f"found near {found_zone}, {detail}"
        cm = rng.choice(centers)
        cf = rng.choice([c for c in centers if c != cm])
        out.append((cm, assign(cm, missing, group)))
        out.append((cf, assign(cf, found, group)))
        produced += 2

    # 2) 8% duplicates: re-report some FOUND records at a second center.
    found_records = [(ck, r) for ck, r in out if r.record_type == RECORD_FOUND]
    n_dupes = int(n * 0.08)
    for _ in range(min(n_dupes, len(found_records))):
        ck, orig = rng.choice(found_records)
        group = ds.truth[orig.person_record_id]  # same person -> same truth group
        dupe_center = rng.choice([c for c in centers if c != ck])
        dupe = _mk_person(rng, record_type=RECORD_FOUND, language=orig.language,
                          age_band=orig.age_band, zone=orig.last_seen_zone,
                          seen_time=dt.datetime.fromisoformat(orig.last_seen_time),
                          with_name=orig.full_name is not None, photo=False)
        dupe.full_name = orig.full_name          # same person -> same name
        dupe.home_state = orig.home_state
        dupe.last_seen_time = orig.last_seen_time
        dupe.free_text = orig.free_text
        assign(dupe_center, dupe, group)
        out.append((dupe_center, dupe))
        ds.duplicate_ids.add(dupe.person_record_id)
        produced += 1

    # 3) Fill the rest with unrelated singletons (the long tail / noise). Each is
    #    its own truth group (no correct partner exists).
    while produced < n:
        group_seq += 1
        group = f"s{group_seq}"
        lang = rng.choice(langs)
        ab = _age_band(rng)
        zone = rng.choice(config.ZONES)
        rtype = rng.choice([RECORD_MISSING, RECORD_FOUND])
        rec = _mk_person(rng, record_type=rtype, language=lang, age_band=ab,
                         zone=zone, seen_time=rand_time(),
                         with_name=rng.random() > 0.15,  # 15% no-name overall
                         photo=rng.random() < 0.1)
        ck = rng.choice(centers)
        out.append((ck, assign(ck, rec, group)))
        produced += 1

    return ds


def _as_records(data) -> list:
    """Accept a Dataset or a raw list of (center_key, PersonRecord)."""
    return data.records if isinstance(data, Dataset) else data


def seed_store(store: Store, data) -> int:
    """Seed records whose origin_domain matches this store's domain (each node
    holds the records created at that center; sync distributes the rest)."""
    n = 0
    for _center_key, rec in _as_records(data):
        if rec.origin_domain == store.domain:
            store.put_person(rec)
            n += 1
    return n


def stats(data) -> dict:
    recs = [r for _, r in _as_records(data)]
    total = len(recs)
    elderly = sum(1 for r in recs if r.age_band in config.ELDERLY_BANDS)
    children = sum(1 for r in recs if r.age_band in config.CHILD_BANDS)
    no_name = sum(1 for r in recs if not r.full_name)
    missing = sum(1 for r in recs if r.record_type == RECORD_MISSING)
    found = total - missing
    return {
        "total": total,
        "pct_elderly": round(100 * elderly / total, 1),
        "pct_children": round(100 * children / total, 1),
        "pct_no_name": round(100 * no_name / total, 1),
        "missing_stream": missing,
        "found_stream": found,
        "languages": len({r.language for r in recs}),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate synthetic SETU dataset")
    ap.add_argument("-n", type=int, default=2500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    data = generate(args.n, seed=args.seed)
    import json

    s = stats(data)
    s["true_pairs"] = sum(1 for g in data.truth.values() if g.startswith("g")) // 2
    s["duplicates"] = len(data.duplicate_ids)
    print(json.dumps(s, indent=2))
