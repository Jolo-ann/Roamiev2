# nlp_engine.py
import re
import math
import difflib
import unicodedata
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
    "searching for laoag", "searching in laoag", "search laoag",
    "help", "what can you do", "hi", "hello"
}

def is_non_search_input(text):
    clean = normalize_text(text)
    return clean in NON_SEARCH_PHRASES or any(clean == p for p in NON_SEARCH_PHRASES)

def normalize_text(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    text = text.lower().replace("’", "'").replace('"', '').replace("–", "-").replace("—", "-").replace("/", " ")
    return re.sub(r"\s+", " ", text).strip()

def tokenize_text(text):
    return wordpunct_tokenize(normalize_text(text))

def singularize_word(word):
    word = str(word).lower().strip()
    irregular = {
        "restaurants": "restaurant", "cafes": "cafe", "hotels": "hotel",
        "hospitals": "hospital", "banks": "bank", "gyms": "gym",
        "resorts": "resort", "stores": "store", "places": "place",
        "groceries": "grocery", "supermarkets": "supermarket",
        "pharmacies": "pharmacy", "veterinaries": "veterinary",
        "drinks": "drink", "bars": "bar", "airplanes": "airplane", "planes": "plane"
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
    if len(clean) < n:
        return [clean]
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
    if len(text_words) < phrase_len:
        return False
    for i in range(len(text_words) - phrase_len + 1):
        if similarity_score(" ".join(text_words[i:i + phrase_len]), clean_phrase) >= threshold:
            return True
    return False

def phrase_present(text, phrase):
    return fuzzy_phrase_present(text, phrase, threshold=0.82)

NEGATION_TRIGGERS = {
    "no", "not", "dont", "don't", "dont want", "don't want", "doesnt", "doesn't", 
    "except", "excluding", "without", "other than", "hate", "avoid", "instead of",
    "dont like", "don't like", "dislike", "not a fan of"
}

def is_span_negated(text, span_start):
    prefix = text[:span_start].strip()
    words = re.findall(r"\b\w+[\'\w]*\b", prefix)
    window = " ".join(words[-4:]).lower() if words else ""
    return any(re.search(rf"\b{re.escape(t)}\b", window) for t in NEGATION_TRIGGERS)

def detect_unsupported_intent(text):
    clean = normalize_text(text)
    unsupported_keywords = [
        "reserve", "reservation", "book a table", "booking",
        "waiting line", "waiting time", "how long is the line", "how long is the wait",
        "generator", "brownout", "power outage", "blackout", "wifi password",
        "order online", "deliver to my house", "menu", "price of"
    ]
    for kw in unsupported_keywords:
        if re.search(rf"\b{re.escape(kw)}\b", clean) or kw in clean:
            return kw
    return None

def detect_location_entities(text):
    clean, found = normalize_text(text), []
    for municipality, aliases in MUNICIPALITY_ALIASES.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            match = re.search(rf"\b{re.escape(alias_norm)}\b", clean)
            if match:
                found.append((municipality, match.start()))
                break
    # Sort by position in the text so the LAST mentioned location is chosen by the app
    found.sort(key=lambda x: x[1])
    return [f[0] for f in found]

def detect_unsupported_location(text):
    clean = normalize_text(text)
    
    # FIX: Check the UNSUPPORTED_LOCATIONS from config.py first!
    for loc in UNSUPPORTED_LOCATIONS:
        if re.search(rf"\b{re.escape(loc)}\b", clean):
            return loc.title()

    KNOWN_UNSUPPORTED = [
        "vigan", "baguio", "manila", "candon", "la union", "pangasinan", 
        "ilocos sur", "abra", "cagayan", "isabela", "tuguegarao", "africa", 
        "cebu", "davao", "boracay", "subic", "clark", "pampanga", "bulacan"
    ]
    for loc in KNOWN_UNSUPPORTED:
        if re.search(rf"\b{re.escape(loc)}\b", clean):
            return loc.title()
    words = clean.split()
    if len(words) == 1 and len(clean) >= 3:
        is_supported = any(clean in aliases or clean == muni for muni, aliases in MUNICIPALITY_ALIASES.items())
        if not is_supported:
            if not detect_category_entity(clean) and not detect_feature_entities(clean) and not detect_dish_entity(clean):
                return clean.title()
    return None

def detect_category_entity(text):
    clean = normalize_text(text)
    if not clean:
        return None
        
    # Universal Intent Mapping
    if any(w in clean for w in ["hungry", "starving", "want to eat", "need food", "meal", "eat", "food"]):
        return "restaurant"
    if any(w in clean for w in ["thirsty", "want a drink", "refreshment", "drink"]):
        return "cafe"

    clean_sing = " ".join(normalized_tokens(clean))
    matches = []
    for category, aliases in CATEGORY_SYNONYMS.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            alias_sing = singularize_word(alias_norm)
            for target_text in [clean, clean_sing]:
                for m in re.finditer(rf"\b{re.escape(alias_sing)}\b", target_text):
                    if not is_span_negated(clean, m.start()):
                        matches.append((len(alias_sing), m.start(), category))
                if alias_sing in target_text and len(alias_sing) > 3:
                    if not any(cat == category for _, _, cat in matches):
                        matches.append((len(alias_sing), target_text.find(alias_sing), category))

    if not matches:
        for word in clean.split():
            if len(word) > 3: 
                for category, aliases in CATEGORY_SYNONYMS.items():
                    close_matches = difflib.get_close_matches(word, aliases, n=1, cutoff=0.75)
                    if close_matches:
                        return category
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    return matches[0][2]

def detect_exclusions(text):
    clean, exclusions = normalize_text(text), []
    pattern = r"\b(?:dont want|don't want|dont like|don't like|hate|dislike|not a fan of|no|not|excluding|except|without|other than)\b\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s]+)"
    for match in re.findall(pattern, clean):
        clause = re.split(r'[.,!?]', match)[0].strip()
        for cat_key, synonyms in CATEGORY_SYNONYMS.items():
            if any(re.search(rf"\b{re.escape(syn)}\b", clause) for syn in synonyms):
                exclusions.append(cat_key)
    return list(set(exclusions))

def detect_excluded_features(text):
    clean = normalize_text(text)
    found = []
    pattern = r"\b(?:dont want|don't want|dont like|don't like|no|not|excluding|except|without|other than)\b\s+(?:a\s+|an\s+|the\s+)?([a-z\s]+)"
    for match in re.finditer(pattern, clean):
        phrase = match.group(1).strip()
        for feat, aliases in FEATURE_ALIASES.items():
            for alias in aliases:
                if alias in phrase:
                    found.append(feat)
                    break
    return list(set(found))

def detect_excluded_locations(text):
    clean = normalize_text(text)
    found = []
    pattern = r"\b(?:dont like|don't like|hate|dislike|not a fan of|excluding|not in|avoid)\b\s+(\w+)"
    for match in re.finditer(pattern, clean):
        word = match.group(1).strip()
        for muni, aliases in MUNICIPALITY_ALIASES.items():
            if word in aliases or word == muni:
                found.append(muni)
                break
    return list(set(found))

def detect_feature_entities(text):
    clean = normalize_text(text)
    found = []
    for feat, aliases in FEATURE_ALIASES.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if feat == "pet-friendly" and any(w in clean for w in ["vet", "veterinary", "clinic"]):
                continue
            for m in re.finditer(rf"\b{re.escape(alias_norm)}\b", clean):
                if not is_span_negated(clean, m.start()):
                    found.append(feat)
                    break
    m_feat = re.search(r"\b(?:with|has|offering|serves?|serving)\s+([a-z\s]+)", clean)
    if m_feat:
        ext = m_feat.group(1).strip()
        stop_phrases = {"card", "can i", "can", "i", "a", "the", "in", "near", "for", "me", "pesos", "php"}
        ext_words = ext.split()
        if len(ext_words) <= 2 and ext not in found and len(ext) > 2 and ext not in stop_phrases:
            if not any(c.isdigit() for c in ext):
                found.append(ext)
    return list(set(found))

def detect_dish_entity(text):
    clean = normalize_text(text)
    for dish in sorted(LOCAL_DISHES, key=len, reverse=True):
        if phrase_present(clean, dish):
            return dish
    return None

def parse_time_to_minutes(time_str):
    if not time_str:
        return None
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?", str(time_str).strip().upper())
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
    if not hours_str:
        return None, None
    try:
        parts = re.split(r"\s*(?:-|–|to)\s*", str(hours_str).strip(), flags=re.IGNORECASE)
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
                if str(k).strip().lower() == str(target_day).strip().lower():
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
        r"\b(?:only\s*have|have|budget|under|below|less than|up to|max|cheap|with|spend|buy|for|how about|what about)\b.*?(?:₱|php|p)?\s*(\d[\d,]*)",
        r"^\s*(\d[\d,]*)\s*$"
    ]
    for p in patterns:
        for m in re.finditer(p, clean, flags=re.IGNORECASE):
            try:
                full_match = m.group(0)
                if re.search(r'\d+\s*(?::\d+|am|pm|o\'clock)', full_match, re.IGNORECASE):
                    continue
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
    excluded_locs = detect_excluded_locations(clean_text)
    locations = [loc for loc in locations if loc not in excluded_locs]
    
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    target_day = next((day for day in days if re.search(rf"\b{day}\b", clean_text)), None)

    constraints = {
        "category": detect_category_entity(clean_text),
        "exclusions": detect_exclusions(clean_text),
        "excluded_features": detect_excluded_features(clean_text),
        "excluded_locations": excluded_locs,
        "locations": locations,
        "location": locations[-1] if locations else None,
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

def lexical_overlap_score(query_text, place_text, place_corpus_list=None, idf_cache=None):
    q_tokens, p_tokens = content_tokens(query_text), content_tokens(place_text)
    if not q_tokens or not p_tokens:
        return 0.0
    word_counts = Counter(p_tokens)
    tfidf_score = 0.0
    for token in set(q_tokens):
        matched_word = token if token in word_counts else next((w for w in word_counts if similarity_score(token, w) >= 0.85), None)
        if matched_word:
            tf = word_counts[matched_word] / float(len(p_tokens))
            if idf_cache and token in idf_cache:
                idf = idf_cache[token]
            else:
                num_docs = len(place_corpus_list) if place_corpus_list else 1
                df = sum(1 for doc in place_corpus_list if token in str(doc).lower()) if place_corpus_list else 1
                idf = math.log((1.0 + num_docs) / (1.0 + df)) + 1.0
            tfidf_score += tf * idf
    return (tfidf_score * 0.50) + (ngram_similarity(query_text, place_text) * 0.50)

def extract_place_name_query(text):
    clean = normalize_text(text)
    patterns = [
        r"\bwhere\s+is\s+(.+)", r"\bwhere\s+can\s+i\s+find\s+(.+)",
        r"\bwhere\s+to\s+find\s+(.+)", r"\bi\s+want\s+to\s+eat\s+at\s+(.+)",
        r"\bi\s+want\s+to\s+go\s+to\s+(.+)", r"\bhow\s+to\s+get\s+to\s+(.+)"
    ]
    for p in patterns:
        m = re.search(p, clean)
        if m:
            cleaned = re.sub(r"[^\w\s]", "", m.group(1).strip()).strip()
            cleaned = re.sub(r"\b(nearest|restaurant|hotel|shop|store|the|a|an|in|at|near)\b", "", cleaned).strip()
            
            if cleaned and cleaned not in MUNICIPALITIES and cleaned not in ["laoag city", "batac city"]:
                is_just_category = False
                for cat, aliases in CATEGORY_SYNONYMS.items():
                    if cleaned in aliases or cleaned == cat:
                        is_just_category = True
                        break
                if not is_just_category:
                    return cleaned
    return None

def find_place_globally(text, places_list):
    target_name = extract_place_name_query(text) or text
    clean_target = normalize_text(target_name)
    if not clean_target or clean_target in MUNICIPALITIES:
        return None
        
    best_match, highest_score = None, 0.0
    for place in (places_list or []):
        p_name = ""
        for k in ["Business name", "Business Name", "business_name", "name"]:
            if k in place and place[k]:
                p_name = str(place[k])
                break
        if not p_name: continue
        
        clean_p_name = normalize_text(p_name)
        if not clean_p_name: continue
        
        # 1. Direct substring match (e.g., "bdo unibank" in "BDO Unibank - Laoag Main")
        if clean_p_name in clean_target or clean_target in clean_p_name:
            return place
            
        # 2. Fuzzy phrase match (e.g., "beam me up" -> "Bean Me Up")
        if fuzzy_phrase_present(clean_target, clean_p_name, threshold=0.75):
            return place
            
        # 3. Sequence matcher score
        score = similarity_score(clean_target, clean_p_name)
        if score > highest_score and score >= 0.65:
            highest_score, best_match = score, place
            
    # 4. Fallback for word overlap (e.g., "bdo unibank" -> "bdo network bank")
    if not best_match:
        target_words = set(clean_target.split())
        valid_words = [w for w in target_words if len(w) > 2]
        if valid_words:
            for place in (places_list or []):
                p_name = str(next((place[k] for k in ["Business name", "business_name", "name"] if k in place and place[k]), ""))
                clean_p_name = normalize_text(p_name)
                if all(w in clean_p_name for w in valid_words):
                    return place

    return best_match