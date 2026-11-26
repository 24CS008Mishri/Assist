"""Normalize the text sent to TTS. Stored evidence and PDF text are untouched."""
from datetime import date
import os
import re

from indic_numtowords import num2words

_DIGITS = str.maketrans("०१२३४५६७८९૦૧૨૩૪૫૬૭૮૯", "01234567890123456789")
_NUMBER = r"(?:[0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]+)(?:\.[0-9]+)?"
_ORDINAL_ENDS = {
    "one": "first", "two": "second", "three": "third", "five": "fifth",
    "eight": "eighth", "nine": "ninth", "twelve": "twelfth",
}
_TERMS = {
    "en": ("point", "percent", "to", "over", "Indian rupees", "minus", "equals", "times", "divided by", "plus"),
    "hi": ("दशमलव", "प्रतिशत", "से", "बटा", "रुपये", "माइनस", "बराबर", "गुणा", "भाग", "जोड़"),
    "gu": ("દશાંશ", "ટકા", "થી", "ભાગ્યા", "રૂપિયા", "માઇનસ", "બરાબર", "ગુણ્યા", "ભાગ્યા", "વત્તા"),
}
_HI_ORDINALS = "पहला दूसरा तीसरा चौथा पाँचवाँ छठा सातवाँ आठवाँ नौवाँ दसवाँ ग्यारहवाँ बारहवाँ".split()
_GU_ORDINALS = "પહેલું બીજું ત્રીજું ચોથું પાંચમું છઠ્ઠું સાતમું આઠમું નવમું દસમું અગિયારમું બારમું".split()
_MONTHS = {
    "en": "January February March April May June July August September October November December".split(),
    "hi": "जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर".split(),
    "gu": "જાન્યુઆરી ફેબ્રુઆરી માર્ચ એપ્રિલ મે જૂન જુલાઈ ઑગસ્ટ સપ્ટેમ્બર ઑક્ટોબર નવેમ્બર ડિસેમ્બર".split(),
}


def avatar_gender():
    return "masculine" if os.getenv("TAVUS_AVATAR_GENDER", "").lower() == "masculine" else "feminine"


def normalize_speech(message, language):
    lang = language if language in ("hi", "gu") else "en"
    if language == "mixed":
        indic = re.search(r"[\u0900-\u097f\u0a80-\u0aff]", message)
        if indic:
            lang = "gu" if indic.group() >= "\u0a80" else "hi"
    point, percent, to, over, rupees, minus, equals, times, divide, plus = _TERMS[lang]

    def digits(number):
        return " ".join(num2words(int(digit), lang=lang) for digit in number)

    def cardinal(raw):
        whole, dot, fraction = raw.replace(",", "").partition(".")
        if len(whole) > 9 or (len(whole) > 1 and whole.startswith("0")):
            result = digits(whole)
        else:
            result = num2words(int(whole), lang=lang)
            if lang == "en":
                result = result.replace(" and ", " ")
                result = re.sub(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety) (one|two|three|four|five|six|seven|eight|nine)\b",
                                r"\1-\2", result)
        return f"{result} {point} {digits(fraction)}" if dot else result

    def ordinal(raw):
        number = int(raw)
        if lang != "en":
            words = _HI_ORDINALS if lang == "hi" else _GU_ORDINALS
            if 1 <= number <= len(words):
                return words[number - 1]
            return ("क्रम संख्या " if lang == "hi" else "ક્રમ નંબર ") + cardinal(raw)
        word = cardinal(raw)
        match = re.search(r"[a-z]+$", word)
        if not match:
            return word
        last = match.group()
        ending = _ORDINAL_ENDS.get(last, last[:-1] + "ieth" if last.endswith("y") else last + "th")
        return word[:match.start()] + ending

    def iso_date(match):
        try:
            parsed = date.fromisoformat(match.group())
        except ValueError:
            return " ".join(digits(field) for field in match.group().split("-"))
        return f"{cardinal(str(parsed.day))} {_MONTHS[lang][parsed.month - 1]} {cardinal(str(parsed.year))}"

    def academic_year(match):
        start, short_end = int(match[1]), int(match[2])
        end = start // 100 * 100 + short_end
        if end < start:
            end += 100
        return f"{cardinal(str(start))} {to} {cardinal(str(end))}" if end <= start + 5 else (
            f"{cardinal(match[1])} {to} {cardinal(match[2])}"
        )

    def local_date(match):
        day, month, year = map(int, match.groups())
        try:
            parsed = date(year, month, day)
        except ValueError:
            return " ".join(digits(field) for field in match.groups())
        return f"{cardinal(str(parsed.day))} {_MONTHS[lang][parsed.month - 1]} {cardinal(str(parsed.year))}"

    text = message.strip()
    feminine = avatar_gender() == "feminine"
    for masculine, female in (
        ("मैं समझ गया", "मैं समझ गई"), ("मैं बता सकता", "मैं बता सकती"),
        ("मैं कर लेता", "मैं कर लेती"), ("मैं चेक करता", "मैं चेक करती"),
        ("હું સમજી ગયો", "હું સમજી ગઈ"),
    ):
        text = text.replace(masculine, female) if feminine else text.replace(female, masculine)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"https?://[^\s<>]+", "", text)
    text = re.sub(r"\[(?:source[^\]]*|\d+(?:\s*,\s*\d+)*)\]", "", text, flags=re.I)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*]\s+)", "", text)
    text = text.replace("**", "").replace("\x60", "")
    text = text.translate(_DIGITS)
    # Alphanumeric course codes and explicit identifier/telephone labels keep digit order.
    text = re.sub(r"\b([A-Z]{2,8})-?([0-9]{2,8})([A-Z]?)\b",
                  lambda m: " ".join((*m[1], digits(m[2]), *m[3])), text)
    text = re.sub(r"\b((?:registration|id|phone|telephone|roll)\s+(?:number\s+)?)([0-9]{5,})\b",
                  lambda m: m[1] + digits(m[2]), text, flags=re.I)
    text = re.sub(r"\b[12][0-9]{3}-[0-9]{2}-[0-9]{2}\b", iso_date, text)
    text = re.sub(r"\b([0-9]{1,2})/([0-9]{1,2})/([12][0-9]{3})\b", local_date, text)
    text = re.sub(r"\b([12][0-9]{3})\s*[-–—/]\s*([0-9]{2})(?![0-9/])", academic_year, text)
    text = re.sub(r"\b([0-9]{1,4})(?:st|nd|rd|th)\b", lambda m: ordinal(m[1]), text, flags=re.I)
    text = re.sub(rf"(?<!\w)₹\s*({_NUMBER})", lambda m: f"{cardinal(m[1])} {rupees}", text)
    text = re.sub(rf"(?<!\w)({_NUMBER})\s*%", lambda m: f"{cardinal(m[1])} {percent}", text)
    text = re.sub(rf"(?<!\w)({_NUMBER})\s*[–—-]\s*({_NUMBER})(?!\w)",
                  lambda m: f"{cardinal(m[1])} {to} {cardinal(m[2])}", text)
    text = re.sub(r"(?<![\w/])([0-9]{1,3})/([0-9]{1,3})(?![\w/])",
                  lambda m: f"{cardinal(m[1])} {over} {cardinal(m[2])}", text)
    text = re.sub(rf"(?<![\w/])(-?)({_NUMBER})(?![\w/])",
                  lambda m: (f"{minus} " if m[1] else "") + cardinal(m[2]), text)
    text = re.sub(r"\bAI/ML\b", "A I and M L", text)
    text = re.sub(r"\b(?:AICTE|CSE|IT|NEP|BBA|BCA|AI|ML)\b", lambda m: " ".join(m.group()), text)
    for symbol, word in (("=", equals), ("×", times), ("÷", divide), ("+", plus), ("−", minus)):
        text = text.replace(symbol, f" {word} ")
    return " ".join(text.split())
