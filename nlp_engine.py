# nlp_engine.py
import re
import math
from collections import Counter
from difflib import SequenceMatcher
from nltk.tokenize import wordpunct_tokenize
from nltk.tree import Tree

from config import (
    MUNICIPALITIES, MUNICIPALITY_ALIASES, UNSUPPORTED_LOCATIONS, 
    CATEGORY_SYNONYMS, LOCAL_DISHES, FEATURE_ALIASES, STOPWORDS
)

NON_SEARCH_PHRASES = {
    "i dont know", "i don't know", "dont know", "don't know", "idk",
    "sure", "yes", "no", "maybe", "okay", "ok", "yep", "yeah",
    "searching for laoag", "searching in laoag", "search laoag"
}

def is_non_search_input(text):
    clean = normalize_text(text)
    return clean in NON_SEARCH_PHRASES or any(clean == p for p in NON_SEARCH_PHRASES)

def normalize_text(text):
    text = str(text or "").lower().replace("’", "'").replace('"', '').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()

def tokenize_text(text):
    return wordpunct_tokenize(normalize_text(text))

def singularize_word(word):
    word = word.lower().strip()
    irregular = {
        "restaurants": "restaurant", "cafes": "cafe", "hotels": "hotel",
        "hospitals": "hospital", "banks": "bank", "gyms": "gym",
        "resorts": "resort", "stores": "store", "places": "place",
        "groceries": "grocery", "supermarkets": "supermarket"
    }
    if word in irregular:
        return irregular[word]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word

def normalized_tokens(text):
    return [singularize_word(t) for t in tokenize_text(text) if re.search(r"[a-z0-9]", t)]

def similarity_score(a, b):
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def get_character_ngrams(text, n=3):
    clean = f"${normalize_text(text)}$"
    return [clean[i:i+n] for i in range(len(clean) - n + 1)]

def ngram_similarity(str1, str2, n=3):
    ng1, ng2 = set(get_character_ngrams(str1, n)), set(get_character_ngrams(str2, n))
    return len(ng1.intersection(ng2)) / len(ng1.union(ng2)) if ng1 and ng2 else 0.0

def fuzzy_phrase_present(text, phrase, threshold=0.80):
    clean_text, clean_phrase = normalize_text(text), normalize_text(phrase)
    if not clean_phrase or not clean_text:
        return False
    if re.search(rf"(?<!\w){re.escape(clean_phrase)}(?!\w)", clean_text):
        return True
    text_words, phrase_words = clean_text.split(), clean_phrase.split()
    phrase_len = len(phrase_words)
    for i in range(len(text_words) - phrase_len + 1):
        if similarity_score(" ".join(text_words[i:i + phrase_len]), clean_phrase) >= threshold:
            return True
    return False

def phrase_present(text, phrase):
    return fuzzy_phrase_present(text, phrase, threshold=0.82)

NEGATION_TRIGGERS = {"no", "not", "dont", "don't", "dont want", "don't want", "doesnt", "doesn't", "except", "excluding", "without", "other than", "hate", "avoid", "instead of"}

def is_span_negated(text, span_start):
    prefix = text[:span_start].strip()
    words = re.findall(r"\b\w+[\'\w]*\b", prefix)
    window = " ".join(words[-4:]).lower() if words else ""
    return any(re.search(rf"\b{re.escape(t)}\b", window) for t in NEGATION_TRIGGERS)

def detect_location_entities(text):
    clean, found = normalize_text(text), set()
    for municipality, aliases in MUNICIPALITY_ALIASES.items():
        if any(phrase_present(clean, alias) for alias in aliases):
            found.add(municipality)
    return list(found)

def detect_unsupported_location(text):
    clean = normalize_text(text)
    for loc in UNSUPPORTED_LOCATIONS:
        if phrase_present(clean, loc):
            return loc.title()
    return None

def detect_category_entity(text):
    clean = normalize_text(text)
    if not clean:
        return None
    matches = []
    for category, aliases in CATEGORY_SYNONYMS.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            for m in re.finditer(rf"\b{re.escape(alias_norm)}\b", clean):
                if not is_span_negated(clean, m.start()):
                    matches.append((len(alias_norm), m.start(), category))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[1], item[0]), reverse=True)
    return matches[0][2]

def detect_exclusions(text):
    clean, exclusions = normalize_text(text), []
    pattern = r"\b(?:dont want|don't want|no|not|excluding|except|without|other than)\b\s+(?:a\s+|an\s+|the\s+)?([a-z\s]+)"
    for match in re.findall(pattern, clean):
        for cat_key, synonyms in CATEGORY_SYNONYMS.items():
            if any(syn in match for syn in synonyms):
                exclusions.append(cat_key)
    return list(set(exclusions))

def detect_feature_entities(text):
    clean = normalize_text(text)
    found = [f for f, aliases in FEATURE_ALIASES.items() if any(phrase_present(clean, a) for a in aliases)]
    m_feat = re.search(r"\b(?:with|has|offering|serves?|serving)\s+([a-z0-9\s]+)", clean)
    if m_feat:
        ext = m_feat.group(1).strip()
        if ext and ext not in found and len(ext) > 2:
            found.append(ext)
    return found

def detect_dish_entity(text):
    clean = normalize_text(text)
    for dish in sorted(LOCAL_DISHES, key=len, reverse=True):
        if phrase_present(clean, dish):
            return dish
    return None

def parse_time_to_minutes(time_str):
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", str(time_str or "").strip().upper())
    if not match:
        return None
    hours, minutes, period = int(match.group(1)), int(match.group(2)) if match.group(2) else 0, match.group(3)
    if hours > 23 or minutes > 59:
        return None
    if period == "PM" and hours != 12:
        hours += 12
    elif period == "AM" and hours == 12:
        hours = 0
    elif period is None and hours < 7:
        hours += 12
    return hours * 60 + minutes

def parse_hours_range(hours_str):
    try:
        parts = re.split(r"\s*(?:-|–|to)\s*", str(hours_str or "").strip(), flags=re.IGNORECASE)
        if len(parts) != 2:
            return None, None
        o_min, c_min = parse_time_to_minutes(parts[0]), parse_time_to_minutes(parts[1])
        if c_min is not None and o_min is not None and c_min <= o_min:
            c_min += 24 * 60
        return o_min, c_min
    except Exception:
        return None, None

def extract_operating_bounds(hours_data, target_day=None):
    if not hours_data:
        return None, None
    if isinstance(hours_data, dict):
        day_sch = None
        if target_day:
            for k, v in hours_data.items():
                if str(k).strip().lower() == target_day.strip().lower():
                    day_sch = v
                    break
        if day_sch is None:
            day_sch = next(iter(hours_data.values()), None)
        if isinstance(day_sch, dict):
            return parse_time_to_minutes(day_sch.get("opening") or day_sch.get("open")), parse_time_to_minutes(day_sch.get("closing") or day_sch.get("close"))
        elif isinstance(day_sch, str):
            return parse_hours_range(day_sch)
    return parse_hours_range(hours_data) if isinstance(hours_data, str) else (None, None)

def parse_opening_time_constraint(query_text):
    m = re.search(r"\b(?:opens?\s*at|opening\s*at|open\s*at)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", normalize_text(query_text))
    return parse_time_to_minutes(m.group(1)) if m else None

def parse_closing_time_constraint(query_text):
    m = re.search(r"\b(?:closes?\s*at|closing\s*at|close\s*at|open\s*until|until)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", normalize_text(query_text))
    return parse_time_to_minutes(m.group(1)) if m else None

def parse_budget(query_text):
    clean, candidates = normalize_text(query_text), []
    patterns = [
        r"(?:₱|php\s*|p\s*)\s*(\d[\d,]*(?:\.\d+)?)",
        r"(\d[\d,]*(?:\.\d+)?)\s*(?:pesos?|php)",
        r"\b(?:only\s*have|have|budget|under|below|less than|up to|max|cheap)\b.*?(?:₱|php|p)?\s*(\d[\d,]*)",
    ]
    for p in patterns:
        for m in re.finditer(p, clean, flags=re.IGNORECASE):
            try:
                val = float(m.group(1).replace(",", ""))
                if val > 0:
                    candidates.append(val)
            except (ValueError, IndexError):
                pass
    return min(candidates) if candidates else None

def build_query_parse_tree(query_text, constraints):
    children = []
    if constraints.get("category"):
        children.append(Tree("CATEGORY", [constraints["category"]]))
    if constraints.get("locations"):
        children.append(Tree("LOCATIONS", constraints["locations"]))
    if constraints.get("exclusions"):
        children.append(Tree("EXCLUSIONS", constraints["exclusions"]))
    if constraints.get("required_features"):
        children.append(Tree("FEATURES", [Tree("FEATURE", [f]) for f in constraints["required_features"]]))
    if constraints.get("dish"):
        children.append(Tree("DISH", [constraints["dish"]]))
    if constraints.get("max_budget") is not None:
        children.append(Tree("BUDGET", [str(constraints["max_budget"])]))
    if not children:
        children.append(Tree("TEXT", list(normalized_tokens(query_text))))
    return Tree("QUERY", children)

def extract_constraints_nlp(query_text):
    clean_text = normalize_text(query_text)
    locations = detect_location_entities(clean_text)
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    target_day = next((day for day in days if re.search(rf"\b{day}\b", clean_text)), None)

    constraints = {
        "category": detect_category_entity(clean_text),
        "exclusions": detect_exclusions(clean_text),
        "locations": locations,
        "location": locations[0] if locations else None,
        "dish": detect_dish_entity(clean_text),
        "max_budget": parse_budget(clean_text),
        "required_features": detect_feature_entities(clean_text),
        "target_opening_time": parse_opening_time_constraint(clean_text),
        "target_closing_time": parse_closing_time_constraint(clean_text),
        "target_day": target_day,
        "raw_query": query_text,
        "tokens": tokenize_text(clean_text),
        "parse_tree": None,
    }
    constraints["parse_tree"] = build_query_parse_tree(query_text, constraints)
    return constraints

def content_tokens(text):
    return [singularize_word(t) for t in normalized_tokens(text) if t not in STOPWORDS and len(t) > 1]

def lexical_overlap_score(query_text, place_text, place_corpus_list):
    q_tokens, p_tokens = content_tokens(query_text), content_tokens(place_text)
    if not q_tokens or not p_tokens:
        return 0.0
    num_docs = len(place_corpus_list) if place_corpus_list else 1
    word_counts = Counter(p_tokens)
    tfidf_score = 0.0
    for token in set(q_tokens):
        matched_word = token if token in word_counts else next((w for w in word_counts if similarity_score(token, w) >= 0.85), None)
        if matched_word:
            tf = word_counts[matched_word] / len(p_tokens)
            df = sum(1 for doc in place_corpus_list if token in doc.lower())
            idf = math.log((1 + num_docs) / (1 + df)) + 1.0
            tfidf_score += tf * idf
    return (tfidf_score * 0.50) + (ngram_similarity(query_text, place_text) * 0.50)

def extract_place_name_query(text):
    clean = normalize_text(text)
    if any(k in clean for k in ["cafe", "restaurant", "hotel", "hospital", "bank", "gym", "bar", "coffee"]):
        return None
    patterns = [
        r"\bwhere\s+is\s+(.+)", r"\bwhere\s+can\s+i\s+find\s+(.+)",
        r"\bwhere\s+to\s+find\s+(.+)", r"\bi\s+want\s+to\s+eat\s+at\s+(.+)",
        r"\bi\s+want\s+to\s+go\s+to\s+(.+)", r"\bhow\s+to\s+get\s+to\s+(.+)"
    ]
    for p in patterns:
        m = re.search(p, clean)
        if m:
            cleaned = re.sub(r"[^\w\s]", "", m.group(1).strip()).strip()
            if cleaned and cleaned not in MUNICIPALITIES and cleaned not in ["laoag city", "batac city"]:
                return cleaned
    return None

def find_place_globally(text, places_list):
    target_name = extract_place_name_query(text) or text
    clean_target = normalize_text(target_name)
    if not clean_target or clean_target in MUNICIPALITIES:
        return None

    best_match, highest_score = None, 0.0
    for place in (places_list or []):
        p_name = str(place.get("Business name") or place.get("business_name") or place.get("name") or "")
        clean_p_name = normalize_text(p_name)
        if clean_target in clean_p_name or clean_p_name in clean_target:
            return place
        score = similarity_score(clean_target, clean_p_name)
        if score > highest_score and score >= 0.75:
            highest_score, best_match = score, place
    return best_match