"""Answer upload-name questions from the authenticated owner's metadata."""
import re

from pymongo import timeout

from backend.data.database import get_designer_metadata_collection


def is_upload_inventory(*phrases):
    for phrase in phrases:
        query = phrase.casefold()
        if re.search(r"\b(compare|analy[sz]e|review|credits?|compliance|gaps?|missing)\b|વિશ્લેષણ|સરખામણી|तुलना|विश्लेषण", query):
            continue
        if re.search(r"upload|અપલોડ|अपलोड", query) and re.search(
            r"\b(list|names?|titles?|which|what)\b|નામ|લિસ્ટ|યાદી|કયા|नाम|सूची|कौन|लिस्ट", query,
        ):
            return True
        if re.search(r"curricul|કરિક્યુલમ|અભ્યાસક્રમ|पाठ्यक्रम|करिकुलम", query) and re.search(
            r"\b(just|only)\b.*\b(names?|titles?)\b|(?:ખાલી|ફક્ત).*નામ|(?:सिर्फ़?|केवल).*नाम", query,
        ):
            return True
    return False


def upload_inventory(owner_id: str, language: str, question: str):
    with timeout(3):
        rows = list(get_designer_metadata_collection().find(
            {"owner_id": owner_id, "source_type": "submitted_curriculum", "status": "Active"},
            {"filename": 1, "_id": 0},
        ).sort("uploaded_at", -1))
    filenames = list(dict.fromkeys(row["filename"] for row in rows if row.get("filename")))
    names = [re.sub(r"\.pdf$", "", filename, flags=re.I) or filename for filename in filenames]
    if language == "mixed":
        language = "gu" if re.search(r"[\u0a80-\u0aff]", question) else "hi" if re.search(r"[\u0900-\u097f]", question) else "en-in"
    empty, intro, remainder = {
        "gu": ("તમારા ખાતામાં હજી કોઈ કરિક્યુલમ અપલોડ નથી.", "તમે આ કરિક્યુલમ અપલોડ કર્યા છે", "બાકીનાં નામ Evidence પેનલમાં છે."),
        "hi": ("आपके खाते में अभी कोई पाठ्यक्रम अपलोड नहीं है।", "आपने ये पाठ्यक्रम अपलोड किए हैं", "बाकी नाम Evidence पैनल में हैं।"),
    }.get(language, ("There are no uploaded curricula in your account yet.", "You've uploaded these curricula", "The remaining names are in the Evidence panel."))
    if not names:
        return empty, []
    answer = f"{intro}. {', '.join(names[:12])}."
    if len(names) > 12:
        answer += f" {remainder}"
    return answer, [{"title": filename, "kind": "Your curriculum"} for filename in filenames]
