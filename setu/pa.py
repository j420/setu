"""PA (loudspeaker) script generation — the operational heart.

The real data shows targeted loudspeaker announcements in the person's OWN
language are the single highest-leverage reunification lever (Prayagraj 2025: the
manual loudspeaker camp reunited 19,274; facial recognition had no audited
reunifications). SETU augments that human lever — it does not replace it.

We generate zone-specific, own-language, NAME-OPTIONAL scripts. When no name is
known (15% of cases) the script falls back to age-band + last-seen + language
cues. Scripts are templated so most can fire without per-message human approval;
any non-templated / free-text PA requires human approval (enforced at the MCP
tool layer).

Templates are provided in native script for all 10 languages with a Latin
transliteration line for the announcer. Production TTS is via Bhashini
(see bhashini.py) — the locale codes here line up with that contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config

# Native-script templates. {name} is omitted entirely when unknown.
# Two variants per language: with-name and no-name. Kept short for loudspeakers.
_TEMPLATES = {
    "hindi": {
        "named": "ध्यान दें। {name}, उम्र लगभग {age}, {state} से, कृपया {zone} "
                 "सहायता केंद्र पर आएं। आपके परिवार वाले आपको ढूंढ रहे हैं।",
        "noname": "ध्यान दें। {state} से आए, {age} वर्ष के एक यात्री के परिवार "
                  "वाले उन्हें ढूंढ रहे हैं। कृपया {zone} सहायता केंद्र पर संपर्क करें।",
    },
    "maithili": {
        "named": "ध्यान दिअ। {name}, उमेर करीब {age}, {state} सँ, कृपया {zone} "
                 "सहायता केंद्र पर आउ। अहाँक परिवार अहाँके ताकि रहल अछि।",
        "noname": "ध्यान दिअ। {state} सँ आएल, {age} वर्षक एक यात्रीक परिवार हुनका "
                  "ताकि रहल अछि। कृपया {zone} सहायता केंद्र पर संपर्क करू।",
    },
    "bengali": {
        "named": "মনোযোগ দিন। {name}, বয়স প্রায় {age}, {state} থেকে, অনুগ্রহ করে "
                 "{zone} সহায়তা কেন্দ্রে আসুন। আপনার পরিবার আপনাকে খুঁজছে।",
        "noname": "মনোযোগ দিন। {state} থেকে আসা {age} বছরের একজন যাত্রীর পরিবার "
                  "তাঁকে খুঁজছে। অনুগ্রহ করে {zone} সহায়তা কেন্দ্রে যোগাযোগ করুন।",
    },
    "kannada": {
        "named": "ಗಮನಿಸಿ. {name}, ಸುಮಾರು {age} ವರ್ಷ, {state} ಯಿಂದ, ದಯವಿಟ್ಟು "
                 "{zone} ಸಹಾಯ ಕೇಂದ್ರಕ್ಕೆ ಬನ್ನಿ. ನಿಮ್ಮ ಕುಟುಂಬ ನಿಮ್ಮನ್ನು ಹುಡುಕುತ್ತಿದೆ.",
        "noname": "ಗಮನಿಸಿ. {state} ಯಿಂದ ಬಂದ {age} ವರ್ಷದ ಯಾತ್ರಿಕರ ಕುಟುಂಬ ಅವರನ್ನು "
                  "ಹುಡುಕುತ್ತಿದೆ. ದಯವಿಟ್ಟು {zone} ಸಹಾಯ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    },
    "gujarati": {
        "named": "ધ્યાન આપો. {name}, ઉંમર આશરે {age}, {state} થી, કૃપા કરી {zone} "
                 "સહાય કેન્દ્ર પર આવો. તમારો પરિવાર તમને શોધી રહ્યો છે.",
        "noname": "ધ્યાન આપો. {state} થી આવેલા {age} વર્ષના યાત્રીના પરિવારજનો "
                  "તેમને શોધી રહ્યા છે. કૃપા કરી {zone} સહાય કેન્દ્રનો સંપર્ક કરો.",
    },
    "telugu": {
        "named": "దయచేసి గమనించండి. {name}, వయసు సుమారు {age}, {state} నుండి, దయచేసి "
                 "{zone} సహాయ కేంద్రానికి రండి. మీ కుటుంబం మీ కోసం వెతుకుతోంది.",
        "noname": "దయచేసి గమనించండి. {state} నుండి వచ్చిన {age} ఏళ్ల యాత్రికుని కుటుంబం "
                  "వారి కోసం వెతుకుతోంది. దయచేసి {zone} సహాయ కేంద్రాన్ని సంప్రదించండి.",
    },
    "bhojpuri": {
        "named": "धेयान दीं। {name}, उमिर करीब {age}, {state} से, कृपया {zone} "
                 "सहायता केंद्र पर आईं। राउर परिवार राउरा के खोजत बा।",
        "noname": "धेयान दीं। {state} से आइल {age} बरिस के एगो यात्री के परिवार "
                  "ओनके खोजत बा। कृपया {zone} सहायता केंद्र पर संपर्क करीं।",
    },
    "awadhi": {
        "named": "धियान देई। {name}, उमिर लगभग {age}, {state} से, किरपा करके {zone} "
                 "सहायता केंद्र पर आवा। तोहार परिवार तोहका खोजत बा।",
        "noname": "धियान देई। {state} से आइल {age} बरिस के एक यात्री के परिवार "
                  "ओनका खोजत बा। किरपा करके {zone} सहायता केंद्र पर संपर्क करा।",
    },
    "tamil": {
        "named": "கவனிக்கவும். {name}, வயது சுமார் {age}, {state} இலிருந்து, தயவுசெய்து "
                 "{zone} உதவி மையத்திற்கு வாருங்கள். உங்கள் குடும்பம் உங்களைத் தேடுகிறது.",
        "noname": "கவனிக்கவும். {state} இலிருந்து வந்த {age} வயது யாத்ரீகரின் குடும்பம் "
                  "அவரைத் தேடுகிறது. தயவுசெய்து {zone} உதவி மையத்தைத் தொடர்பு கொள்ளுங்கள்.",
    },
    "marathi": {
        "named": "लक्ष द्या. {name}, वय अंदाजे {age}, {state} येथून, कृपया {zone} "
                 "मदत केंद्रावर या. तुमचे कुटुंब तुम्हाला शोधत आहे.",
        "noname": "लक्ष द्या. {state} येथून आलेल्या {age} वर्षांच्या यात्रेकरूच्या "
                  "कुटुंबीयांनी त्यांचा शोध घेत आहेत. कृपया {zone} मदत केंद्राशी संपर्क साधा.",
    },
}

# Latin announcer line (helps a Marathi-speaking announcer read a Maithili name).
_ANNOUNCER_LATIN = {
    "named": "ATTENTION: {name}, approx age {age}, from {state} — please come to "
             "the {zone} help desk. Your family is looking for you.",
    "noname": "ATTENTION: family of a traveller approx age {age} from {state} is "
              "searching for them — please contact the {zone} help desk.",
}


@dataclass
class PAScript:
    zone: str
    language: str
    pa_locale: str
    native_text: str
    announcer_latin: str
    templated: bool                  # True -> may fire without per-message approval
    requires_human_approval: bool


def _age_phrase(age_band: str) -> str:
    return age_band.replace("-", " to ") if age_band else "unknown"


def generate_pa_script(
    *,
    zone: str,
    language: str,
    age_band: str = "",
    home_state: str = "",
    name: str | None = None,
    free_text: str | None = None,
) -> PAScript:
    """Generate a zone-targeted, own-language PA script. Name-optional: if no
    name, the no-name template (age-band + origin + last-seen) is used.

    If `free_text` (non-templated content) is supplied it is appended and the
    script is flagged as requiring human approval before firing."""
    lang = language if language in _TEMPLATES else "hindi"
    locale = config.LANGUAGES.get(lang, config.LANGUAGES["hindi"])["pa_locale"]
    zone_name = config.CENTERS.get(zone, {}).get("name", zone.replace("_", " ").title())
    age = _age_phrase(age_band)
    state = home_state or "another state"

    variant = "named" if name else "noname"
    native = _TEMPLATES[lang][variant].format(
        name=name or "", age=age, state=state, zone=zone_name)
    latin = _ANNOUNCER_LATIN[variant].format(
        name=name or "", age=age, state=state, zone=zone_name)

    templated = True
    needs_approval = False
    if free_text:
        native = f"{native} [{free_text}]"
        latin = f"{latin} [{free_text}]"
        templated = False
        needs_approval = True  # free-text PA must be human-approved

    return PAScript(
        zone=zone,
        language=lang,
        pa_locale=locale,
        native_text=native.strip(),
        announcer_latin=latin.strip(),
        templated=templated,
        requires_human_approval=needs_approval,
    )
