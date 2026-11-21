# app.py
import json
import re
import math
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, render_template, session
from config import (
    STATE_IDLE, MUNICIPALITIES, 
    MUNICIPALITY_ALIASES, CATEGORY_SYNONYMS, FEATURE_ALIASES,
    THINKING_PHRASES, READY_PHRASES, GREETINGS, THANKS_PHRASES # <-- ADD THANKS_PHRASES
)

from config import (
    STATE_IDLE, MUNICIPALITIES, 
    MUNICIPALITY_ALIASES, CATEGORY_SYNONYMS, FEATURE_ALIASES,
    THINKING_PHRASES, READY_PHRASES, GREETINGS
)
from nlp_engine import (
    normalize_text, normalized_tokens, extract_constraints_nlp,
    detect_location_entities, detect_unsupported_location,
    detect_category_entity, detect_feature_entities,
    extract_operating_bounds, lexical_overlap_score, phrase_present,
    extract_place_name_query, is_non_search_input, find_place_globally,
    content_tokens, detect_unsupported_intent, similarity_score
)

app = Flask(__name__)
app.secret_key = "roamie_production_key_fixed"

# --- WEATHER DATA ---
WEATHER_COORDS = {
    "laoag": {"lat": 18.1960, "lon": 120.5927, "name": "Laoag City"},
    "batac": {"lat": 18.0556, "lon": 120.5650, "name": "Batac City"},
    "pagudpud": {"lat": 18.5583, "lon": 120.7861, "name": "Pagudpud"},
    "paoay": {"lat": 18.0617, "lon": 120.5211, "name": "Paoay"},
    "bacarra": {"lat": 18.2511, "lon": 120.6128, "name": "Bacarra"},
    "burgos": {"lat": 18.5144, "lon": 120.6458, "name": "Burgos"},
    "bangui": {"lat": 18.5378, "lon": 120.7678, "name": "Bangui"},
    "badoc": {"lat": 17.9264, "lon": 120.4725, "name": "Badoc"},
    "sarrat": {"lat": 18.1672, "lon": 120.6542, "name": "Sarrat"},
    "vintar": {"lat": 18.2300, "lon": 120.6400, "name": "Vintar"},
    "san nicolas": {"lat": 18.1725, "lon": 120.5958, "name": "San Nicolas"},
    "dingras": {"lat": 18.1000, "lon": 120.7000, "name": "Dingras"},
    "solsona": {"lat": 18.0933, "lon": 120.7719, "name": "Solsona"},
    "piddig": {"lat": 18.1644, "lon": 120.7078, "name": "Piddig"},
    "pasuquin": {"lat": 18.3333, "lon": 120.6167, "name": "Pasuquin"},
    "adams": {"lat": 18.4617, "lon": 120.8931, "name": "Adams"},
    "banna": {"lat": 17.9833, "lon": 120.6500, "name": "Banna"},
    "marcos": {"lat": 18.0333, "lon": 120.6833, "name": "Marcos"},
    "nueva era": {"lat": 17.9167, "lon": 120.6667, "name": "Nueva Era"},
    "pinili": {"lat": 17.9500, "lon": 120.5333, "name": "Pinili"}
}

WEATHER_CODES_MAP = {
    0: "☀️ Clear Sky", 1: "🌤️ Mainly Clear", 2: "⛅ Partly Cloudy", 3: "☁️ Overcast",
    45: "🌫️ Foggy", 48: "🌫️ Depositing Rime Fog", 51: "🌦️ Light Drizzle", 53: "🌦️ Moderate Drizzle",
    55: "🌧️ Dense Drizzle", 61: "🌧️ Slight Rain", 63: "🌧️ Moderate Rain", 65: "🌧️ Heavy Rain",
    80: "🌦️ Slight Rain Showers", 81: "🌧️ Moderate Rain Showers", 82: "⛈️ Violent Rain Showers",
    95: "⛈️ Thunderstorm"
}

MUNICIPALITY_COORDS = {
    "laoag": {"lat": 18.1960, "lon": 120.5927},
    "batac": {"lat": 18.0556, "lon": 120.5650},
    "pagudpud": {"lat": 18.5583, "lon": 120.7861},
    "paoay": {"lat": 18.0617, "lon": 120.5211},
    "bacarra": {"lat": 18.2511, "lon": 120.6128},
    "burgos": {"lat": 18.5144, "lon": 120.6458},
    "bangui": {"lat": 18.5378, "lon": 120.7678},
    "badoc": {"lat": 17.9264, "lon": 120.4725},
    "sarrat": {"lat": 18.1672, "lon": 120.6542},
    "vintar": {"lat": 18.2300, "lon": 120.6400},
    "san nicolas": {"lat": 18.1725, "lon": 120.5958},
    "solsona": {"lat": 18.0933, "lon": 120.7719},
    "adams": {"lat": 18.4617, "lon": 120.8931},
    "banna": {"lat": 17.9833, "lon": 120.6500},
    "marcos": {"lat": 18.0333, "lon": 120.6833},
    "nueva era": {"lat": 17.9167, "lon": 120.6667},
    "pinili": {"lat": 17.9500, "lon": 120.5333}
}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def load_dataset():
    try:
        with open("dataset.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading dataset.json: {e}")
        return {}

dataset = load_dataset()

def get_all_places():
    if isinstance(dataset, dict):
        places = []
        for city_places in dataset.values():
            if isinstance(city_places, list):
                places.extend(city_places)
        return places
    return dataset if isinstance(dataset, list) else []

ALL_PLACES = get_all_places()

def get_place_attr(place, keys, default="N/A"):
    for key in keys:
        if key in place and place[key] not in [None, "", "N/A"]:
            return place[key]
            
    norm_keys = [str(k).lower().replace("_", " ").strip() for k in keys]
    for place_key, value in place.items():
        norm_pk = str(place_key).lower().replace("_", " ").strip()
        if norm_pk in norm_keys and value not in [None, "", "N/A"]:
            return value
            
    return default

def evaluate_category_match(place, requested_category):
    if not requested_category:
        return 2

    primary_cat = normalize_text(str(get_place_attr(place, ["Category", "category"], "")))
    aliases = CATEGORY_SYNONYMS.get(requested_category, [requested_category])

    if any(phrase_present(primary_cat, alias) for alias in aliases):
        return 2

    desc = str(get_place_attr(place, ["Short description", "short_description", "Description", "description"], ""))
    keywords = get_place_attr(place, ["Keywords and synonyms", "keywords_synonyms", "keywords"], "")
    keywords_str = " ".join(str(k) for k in keywords) if isinstance(keywords, list) else str(keywords)
    
    secondary_corpus = normalize_text(f"{desc} {keywords_str}")

    if any(phrase_present(secondary_corpus, alias) for alias in aliases):
        return 1

    return 0

def build_place_corpus(place):
    name = str(get_place_attr(place, ["Business name", "business_name", "name"], ""))
    cat = str(get_place_attr(place, ["Category", "category"], ""))
    city = str(get_place_attr(place, ["Municipality or city", "Municipality/City", "municipality_city", "city", "municipality"], ""))
    desc = str(get_place_attr(place, ["Short description", "short_description", "description"], ""))
    feats = get_place_attr(place, ["Features", "features"], [])
    feats_str = " ".join(str(f) for f in feats) if isinstance(feats, list) else str(feats)
    keywords = get_place_attr(place, ["Keywords and synonyms", "keywords_synonyms", "keywords"], "")
    keywords_str = " ".join(str(k) for k in keywords) if isinstance(keywords, list) else str(keywords)

    return f"{name}. Category: {cat}. Location: {city}. Details: {desc} Features: {feats_str} Keywords: {keywords_str}"

PLACE_CORPUS = [build_place_corpus(p) for p in ALL_PLACES]
PLACE_CORPUS_LOWER = [c.lower() for c in PLACE_CORPUS]

def location_matches(place, requested_locations):
    if not requested_locations:
        return True
    if isinstance(requested_locations, str):
        requested_locations = [requested_locations]
        
    city_text = normalize_text(str(get_place_attr(place, ["Municipality or city", "Municipality/City", "municipality_city", "city", "municipality", "Municipality"], "")))
    
    for req_loc in requested_locations:
        aliases = MUNICIPALITY_ALIASES.get(req_loc.lower(), [req_loc])
        if any(normalize_text(alias) in city_text or phrase_present(city_text, alias) for alias in aliases):
            return True
    return False

def place_has_feature(place, feature):
    feats_raw = get_place_attr(place, ["Features", "features"], [])
    feature_text = " ".join(str(item) for item in feats_raw) if isinstance(feats_raw, list) else str(feats_raw)
    description = str(get_place_attr(place, ["Short description", "short_description", "Description", "description"], ""))
    keywords_raw = get_place_attr(place, ["Keywords and synonyms", "keywords_synonyms", "keywords"], "")
    keywords = " ".join(str(item) for item in keywords_raw) if isinstance(keywords_raw, list) else str(keywords_raw)

    combined = normalize_text(f"{feature_text} {description} {keywords}")
    aliases = FEATURE_ALIASES.get(feature, [feature])
    return any(phrase_present(combined, alias) for alias in aliases)

def place_has_dish(place, dish):
    if not dish:
        return False
    name = str(get_place_attr(place, ["Business name", "business_name", "name"], ""))
    desc = str(get_place_attr(place, ["Short description", "short_description", "Description", "description"], ""))
    keywords_raw = get_place_attr(place, ["Keywords and synonyms", "keywords_synonyms", "keywords"], "")
    keywords = " ".join(str(item) for item in keywords_raw) if isinstance(keywords_raw, list) else str(keywords_raw)
    
    combined_content = normalize_text(f"{name} {desc} {keywords}")
    pattern = r"\b" + re.escape(normalize_text(dish)) + r"\b"
    return bool(re.search(pattern, combined_content))

def price_number_from_place(place):
    price = str(get_place_attr(place, ["Price range", "price_range", "Price Range"], ""))
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", price)
    values = []

    for number in numbers:
        try:
            values.append(float(number.replace(",", "")))
        except ValueError:
            pass

    return min(values) if values else None

def is_acronym_match(query, text):
    if len(query.split()) == 1 and len(query) >= 2:
        words = re.findall(r'\b\w', text)
        acronym = "".join(words).lower()
        if query == acronym:
            return True
    return False

def score_and_rank_places_nlp(constraints, session_location=None):
    if not ALL_PLACES:
        return []

    requested_category = constraints.get("category")
    requested_exclusions = constraints.get("exclusions", [])
    requested_locations = constraints.get("locations") or ([session_location] if session_location else [])
    requested_features = constraints.get("required_features", [])
    requested_excluded_features = constraints.get("excluded_features", [])
    requested_excluded_locations = constraints.get("excluded_locations", [])
    requested_dish = constraints.get("dish")
    target_open_min = constraints.get("target_opening_time")
    target_close_min = constraints.get("target_closing_time")
    target_day = constraints.get("target_day")
    requested_budget = constraints.get("max_budget")
    query_text = constraints.get("raw_query", "")

    q_tokens = set(content_tokens(query_text))
    num_docs = len(PLACE_CORPUS)
    idf_cache = {}
    for token in q_tokens:
        df = sum(1 for doc in PLACE_CORPUS_LOWER if token in doc)
        idf_cache[token] = math.log((1.0 + num_docs) / (1.0 + df)) + 1.0

    has_primary_category_match = False
    if requested_category:
        for p in ALL_PLACES:
            if location_matches(p, requested_locations) and evaluate_category_match(p, requested_category) == 2:
                has_primary_category_match = True
                break

    scored_places = []
    
    for idx, place in enumerate(ALL_PLACES):
        p_cat = normalize_text(str(get_place_attr(place, ["Category", "category"], "")))

        cat_match_level = evaluate_category_match(place, requested_category)
        if requested_category:
            if cat_match_level == 0:
                continue
            if has_primary_category_match and cat_match_level < 2:
                continue

        if requested_exclusions and any(excluded in p_cat for excluded in requested_exclusions):
            continue

        if requested_locations and not location_matches(place, requested_locations):
            continue

        if requested_excluded_locations and location_matches(place, requested_excluded_locations):
            continue

        if requested_budget is not None:
            min_price = price_number_from_place(place)
            if min_price is None or min_price > requested_budget:
                continue

        raw_hours = get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"])
        place_open_min, place_close_min = extract_operating_bounds(raw_hours, target_day=target_day)

        # FIX: "open at X" means the place must be open during that time (not exactly at open time)
        if target_open_min is not None:
            if place_open_min is None or place_close_min is None:
                continue
            if not (place_open_min <= target_open_min < place_close_min):
                continue

        if target_close_min is not None:
            if place_close_min is None or place_close_min != target_close_min:
                continue

        if requested_features:
            matched_count = sum(1 for feat in requested_features if place_has_feature(place, feat))
            if matched_count == 0:
                continue

        if requested_excluded_features:
            if any(place_has_feature(place, feat) for feat in requested_excluded_features):
                continue    

        place_corpus = PLACE_CORPUS[idx]
        score = 0.0
        lexical_score = lexical_overlap_score(query_text, place_corpus, idf_cache=idf_cache)

        if requested_dish:
            if place_has_dish(place, requested_dish):
                score += 50.0 + min(20.0, lexical_score * 20.0)
            else:
                continue
        elif requested_category:
            base_cat_score = 65.0 if cat_match_level == 2 else 25.0
            score += base_cat_score + min(15.0, lexical_score * 15.0)
        else:
            if requested_locations:
                score += 60.0 + min(30.0, lexical_score * 30.0)
            else:
                if lexical_score < 0.15:
                    continue
                score += min(50.0, lexical_score * 50.0)

        if requested_locations:
            score += 20.0

        final_score = max(0.0, min(100.0, round(score, 2)))

        if final_score >= 50.0:
            scored_places.append({"place": place, "score": final_score})

    is_affordable_query = any(w in query_text.lower() for w in ["affordable", "cheap", "budget", "mura", "inexpensive", "low cost", "low price", "student friendly"])
    is_nearest_query = any(w in query_text.lower() for w in ["nearest", "closest", "close", "near me", "malapit", "near", "nearby"])

    if is_affordable_query:
        def get_price_key(item):
            price = price_number_from_place(item["place"])
            return price if price is not None else float('inf')
        scored_places.sort(key=lambda item: (get_price_key(item), -item["score"]))
        
    elif is_nearest_query:
        reference_lat, reference_lon = None, None
        ref_name = "town center"

        # Try to extract the specific landmark text
        match = re.search(r"\b(?:near|nearby|around|close to|in|at)\s+([a-z0-9\s,]+)", query_text, re.IGNORECASE)
        if match:
            landmark_query = match.group(1).strip()
            # Clean up: remove anything after "where", "that", comma, etc.
            landmark_query = re.split(r'\b(?:where|that|which|is|are)\b|,|\?', landmark_query)[0].strip()
            
            if landmark_query:
                best_match, highest_score = None, 0.0
                for p in ALL_PLACES:
                    p_name = str(get_place_attr(p, ["Business name", "business_name", "name"], "")).lower()
                    score = similarity_score(landmark_query, p_name)
                    if score > highest_score and score >= 0.70:
                        highest_score, best_match = score, p
                
                if best_match:
                    reference_lat = best_match.get("latitude")
                    reference_lon = best_match.get("longitude")
                    ref_name = str(get_place_attr(best_match, ["Business name", "business_name", "name"], ""))
        
        # Fallback to town center
        if reference_lat is None and requested_locations:
            target_town = requested_locations[0].lower()
            town_center = MUNICIPALITY_COORDS.get(target_town)
            if town_center:
                reference_lat = town_center["lat"]
                reference_lon = town_center["lon"]
                ref_name = f"{target_town.title()} town center"

        if reference_lat is not None and reference_lon is not None:
            for item in scored_places:
                place = item["place"]
                lat = place.get("latitude")
                lon = place.get("longitude")
                
                if lat and lon:
                    try:
                        dist = haversine(reference_lat, reference_lon, float(lat), float(lon))
                        item["distance"] = round(dist, 3)
                        item["ref_name"] = ref_name
                        
                        proximity_score = max(0, 100 - (dist * 10)) 
                        blended_score = (item["score"] * 0.4) + (proximity_score * 0.6)
                        
                        if item["score"] >= 50.0:
                            item["score"] = round(max(50.1, blended_score), 2)
                        else:
                            item["score"] = round(blended_score, 2)
                            
                    except Exception:
                        pass
            
            scored_places.sort(key=lambda item: item["score"], reverse=True)
        else:
            scored_places.sort(key=lambda item: item["score"], reverse=True)
    
    return scored_places

def format_hours(value):
    if value is None or value == "":
        return "N/A"
    if isinstance(value, str):
        return value.strip() or "N/A"
    if isinstance(value, dict):
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if any(day in value for day in day_names):
            schedule_groups = {}
            for day in day_names:
                if day not in value:
                    continue
                schedule = value[day]
                if schedule is None or (isinstance(schedule, str) and schedule.strip().lower() in {"closed", "none", "n/a"}):
                    desc = "Closed"
                elif isinstance(schedule, dict):
                    opening = schedule.get("opening")
                    closing = schedule.get("closing")
                    desc = f"{opening}–{closing}" if opening and closing else str(opening or closing or "Not specified")
                else:
                    desc = str(schedule)

                schedule_groups.setdefault(desc, []).append(day.title()[:3])

            if not schedule_groups:
                return "N/A"

            formatted_parts = []
            for time_slot, days in schedule_groups.items():
                day_str = f"{days[0]}–{days[-1]}" if len(days) > 1 else days[0]
                formatted_parts.append(f"{day_str}: {time_slot}")

            return "<br>&nbsp;&nbsp;&nbsp;&nbsp;• " + "<br>&nbsp;&nbsp;&nbsp;&nbsp;• ".join(formatted_parts)

        return "; ".join(f"{label}: {format_hours(schedule)}" for label, schedule in value.items())
    return str(value)

def format_place_output(ranked_results, constraints=None, current_location="Laoag", has_explicit_location=True):
    primary_results = [item for item in ranked_results if item["score"] >= 50.0][:5]
    constraints = constraints or {}
    loc_display = (constraints.get("location") or current_location or "Laoag").title()
    
    if not primary_results:
        req_cat = constraints.get("category")
        req_budget = constraints.get("max_budget")
        req_feat = constraints.get("required_features")
        req_excluded = constraints.get("excluded_features", [])
        req_excl_loc = constraints.get("excluded_locations", [])
        
        reason_parts = []
        if req_cat:
            reason_parts.append(f"<b>'{req_cat}'</b>")
        if req_feat:
            reason_parts.append(f"with <b>'{req_feat[0]}'</b>")
        if req_excluded:
            reason_parts.append(f"without <b>'{req_excluded[0]}'</b>")
        if req_excl_loc:
            reason_parts.append(f"outside <b>{req_excl_loc[0].title()}</b>")
        if req_budget is not None:
            reason_parts.append(f"under <b>₱{int(req_budget)}</b>")
            
        if reason_parts:
            reason_str = " ".join(reason_parts)
            reply = f"I couldn't find any {reason_str} in <b>{loc_display}</b>.<br><br>"
        else:
            reply = f"I couldn't find any matching places in <b>{loc_display}</b>.<br><br>"
        
        if req_budget is not None:
            reply += f"💡 <b>Tip</b>: The places I know in this area usually start at a higher price. Try increasing your budget!<br><br>"
            
        reply += f"<b>What would you like to do?</b><br>"
        reply += f"• Try increasing your budget or relaxing filters.<br>"
        reply += f"• Try searching in another city or municipality."
        return reply

    reply = f"📍 <i>Currently searching in <b>{loc_display}</b></i>"
    
    if not has_explicit_location:
        reply += f"<br>💡 <i>Are you still searching in <b>{loc_display}</b>, or would you like to try a different city/municipality (e.g., San Nicolas, Batac, Bacarra)?</i>"

    reply += "<br><br>Here are the top matching places for your search:<br><br>"
    
    req_cat = constraints.get("category")
    req_dish = constraints.get("dish")
    req_loc = constraints.get("location")
    req_features = constraints.get("required_features", [])

    for idx, item in enumerate(primary_results, 1):
        place = item["place"]
        score = item["score"]
        name = str(get_place_attr(place, ["Business name", "business_name", "name"]))
        cat = str(get_place_attr(place, ["Category", "category"]))
        city = str(get_place_attr(place, ["Municipality or city", "Municipality/City", "municipality_city", "city", "municipality", "Municipality"]))
        hours = format_hours(get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"]))
        price = str(get_place_attr(place, ["Price range", "price_range", "Price Range"]))

        distance = item.get("distance")
        ref_name = item.get("ref_name", "town center")
        
        reply += f"<b>{idx}. {name}</b> ({cat})<br>"
        if distance is not None:
            reply += f"<b>Distance</b>: {distance} km from {ref_name}<br>"
        reply += f"📍 <b>Location</b>: {city}<br>"
        reply += f"⏰ <b>Hours</b>: {hours}<br>"
        reply += f"💰 <b>Price</b>: {price}<br>"
        reply += f"🔍 <b>Match Score</b>: {score}/100<br>"

        if req_dish and place_has_dish(place, req_dish):
            reply += f"• ✅ <b>Dish Match</b>: Serves '<i>{req_dish}</i>'.<br>"
        elif req_cat:
            reply += f"• ✅ <b>Category Match</b>: Matches '<i>{req_cat}</i>'.<br>"
            
        if req_loc:
            reply += f"• ✅ <b>Location Match</b>: Located in '<i>{city}</i>'.<br>"
            
        if req_features:
            matched_feats = [f for f in req_features if place_has_feature(place, f)]
            if matched_feats:
                reply += f"• ✅ <b>Feature Match</b>: Includes {', '.join(matched_feats)}.<br>"

        clean_name = name.replace("'", "\\'")
        reply += f"<button class='inline-place-btn' onclick=\"sendChoice('{idx}', 'View details for #{idx}: {clean_name}')\">View #{idx} Details</button><br>"

        if idx < len(primary_results):
            reply += "<hr style='border: 0; border-top: 1px solid rgba(255,255,255,0.1); margin: 12px 0;'>"

    return reply

def format_single_place_detail(item):
    place = item["place"] if isinstance(item, dict) and "place" in item else item
    score = item.get("score") if isinstance(item, dict) else None

    name = str(get_place_attr(place, ["Business name", "business_name", "name"]))
    cat = str(get_place_attr(place, ["Category", "category"]))
    city = str(get_place_attr(place, ["Municipality or city", "Municipality/City", "municipality_city", "city", "municipality", "Municipality"]))
    hours = format_hours(get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"]))
    price = str(get_place_attr(place, ["Price range", "price_range", "Price Range"]))
    features_list = get_place_attr(place, ["Features", "features"], default=[])

    features = ", ".join(str(f) for f in features_list) if isinstance(features_list, list) else str(features_list)
    description = str(get_place_attr(place, ["Short description", "short_description", "Description", "description"], default="No description available."))
    maps_url = get_place_attr(place, ["Google Maps", "google_maps", "maps_link"], default=None)

    if not maps_url or maps_url == "N/A":
        search_query = f"{name} {city}".replace(" ", "+")
        maps_url = f"https://www.google.com/maps/search/?api=1&query={search_query}"

    reply = f"Here are the full details for <b>{name}</b>:<br><br>"
    reply += f"🏢 <b>Category</b>: {cat}<br>"
    reply += f"📍 <b>Location</b>: {city}<br>"
    reply += f"⏰ <b>Hours</b>: {hours}<br>"
    reply += f"💰 <b>Price Range</b>: {price}<br>"

    if features and features != "N/A":
        reply += f"✨ <b>Features</b>: {features}<br>"

    if score is not None:
        reply += f"<br>📊 <b>Match Score</b>: {score}/100<br>"

    reply += f"<br>🗺️ <b>Google Maps</b>: <a href='{maps_url}' target='_blank' style='color: #38bdf8; text-decoration: underline;'>Open in Google Maps ↗</a><br>"
    reply += f"<br>📝 <b>Description</b>:<br>{description}"

    return reply

def get_user_session():
    if "user_data" not in session:
        session["user_data"] = {
            "location": "Laoag",
            "state": STATE_IDLE,
            "last_places": [],
            "last_category": None,
            "last_constraints": {},
            "fsm_context": "IDLE"
        }
    return session["user_data"]

@app.route("/")
def home():
    session["user_data"] = {
        "location": "Laoag",
        "state": STATE_IDLE,
        "last_places": [],
        "last_category": None,
        "last_constraints": {},
        "fsm_context": "IDLE"
    }
    return render_template("index.html")

@app.route("/get_response", methods=["POST"])
def get_response():
    data = request.get_json() or {}
    msg = str(data.get("message", "")).strip()
    msg_lower = normalize_text(msg)
    u_session = get_user_session()

    if is_non_search_input(msg_lower):
        current_loc = u_session.get("location", "Laoag").title()
        return jsonify({
            "reply": f"Hello! You are currently searching in <b>{current_loc}</b>! How can I help you explore Ilocos Norte right now?"
        })

    unsupported_intent = detect_unsupported_intent(msg_lower)
    if unsupported_intent:
        return jsonify({
            "reply": "I apologize, but I am only a local place finder. I cannot assist with reservations, live waiting times, or real-time operational updates like power outages. I can only help you search for and discover places in Ilocos Norte."
        })

    if any(w in msg_lower for w in ["weather", "forecast", "temperature", "climate", "umulan", "init"]):
        locs = detect_location_entities(msg_lower)
        target_loc = locs[0] if locs else u_session.get("location", "laoag").lower()
        
        coords = WEATHER_COORDS.get(target_loc)
        if not coords:
            coords = WEATHER_COORDS["laoag"]
            
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current_weather=true"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                api_data = json.loads(response.read().decode())
                
            if api_data and "current_weather" in api_data:
                temp = round(api_data["current_weather"]["temperature"])
                wind = api_data["current_weather"]["windspeed"]
                code = api_data["current_weather"]["weathercode"]
                condition = WEATHER_CODES_MAP.get(code, "🌤️ Fair")
                
                reply = f"📍 <b>Current Weather in {coords['name']}</b><br><br>"
                reply += f"🌡️ <b>Temperature</b>: {temp}°C<br>"
                reply += f"☁️ <b>Condition</b>: {condition}<br>"
                reply += f"💨 <b>Wind Speed</b>: {wind} km/h<br><br>"
                reply += f"<i>(You can also check other areas using the 🌤️ Weather dropdown at the top right!)</i>"
                return jsonify({"reply": reply})
        except Exception as e:
            print(f"Weather API Error: {e}")
            return jsonify({
                "reply": "I couldn't fetch the weather right now. Please check your internet connection or try clicking the <b>🌤️ Weather</b> dropdown button."
            })

    if msg_lower in THINKING_PHRASES:
        return jsonify({"reply": "No rush at all! Take your time. Just let me know whenever you're ready to search."})

    if msg_lower in READY_PHRASES:
        return jsonify({"reply": "Awesome! What kind of place or category would you like to search for?"})

    if msg_lower in GREETINGS:
        current_loc = u_session.get("location", "Laoag").title()
        return jsonify({"reply": f"Hello! I am currently set to search in <b>{current_loc}</b>. How can I help you explore Ilocos Norte right now?"})

    if any(phrase in msg_lower for phrase in THANKS_PHRASES):
        return jsonify({"reply": "You're very welcome! 😊 Is there anything else I can help you find in Ilocos Norte?"})

    unsupported_town = detect_unsupported_location(msg_lower)
    if unsupported_town:
        supported_str = ", ".join([m.title() for m in MUNICIPALITIES])
        return jsonify({
            "reply": f"Sorry! I don't cover <b>{unsupported_town}</b> yet. I currently cover places in <b>{supported_str}</b>."
        })

    if u_session["last_places"] and msg_lower in ["1", "2", "3", "4", "5", "option 1", "option 2", "option 3", "option 4", "option 5"]:
        idx_map = {"1": 0, "option 1": 0, "2": 1, "option 2": 1, "3": 2, "option 3": 2, "4": 3, "option 4": 3, "5": 4, "option 5": 4}
        selected_idx = idx_map.get(msg_lower)
        if selected_idx is not None and selected_idx < len(u_session["last_places"]):
            chosen_item = u_session["last_places"][selected_idx]
            return jsonify({"reply": format_single_place_detail(chosen_item)})

    constraints = extract_constraints_nlp(msg)
    
    global_matched_place = find_place_globally(msg, ALL_PLACES)
    is_nearby_query = any(w in msg_lower for w in ["nearest", "near", "close", "malapit", "around", "nearby"])
    
    # Don't hijack if the user is looking for a category near this place
    if global_matched_place and not constraints.get("category") and not is_nearby_query and any(k in msg_lower for k in ["where", "how to get", "eat at", "go to", "view", "find", "buy"]):
        p_name = str(get_place_attr(global_matched_place, ["Business name", "business_name", "name"]))
        p_city = str(get_place_attr(global_matched_place, ["Municipality or city", "Municipality/City", "municipality_city", "city", "municipality", "Municipality"]))
        
        u_session["location"] = p_city
        u_session["last_places"] = [{"place": global_matched_place, "score": 100.0}]
        session.modified = True
        
        reply = f"<b>{p_name}</b> is located in <b>{p_city}</b>.<br><br>" + format_single_place_detail(global_matched_place)
        return jsonify({"reply": reply})
    
    has_meaningful_intent = (
        constraints.get("category") or 
        constraints.get("dish") or 
        constraints.get("required_features") or 
        constraints.get("locations") or
        constraints.get("max_budget") is not None
    )
    
    if not has_meaningful_intent:
        if any(w in msg_lower for w in ["hi", "hello", "hey", "sup", "im ", "i'm ", "name is", "my name"]):
            return jsonify({
                "reply": "Hello! I am Roamie, your Ilocos Norte place finder. How can I help you today? You can search for a category (e.g., 'cafe'), a municipality (e.g., 'Laoag'), or a budget."
            })
            
        return jsonify({
            "reply": f"I couldn't find a specific place to search for in your message. 😅 I can help you find places, restaurants, cafes, and more in Ilocos Norte. Try including a category (e.g., 'cafe') or a location (e.g., 'Laoag')."
        })

    has_explicit_location = bool(constraints.get("locations"))

    last_constraints = u_session.get("last_constraints", {})
    
    if not constraints.get("category") and not constraints.get("dish") and not constraints.get("required_features") and last_constraints.get("category"):
        clean_query = normalize_text(msg)
        for loc in constraints.get("locations", []):
            clean_query = clean_query.replace(loc, "")
        
        clean_query = re.sub(r"\b(in|near|at|around|to|the|a|an|what|about|how|is|are|there|any|for)\b", "", clean_query).strip()
        
        if len(clean_query) == 0:
            constraints["category"] = last_constraints.get("category")

    if constraints.get("locations"):
        u_session["location"] = constraints["locations"][0]
    elif u_session.get("location"):
        constraints["locations"] = [u_session["location"]]

    current_loc = u_session.get("location", "Laoag")
    ranked_results = score_and_rank_places_nlp(constraints, current_loc)

    u_session["last_constraints"] = constraints
    if ranked_results:
        qualifying = [item for item in ranked_results if item["score"] >= 50.0]
        if qualifying:
            u_session["last_places"] = qualifying[:5]
            session.modified = True

    return jsonify({
        "reply": format_place_output(
            ranked_results, 
            constraints=constraints, 
            current_location=current_loc,
            has_explicit_location=has_explicit_location
        )
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)