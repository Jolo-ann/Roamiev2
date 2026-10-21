# nlp_engine.py
import re
import math
from collections import Counter
from difflib import SequenceMatcher
from nltk.tokenize import wordpunct_tokenize
from nltk.tree import Tree

from config import (
    MUNICIPALITIES, MUNICIPALITY_ALIASES, UNSUPPORTED_LOCATIONS, 
    CATEGORY_SYNONYMS, LOCAL_DISHES, FEATURE_ALIASES, STOPWORDS, 
    GEOGRAPHIC_COORDINATES
)

# 1. TEXT PROCESSING & TOKENIZATION UTILITIES
def normalize_text(text):
    text = str(text or "").lower()
    text = text.replace("’", "'").replace('"', '')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

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
    return [
        singularize_word(token)
        for token in tokenize_text(text)
        if re.search(r"[a-z0-9]", token)
    ]

# 2. HAVERSINE PROXIMITY CALCULATOR
def haversine_distance(coord1, coord2):
    if not coord1 or not coord2:
        return 999.0
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371.0  # Radius of Earth in KM

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# 3. FUZZY MATCHING & N-GRAM RECOGNITION
def similarity_score(a, b):
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

def get_character_ngrams(text, n=3):
    clean = f"${normalize_text(text)}$"
    return [clean[i:i+n] for i in range(len(clean) - n + 1)]

def ngram_similarity(str1, str2, n=3):
    ngrams1 = set(get_character_ngrams(str1, n))
    ngrams2 = set(get_character_ngrams(str2, n))
    if not ngrams1 or not ngrams2:
        return 0.0
    return len(ngrams1.intersection(ngrams2)) / len(ngrams1.union(ngrams2))

def fuzzy_phrase_present(text, phrase, threshold=0.80):
    clean_text = normalize_text(text)
    clean_phrase = normalize_text(phrase)
    
    if not clean_phrase or not clean_text:
        return False
        
    if re.search(rf"(?<!\w){re.escape(clean_phrase)}(?!\w)", clean_text):
        return True
        
    text_words = clean_text.split()
    phrase_words = clean_phrase.split()
    phrase_len = len(phrase_words)
    
    for i in range(len(text_words) - phrase_len + 1):
        window = " ".join(text_words[i:i + phrase_len])
        if similarity_score(window, clean_phrase) >= threshold:
            return True
            
    return False

def phrase_present(text, phrase):
    return fuzzy_phrase_present(text, phrase, threshold=0.82)

# 4. ENTITY DETECTORS
def detect_location_entities(text):
    clean = normalize_text(text)
    found_locations = set()
    for municipality, aliases in MUNICIPALITY_ALIASES.items():
        for alias in aliases:
            if phrase_present(clean, alias):
                found_locations.add(municipality)
                break
    return list(found_locations)

def detect_unsupported_location(text):
    clean = normalize_text(text)
    for loc in UNSUPPORTED_LOCATIONS:
        if phrase_present(clean, loc):
            return loc.title()
    return None

def detect_category_entity(text):
    clean = normalize_text(text)
    matches = []
    for category, aliases in CATEGORY_SYNONYMS.items():
        for alias in aliases:
            if phrase_present(clean, alias):
                matches.append((len(alias), category))
                break
    if not matches:
        return None
    matches.sort(reverse=True)
    return matches[0][1]

def detect_exclusions(text):
    clean = normalize_text(text)
    exclusions = []
    exclusion_patterns = [
        r"(?:don'?t want|no|not|excluding|except)\s+([a-z\s]+)",
    ]
    for pattern in exclusion_patterns:
        matches = re.findall(pattern, clean)
        for match in matches:
            for category in CATEGORY_SYNONYMS.keys():
                if category in match:
                    exclusions.append(category)
    return exclusions

def detect_feature_entities(text):
    clean = normalize_text(text)
    found = []
    for feature, aliases in FEATURE_ALIASES.items():
        if any(phrase_present(clean, alias) for alias in aliases):
            found.append(feature)
    return found

def detect_dish_entity(text):
    clean = normalize_text(text)
    sorted_dishes = sorted(LOCAL_DISHES, key=len, reverse=True)
    for dish in sorted_dishes:
        if phrase_present(clean, dish):
            return dish
    return None

# 5. OPERATING HOURS & BUDGET PARSERS
def parse_time_to_minutes(time_str):
    time_str = str(time_str or "").strip().upper()
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", time_str)
    if not match:
        return None

    hours = int(match.group(1))
    minutes = int(match.group(2)) if match.group(2) else 0
    period = match.group(3)

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
        clean = str(hours_str or "").strip()
        parts = re.split(r"\s*(?:-|–|to)\s*", clean, flags=re.IGNORECASE)
        if len(parts) != 2:
            return None, None

        open_min = parse_time_to_minutes(parts[0])
        close_min = parse_time_to_minutes(parts[1])

        if close_min is not None and open_min is not None and close_min <= open_min:
            close_min += 24 * 60

        return open_min, close_min
    except Exception:
        return None, None

def parse_budget(query_text):
    clean = normalize_text(query_text)
    patterns = [
        r"(?:₱|php\s*|p\s*)\s*(\d[\d,]*(?:\.\d+)?)",
        r"(\d[\d,]*(?:\.\d+)?)\s*(?:pesos?|php)",
        r"\b(?:under|below|less than|up to|within|max(?:imum)?(?: budget)? of|cheap|affordable|budget)\b.*?(?:₱|php|p)?\s*(\d[\d,]*)",
    ]
    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, clean, flags=re.IGNORECASE):
            try:
                raw = match.group(1).replace(",", "")
                value = float(raw)
                if value > 10:
                    candidates.append(int(value))
            except (ValueError, IndexError):
                pass

    budget_words = ["budget", "price", "cost", "cheap", "affordable", "under", "below", "less than", "pesos", "php", "₱"]
    if not any(word in clean for word in budget_words):
        return None

    return min(candidates) if candidates else None

def parse_target_closing_time(query_text):
    clean = normalize_text(query_text)
    pattern = r"\b(?:until|till|open until|open till|past|at least|up to|open late|late night)\b\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
    match = re.search(pattern, clean, flags=re.IGNORECASE)
    if not match:
        return None
    return parse_time_to_minutes(match.group(1))

# 6. NATURAL LANGUAGE PARSER & QUERY TREE GENERATOR
def build_query_parse_tree(query_text, constraints):
    children = []
    if constraints.get("category"):
        children.append(Tree("CATEGORY", [constraints["category"]]))
    if constraints.get("locations"):
        children.append(Tree("LOCATIONS", constraints["locations"]))
    if constraints.get("exclusions"):
        children.append(Tree("EXCLUSIONS", constraints["exclusions"]))
    if constraints.get("required_features"):
        children.append(Tree("FEATURES", [Tree("FEATURE", [feature]) for feature in constraints["required_features"]]))
    if constraints.get("dish"):
        children.append(Tree("DISH", [constraints["dish"]]))
    if constraints.get("max_budget") is not None:
        children.append(Tree("BUDGET", [str(constraints["max_budget"])]))
    if constraints.get("target_closing_time") is not None:
        children.append(Tree("CLOSING_TIME", [str(constraints["target_closing_time"])]))
    if not children:
        children.append(Tree("TEXT", list(normalized_tokens(query_text))))
    return Tree("QUERY", children)

def extract_constraints_nlp(query_text):
    clean_text = normalize_text(query_text)
    tokens = tokenize_text(clean_text)
    locations = detect_location_entities(clean_text)

    constraints = {
        "category": detect_category_entity(clean_text),
        "exclusions": detect_exclusions(clean_text),
        "locations": locations,
        "location": locations[0] if locations else None,
        "dish": detect_dish_entity(clean_text),
        "max_budget": parse_budget(clean_text),
        "required_features": detect_feature_entities(clean_text),
        "target_closing_time": parse_target_closing_time(clean_text),
        "raw_query": query_text,
        "tokens": tokens,
        "parse_tree": None,
    }

    constraints["parse_tree"] = build_query_parse_tree(query_text, constraints)
    return constraints

# 7. TF-IDF & LEXICAL SCORING ENGINE
def content_tokens(text):
    return [
        singularize_word(token)
        for token in normalized_tokens(text)
        if token not in STOPWORDS and len(token) > 1
    ]

def lexical_overlap_score(query_text, place_text, place_corpus_list):
    q_tokens = content_tokens(query_text)
    p_tokens = content_tokens(place_text)

    if not q_tokens or not p_tokens:
        return 0.0

    num_docs = len(place_corpus_list) if place_corpus_list else 1
    doc_words = p_tokens
    word_counts = Counter(doc_words)

    tfidf_score = 0.0
    for token in set(q_tokens):
        matched_word = token if token in word_counts else None
        if not matched_word:
            for w in word_counts.keys():
                if similarity_score(token, w) >= 0.85:
                    matched_word = w
                    break
        if matched_word:
            tf = word_counts[matched_word] / len(doc_words)
            df = sum(1 for doc in place_corpus_list if token in doc.lower())
            idf = math.log((1 + num_docs) / (1 + df)) + 1.0
            tfidf_score += tf * idf

    ngram_score = ngram_similarity(query_text, place_text)
    return (tfidf_score * 0.50) + (ngram_score * 0.50)

def extract_place_name_query(text):
    """Extracts target place name only for direct venue queries like 'where is Eagles Nest?'."""
    clean = normalize_text(text)
    
    # Skip if it's a category recommendation query
    if any(k in clean for k in ["cafe", "restaurant", "hotel", "hospital", "bank", "gym", "bar", "coffee"]):
        return None

    patterns = [
        r"\bwhere\s+is\s+(.+)",
        r"\bwhere\s+can\s+i\s+find\s+(.+)",
        r"\bwhere\s+to\s+find\s+(.+)",
        r"\bi\s+want\s+to\s+eat\s+at\s+(.+)",
        r"\bi\s+want\s+to\s+go\s+to\s+(.+)",
        r"\bhow\s+to\s+get\s+to\s+(.+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, clean)
        if match:
            extracted = match.group(1).strip()
            cleaned_target = re.sub(r"[^\w\s]", "", extracted).strip()
            if cleaned_target and cleaned_target not in MUNICIPALITIES and cleaned_target not in ["laoag city", "batac city"]:
                return cleaned_target
    return None