// Name handling: transliteration + Indic phonetic key (port of names.py).
// A name is a SIGNAL, never a GATE.

const DEVANAGARI_MAP: Record<string, string> = {
  "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo",
  "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ं": "n", "ः": "h",
  "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "च": "ch", "छ": "chh",
  "ज": "j", "झ": "jh", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
  "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
  "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y",
  "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s",
  "ह": "h", "ळ": "l",
  "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "े": "e",
  "ै": "ai", "ो": "o", "ौ": "au", "ृ": "ri", "्": "",
};

function isAscii(s: string): boolean {
  // eslint-disable-next-line no-control-regex
  return /^[\x00-\x7F]*$/.test(s);
}

// MOCK of AI4Bharat IndicXlit. Native-script name -> romanised lowercase.
export function transliterate(name: string | null | undefined): string {
  if (!name) return "";
  if (isAscii(name)) return name.trim().toLowerCase();
  let out = "";
  for (const ch of name) {
    if (ch in DEVANAGARI_MAP) out += DEVANAGARI_MAP[ch];
    else if (isAscii(ch)) out += ch;
  }
  return out.trim().toLowerCase();
}

const HONORIFICS = new Set([
  "devi", "kumar", "kumari", "bai", "ben", "lal", "ji", "das", "ram",
  "singh", "khan", "begum", "shri", "smt", "sri",
]);

const FOLD: [RegExp, string][] = [
  [/[^a-z]/g, ""],
  [/a{2,}/g, "a"], [/e{2,}/g, "i"], [/o{2,}/g, "u"],
  [/ph/g, "f"], [/bh/g, "b"], [/gh/g, "g"], [/dh/g, "d"],
  [/th/g, "t"], [/kh/g, "k"], [/chh/g, "c"], [/ch/g, "c"],
  [/sh/g, "s"], [/v/g, "w"],
  [/(.)\1+/g, "$1"],
];

export function phoneticKey(name: string | null | undefined): string {
  const roman = transliterate(name);
  const tokens = roman.split(/\s+/).filter((t) => t && !HONORIFICS.has(t));
  let s = tokens.length ? tokens.join("") : roman.replace(/\s+/g, "");
  for (const [pat, rep] of FOLD) s = s.replace(pat, rep);
  return s.slice(0, 8);
}

export interface NameAgreement {
  present: boolean;
  exact: boolean;
  phonetic: boolean;
  key_a: string | null;
  key_b: string | null;
}

export function nameAgreement(
  a: string | null | undefined,
  b: string | null | undefined,
): NameAgreement {
  if (!a || !b)
    return { present: false, exact: false, phonetic: false, key_a: null, key_b: null };
  const ra = transliterate(a);
  const rb = transliterate(b);
  const ka = phoneticKey(a);
  const kb = phoneticKey(b);
  return {
    present: true,
    exact: ra === rb && ra !== "",
    phonetic: ka === kb && ka !== "",
    key_a: ka,
    key_b: kb,
  };
}
