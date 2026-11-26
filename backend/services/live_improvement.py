"""Identify short, grounded curriculum improvement requests."""
import re


def is_improvement_request(*phrases):
    return any(re.search(
        r"\b(improv(?:e|es|ed|ement|ements|ing)|recommendations?|suggestions?|enhance)\b|સુધાર|बेहतर|सुधार",
        phrase, re.I,
    ) for phrase in phrases)


def quick_recommendations(reviews, language):
    """Use documented credit totals when the model cannot respond in time."""
    if len(reviews) != 1:
        return None
    for semester in reviews[0].get("semesters", []):
        stated = semester.get("stated_credits")
        calculated = semester.get("sum_of_parsed_credits")
        if stated is None or calculated is None or stated == calculated:
            continue
        number = semester["semester"]
        return {
            "hi": f"सेमेस्टर {number} में कुल {stated:g} क्रेडिट लिखे हैं, लेकिन मुझे पढ़ी जा सकी कोर्स पंक्तियों में {calculated:g} मिले। पहले क्रेडिट तालिका की छूटी हुई पंक्तियाँ और कुल जाँच लें।",
            "gu": f"સેમેસ્ટર {number} માં કુલ {stated:g} ક્રેડિટ લખેલી છે, પણ વાંચી શકાયેલી કોર્સ પંક્તિઓમાં {calculated:g} મળી. પહેલાં ક્રેડિટ ટેબલની બાકી પંક્તિઓ અને કુલ ચકાસો.",
        }.get(language, f"Start with the semester {number} credit table. The PDF lists {stated:g} credits, while the course rows I could read add up to {calculated:g}. Check the table for omitted rows and reconcile the total.")
    for course in reviews[0].get("courses", []):
        if course.get("credits") is None and course.get("title"):
            title = course["title"]
            return {
                "hi": f"{title} के क्रेडिट से शुरू करें। पढ़ी गई तालिका में इसका क्रेडिट मान स्पष्ट नहीं था। जाँचें कि सही मान कोर्स पंक्ति में साफ़ लिखा है।",
                "gu": f"{title} ના ક્રેડિટથી શરૂઆત કરો. વાંચેલી ટેબલમાં આ કોર્સનું ક્રેડિટ મૂલ્ય સ્પષ્ટ નહોતું. કોર્સની પંક્તિમાં સાચું મૂલ્ય સ્પષ્ટ છે કે નહીં તે ચકાસો.",
            }.get(language, f"Start by making the credit value for {title} explicit. I couldn't verify it in the course table I read. Check that the correct number is clearly stated in the course row.")
    course = next((course for course in reviews[0].get("courses", []) if course.get("title")), None)
    if course:
        title = course["title"]
        return {
            "hi": f"एक व्यावहारिक सुधार {title} से शुरू करना है। हर मुख्य कोर्स आउटकम के सामने वह असाइनमेंट या मूल्यांकन लिखें जो उसे मापता है। यह डिज़ाइन सुझाव है।",
            "gu": f"એક ઉપયોગી સુધારો {title} થી શરૂ કરો. દરેક મુખ્ય course outcome સામે તેને માપતું assignment અથવા assessment લખો. આ એક ડિઝાઇન સૂચન છે.",
        }.get(language, f"One practical improvement is to start with {title}. Map each main learning outcome to the assignment or assessment that measures it. This is a design suggestion.")
    return None


def compact_review(review):
    return {
        **{key: value for key, value in review.items() if key not in {"courses", "parser_warnings"}},
        "course_fields": ["title", "semester", "category", "credits"],
        "courses": [[course.get(field) for field in ("title", "semester", "category", "credits")]
                    for course in review.get("courses", [])[:80]],
        "course_inventory_truncated": review.get("course_inventory_truncated", False)
                                     or len(review.get("courses", [])) > 80,
        "parser_warnings": [warning[:150] for warning in review.get("parser_warnings", [])[:2]],
    }
