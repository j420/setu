// PA script generation (port of pa.py): zone-targeted, own-language,
// name-optional. Free-text (non-templated) PA requires human approval.

import { CENTERS, LANGUAGES } from "./config";

interface TemplatePair {
  named: string;
  noname: string;
}

const TEMPLATES: Record<string, TemplatePair> = {
  hindi: {
    named:
      "ध्यान दें। {name}, उम्र लगभग {age}, {state} से, कृपया {zone} सहायता केंद्र पर आएं। आपके परिवार वाले आपको ढूंढ रहे हैं।",
    noname:
      "ध्यान दें। {state} से आए, {age} वर्ष के एक यात्री के परिवार वाले उन्हें ढूंढ रहे हैं। कृपया {zone} सहायता केंद्र पर संपर्क करें।",
  },
  maithili: {
    named:
      "ध्यान दिअ। {name}, उमेर करीब {age}, {state} सँ, कृपया {zone} सहायता केंद्र पर आउ। अहाँक परिवार अहाँके ताकि रहल अछि।",
    noname:
      "ध्यान दिअ। {state} सँ आएल, {age} वर्षक एक यात्रीक परिवार हुनका ताकि रहल अछि। कृपया {zone} सहायता केंद्र पर संपर्क करू।",
  },
  bengali: {
    named:
      "মনোযোগ দিন। {name}, বয়স প্রায় {age}, {state} থেকে, অনুগ্রহ করে {zone} সহায়তা কেন্দ্রে আসুন। আপনার পরিবার আপনাকে খুঁজছে।",
    noname:
      "মনোযোগ দিন। {state} থেকে আসা {age} বছরের একজন যাত্রীর পরিবার তাঁকে খুঁজছে। অনুগ্রহ করে {zone} সহায়তা কেন্দ্রে যোগাযোগ করুন।",
  },
  kannada: {
    named:
      "ಗಮನಿಸಿ. {name}, ಸುಮಾರು {age} ವರ್ಷ, {state} ಯಿಂದ, ದಯವಿಟ್ಟು {zone} ಸಹಾಯ ಕೇಂದ್ರಕ್ಕೆ ಬನ್ನಿ. ನಿಮ್ಮ ಕುಟುಂಬ ನಿಮ್ಮನ್ನು ಹುಡುಕುತ್ತಿದೆ.",
    noname:
      "ಗಮನಿಸಿ. {state} ಯಿಂದ ಬಂದ {age} ವರ್ಷದ ಯಾತ್ರಿಕರ ಕುಟುಂಬ ಅವರನ್ನು ಹುಡುಕುತ್ತಿದೆ. ದಯವಿಟ್ಟು {zone} ಸಹಾಯ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ.",
  },
  gujarati: {
    named:
      "ધ્યાન આપો. {name}, ઉંમર આશરે {age}, {state} થી, કૃપા કરી {zone} સહાય કેન્દ્ર પર આવો. તમારો પરિવાર તમને શોધી રહ્યો છે.",
    noname:
      "ધ્યાન આપો. {state} થી આવેલા {age} વર્ષના યાત્રીના પરિવારજનો તેમને શોધી રહ્યા છે. કૃપા કરી {zone} સહાય કેન્દ્રનો સંપર્ક કરો.",
  },
  telugu: {
    named:
      "దయచేసి గమనించండి. {name}, వయసు సుమారు {age}, {state} నుండి, దయచేసి {zone} సహాయ కేంద్రానికి రండి. మీ కుటుంబం మీ కోసం వెతుకుతోంది.",
    noname:
      "దయచేసి గమనించండి. {state} నుండి వచ్చిన {age} ఏళ్ల యాత్రికుని కుటుంబం వారి కోసం వెతుకుతోంది. దయచేసి {zone} సహాయ కేంద్రాన్ని సంప్రదించండి.",
  },
  bhojpuri: {
    named:
      "धेयान दीं। {name}, उमिर करीब {age}, {state} से, कृपया {zone} सहायता केंद्र पर आईं। राउर परिवार राउरा के खोजत बा।",
    noname:
      "धेयान दीं। {state} से आइल {age} बरिस के एगो यात्री के परिवार ओनके खोजत बा। कृपया {zone} सहायता केंद्र पर संपर्क करीं।",
  },
  awadhi: {
    named:
      "धियान देई। {name}, उमिर लगभग {age}, {state} से, किरपा करके {zone} सहायता केंद्र पर आवा। तोहार परिवार तोहका खोजत बा।",
    noname:
      "धियान देई। {state} से आइल {age} बरिस के एक यात्री के परिवार ओनका खोजत बा। किरपा करके {zone} सहायता केंद्र पर संपर्क करा।",
  },
  tamil: {
    named:
      "கவனிக்கவும். {name}, வயது சுமார் {age}, {state} இலிருந்து, தயவுசெய்து {zone} உதவி மையத்திற்கு வாருங்கள். உங்கள் குடும்பம் உங்களைத் தேடுகிறது.",
    noname:
      "கவனிக்கவும். {state} இலிருந்து வந்த {age} வயது யாத்ரீகரின் குடும்பம் அவரைத் தேடுகிறது. தயவுசெய்து {zone} உதவி மையத்தைத் தொடர்பு கொள்ளுங்கள்.",
  },
  marathi: {
    named:
      "लक्ष द्या. {name}, वय अंदाजे {age}, {state} येथून, कृपया {zone} मदत केंद्रावर या. तुमचे कुटुंब तुम्हाला शोधत आहे.",
    noname:
      "लक्ष द्या. {state} येथून आलेल्या {age} वर्षांच्या यात्रेकरूच्या कुटुंबीयांनी त्यांचा शोध घेत आहेत. कृपया {zone} मदत केंद्राशी संपर्क साधा.",
  },
};

const ANNOUNCER_LATIN: TemplatePair = {
  named:
    "ATTENTION: {name}, approx age {age}, from {state} — please come to the {zone} help desk. Your family is looking for you.",
  noname:
    "ATTENTION: family of a traveller approx age {age} from {state} is searching for them — please contact the {zone} help desk.",
};

export interface PAScript {
  zone: string;
  language: string;
  pa_locale: string;
  native_text: string;
  announcer_latin: string;
  templated: boolean;
  requires_human_approval: boolean;
}

function fill(t: string, vars: Record<string, string>): string {
  return t.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
}

function agePhrase(band: string): string {
  return band ? band.replace("-", " to ") : "unknown";
}

export function generatePaScript(opts: {
  zone: string;
  language: string;
  age_band?: string;
  home_state?: string;
  name?: string | null;
  free_text?: string | null;
}): PAScript {
  const lang = opts.language in TEMPLATES ? opts.language : "hindi";
  const locale = (LANGUAGES[lang] ?? LANGUAGES.hindi).pa_locale;
  const zoneName =
    CENTERS[opts.zone]?.name ??
    opts.zone.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const vars = {
    name: opts.name ?? "",
    age: agePhrase(opts.age_band ?? ""),
    state: opts.home_state || "another state",
    zone: zoneName,
  };
  const variant: keyof TemplatePair = opts.name ? "named" : "noname";

  let native = fill(TEMPLATES[lang][variant], vars).trim();
  let latin = fill(ANNOUNCER_LATIN[variant], vars).trim();
  let templated = true;
  let needsApproval = false;

  if (opts.free_text) {
    native = `${native} [${opts.free_text}]`;
    latin = `${latin} [${opts.free_text}]`;
    templated = false;
    needsApproval = true;
  }

  return {
    zone: opts.zone,
    language: lang,
    pa_locale: locale,
    native_text: native,
    announcer_latin: latin,
    templated,
    requires_human_approval: needsApproval,
  };
}
