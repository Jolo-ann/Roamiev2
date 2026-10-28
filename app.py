# app.py
import json
import re
from flask import Flask, request, jsonify, render_template, session

from config import (
    STATE_IDLE, MUNICIPALITIES, 
    MUNICIPALITY_ALIASES, CATEGORY_SYNONYMS, FEATURE_ALIASES,
    THINKING_PHRASES, READY_PHRASES, GREETINGS
)
from nlp_engine import (
    normalize_text, normalized_tokens, extract_constraints_nlp,
    detect_location_entities, detect_unsupported_location,
    detect_category_entity, detect_feature_entities,
    parse_hours_range, lexical_overlap_score, phrase_present,
    extract_place_name_query
)

app = Flask(__name__)
app.secret_key = "roamie_production_key_fixed"

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

def build_place_corpus(place):
    name = str(place.get("Business name") or place.get("business_name") or place.get("name") or "")
    cat = str(place.get("Category") or place.get("category") or "")
    city = str(place.get("Municipality or city") or place.get("municipality_city") or place.get("city") or "")
    desc = str(place.get("Short description") or place.get("short_description") or place.get("Description") or "")
    feats = place.get("Features") or place.get("features") or []
    feats_str = " ".join(str(f) for f in feats) if isinstance(feats, list) else str(feats)
    keywords = str(place.get("Keywords and synonyms") or place.get("keywords_synonyms") or place.get("keywords") or "")

    return f"{name}. Category: {cat}. Location: {city}. Details: {desc} Features: {feats_str} Keywords: {keywords}"

PLACE_CORPUS = [build_place_corpus(p) for p in ALL_PLACES]

def get_place_attr(place, keys, default="N/A"):
    for key in keys:
        if key in place and place[key] not in [None, "", "N/A"]:
            return place[key]
    return default

def category_matches(place, requested_category):
    if not requested_category:
        return True
    category_text = normalize_text(get_place_attr(place, ["Category", "category"], ""))
    aliases = CATEGORY_SYNONYMS.get(requested_category, [requested_category])
    return any(phrase_present(category_text, alias) for alias in aliases)

def location_matches(place, requested_locations):
    if not requested_locations:
        return True
    if isinstance(requested_locations, str):
        requested_locations = [requested_locations]
        
    city_text = normalize_text(get_place_attr(place, ["Municipality or city", "municipality_city", "city", "municipality"], ""))
    
    for req_loc in requested_locations:
        aliases = MUNICIPALITY_ALIASES.get(req_loc, [req_loc])
        if any(phrase_present(city_text, alias) for alias in aliases):
            return True
    return False

def place_has_feature(place, feature):
    feats_raw = get_place_attr(place, ["Features", "features"], [])
    feature_text = " ".join(str(item) for item in feats_raw) if isinstance(feats_raw, list) else str(feats_raw)
    description = str(get_place_attr(place, ["Short description", "short_description", "Description", "description"], ""))
    keywords = str(get_place_attr(place, ["Keywords and synonyms", "keywords_synonyms", "keywords"], ""))

    combined = normalize_text(f"{feature_text} {description} {keywords}")
    aliases = FEATURE_ALIASES.get(feature, [feature])
    return any(phrase_present(combined, alias) for alias in aliases)

def place_has_dish(place, dish):
    if not dish:
        return False
    name = str(get_place_attr(place, ["Business name", "business_name", "name"], ""))
    desc = str(get_place_attr(place, ["Short description", "short_description", "Description", "description"], ""))
    keywords = str(get_place_attr(place, ["Keywords and synonyms", "keywords_synonyms", "keywords"], ""))
    
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

    return max(values) if values else None

def find_place_globally(query_text):
    extracted_target = extract_place_name_query(query_text)
    search_target = extracted_target or normalize_text(query_text)

    if not search_target or len(search_target) < 3:
        return None

    for place in ALL_PLACES:
        p_name = str(get_place_attr(place, ["Business name", "business_name", "name"], ""))
        p_name_clean = normalize_text(p_name)
        if not p_name_clean:
            continue
            
        if phrase_present(search_target, p_name_clean) or phrase_present(p_name_clean, search_target):
            return place

    return None

# app.py

from nlp_engine import (
    normalize_text, normalized_tokens, extract_constraints_nlp,
    detect_location_entities, detect_unsupported_location,
    detect_category_entity, detect_feature_entities,
    parse_hours_range, extract_closing_minutes, lexical_overlap_score, phrase_present,
    extract_place_name_query
)

def score_and_rank_places_nlp(constraints, session_location=None, ignore_features=False):
    if not ALL_PLACES:
        return []

    requested_category = constraints.get("category")
    requested_exclusions = constraints.get("exclusions", [])
    requested_locations = constraints.get("locations") or ([session_location] if session_location else [])
    requested_features = constraints.get("required_features", []) if not ignore_features else []
    requested_dish = constraints.get("dish")
    target_close_min = constraints.get("target_closing_time")
    target_day = constraints.get("target_day")
    requested_budget = constraints.get("max_budget")
    query_text = constraints.get("raw_query", "")

    scored_places = []
    
    for place in ALL_PLACES:
        p_cat = normalize_text(get_place_attr(place, ["Category", "category"], ""))
        p_name = normalize_text(get_place_attr(place, ["Business name", "business_name"], ""))

        # EXCLUSION CHECK
        if requested_exclusions and requested_category:
            if any(excluded in p_cat for excluded in requested_exclusions) and not category_matches(place, requested_category):
                continue

        if requested_locations and not location_matches(place, requested_locations):
            continue

        place_corpus = build_place_corpus(place)
        score = 0.0

        lexical_score = lexical_overlap_score(query_text, place_corpus, PLACE_CORPUS)

        # 1. Category & Dish Match
        if requested_dish:
            if place_has_dish(place, requested_dish):
                score += 35.0
                score += min(15.0, lexical_score * 15.0)
        elif requested_category:
            if category_matches(place, requested_category):
                score += 35.0
                score += min(15.0, lexical_score * 15.0)
            else:
                continue
        else:
            score += min(30.0, lexical_score * 30.0)

        # 2. Location Match Score
        if requested_locations:
            score += 20.0

        # 3. UNIVERSAL CLOSING TIME SCORING
        if target_close_min is not None:
            raw_hours = get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"])
            place_close_min = extract_closing_minutes(raw_hours, target_day=target_day)

            if place_close_min is not None:
                hours_diff = abs(target_close_min - place_close_min) / 60.0
                
                if hours_diff == 0:
                    score += 50.0  # Exact 11 PM match gets massive boost
                else:
                    score += max(0.0, 50.0 - (hours_diff * 15.0))

        # 4. Features & Budget Matching
        pref_points = 0.0
        if requested_features:
            matched_count = sum(1 for feature in requested_features if place_has_feature(place, feature))
            if matched_count == 0 and not ignore_features:
                continue
            elif matched_count > 0:
                pref_points += (matched_count / len(requested_features)) * 15.0

        if requested_budget is not None:
            place_price = price_number_from_place(place)
            if place_price is not None and place_price <= requested_budget:
                pref_points += 5.0

        score += min(15.0, pref_points)

        final_score = max(0.0, min(100.0, round(score, 2)))

        scored_places.append({
            "place": place,
            "score": final_score,
        })

    scored_places.sort(key=lambda item: item["score"], reverse=True)
    return scored_places

def format_hours(value):
    """Render opening-hours strings and structured day/department schedules safely."""
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
                    if opening and closing:
                        desc = f"{opening}–{closing}"
                    elif opening or closing:
                        desc = str(opening or closing)
                    else:
                        desc = "Not specified"
                else:
                    desc = str(schedule)

                schedule_groups.setdefault(desc, []).append(day.title()[:3])

            if not schedule_groups:
                return "N/A"

            # Combine identical schedule days into clean readable blocks
            formatted_parts = []
            for time_slot, days in schedule_groups.items():
                if len(days) > 1:
                    day_str = f"{days[0]}–{days[-1]}"
                else:
                    day_str = days[0]
                formatted_parts.append(f"{day_str}: {time_slot}")

            return "<br>&nbsp;&nbsp;&nbsp;&nbsp;• " + "<br>&nbsp;&nbsp;&nbsp;&nbsp;• ".join(formatted_parts)

        return "; ".join(f"{label}: {format_hours(schedule)}" for label, schedule in value.items())
    return str(value)


def format_place_output(ranked_results, custom_prefix=None, constraints=None, current_location="Laoag"):
    primary_results = [item for item in ranked_results if item["score"] >= 50.0][:5]

    if not primary_results:
        req_feat = constraints.get("required_features")
        query_item = (f"{constraints.get('category')} with {req_feat[0]}" if req_feat and constraints.get("category")
                      else constraints.get("dish") or constraints.get("category") or "matching places")
        loc_display = current_location.title() if current_location else "this area"
        
        reply = f"I couldn't find any places offering <b>'{query_item}'</b> in <b>{loc_display}</b>.<br><br>"
        reply += f"Are you still searching in <b>{loc_display}</b>, or would you like to check a different location?"
        return reply

    if custom_prefix:
        reply = f"{custom_prefix}<br><br>"
    else:
        reply = "Here are the top matching places for your search:<br><br>"

    constraints = constraints or {}
    req_cat = constraints.get("category")
    req_dish = constraints.get("dish")
    req_loc = constraints.get("location") or (constraints.get("locations")[0] if constraints.get("locations") else None)
    req_features = constraints.get("required_features", [])

    for idx, item in enumerate(primary_results, 1):
        place = item["place"]
        score = item["score"]
        name = get_place_attr(place, ["Business name", "business_name", "name"])
        cat = get_place_attr(place, ["Category", "category"])
        city = get_place_attr(place, ["Municipality or city", "municipality_city", "city"])
        hours = format_hours(get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"]))
        price = get_place_attr(place, ["Price range", "price_range", "Price Range"])

        reply += f"<b>{idx}. {name}</b> ({cat})<br>"
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

def format_single_place_detail(item, constraints=None):
    if isinstance(item, dict) and "place" in item:
        place = item["place"]
        score = item.get("score", None)
    else:
        place = item
        score = None

    name = get_place_attr(place, ["Business name", "business_name", "name"])
    cat = get_place_attr(place, ["Category", "category"])
    city = get_place_attr(place, ["Municipality or city", "municipality_city", "city"])
    hours = format_hours(get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"]))
    price = get_place_attr(place, ["Price range", "price_range", "Price Range"])
    features_list = get_place_attr(place, ["Features", "features"], default=[])

    features = ", ".join(str(feature) for feature in features_list) if isinstance(features_list, list) else str(features_list)
    description = get_place_attr(place, ["Short description", "short_description", "Description", "description"], default="No description available.")
    maps_url = get_place_attr(place, ["Google Maps", "google_maps", "maps_link", "GoogleMaps", "maps"], default=None)

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

def is_explicit_followup_question(msg_lower):
    if detect_location_entities(msg_lower) or detect_unsupported_location(msg_lower) or detect_category_entity(msg_lower):
        return False

    followup_patterns = [
        r"\bdo they\b", r"\bis there\b", r"\bdoes it\b", r"\bare there\b",
        r"\bhas parking\b", r"\bhave parking\b", r"\bhas wifi\b",
        r"\bhave wifi\b", r"\bhas ktv\b", r"\bhave ktv\b", r"\bwhich one\b",
        r"\bhow about\b", r"\bwhat about\b", r"\band\b", r"\babout\b"
    ]
    return any(re.search(pattern, msg_lower) for pattern in followup_patterns)

def handle_followup_feature_question(msg_lower, last_places):
    if not is_explicit_followup_question(msg_lower):
        return None

    detected_features = detect_feature_entities(msg_lower)
    if not detected_features:
        return None

    detected_feature = detected_features[0]
    reply = f"Here is the info regarding <b>{detected_feature.title()}</b> for the places listed above:<br><br>"

    for idx, item in enumerate(last_places, 1):
        place = item["place"] if isinstance(item, dict) and "place" in item else item
        name = get_place_attr(place, ["Business name", "business_name", "name"])
        if place_has_feature(place, detected_feature):
            reply += f"✅ <b>{idx}. {name}</b>: Yes, feature/info found matching <i>{detected_feature}</i>.<br>"
        else:
            reply += f"❌ <b>{idx}. {name}</b>: No explicit mention of <i>{detected_feature}</i> in details.<br>"

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

    detected_category = detect_category_entity(msg_lower)

    # 1. Global Direct Place Name Lookup (Skipped if asking for a category)
    if not detected_category:
        global_matched_place = find_place_globally(msg)
        if global_matched_place and any(k in msg_lower for k in ["where", "how to get", "eat at", "go to"]):
            p_name = get_place_attr(global_matched_place, ["Business name", "business_name", "name"])
            p_city = get_place_attr(global_matched_place, ["Municipality or city", "municipality_city", "city"])
            
            u_session["location"] = p_city
            u_session["last_places"] = [{"place": global_matched_place, "score": 100.0}]
            session.modified = True
            
            reply = f"<b>{p_name}</b> is located in <b>{p_city}</b>.<br><br>"
            reply += format_single_place_detail(global_matched_place)
            return jsonify({"reply": reply})

    unsupported_town = detect_unsupported_location(msg_lower)
    if unsupported_town:
        supported_str = ", ".join([m.title() for m in MUNICIPALITIES])
        return jsonify({
            "reply": f"Sorry! I don't cover <b>{unsupported_town}</b> yet. I currently cover places in <b>{supported_str}</b>."
        })

    detected_features = detect_feature_entities(msg_lower)
    detected_feature = detected_features[0] if detected_features else None

    if u_session["last_places"] and (msg_lower in ["1", "2", "3", "4", "5", "option 1", "option 2", "option 3", "option 4", "option 5"]):
        idx_map = {"1": 0, "option 1": 0, "2": 1, "option 2": 1, "3": 2, "option 3": 2, "4": 3, "option 4": 3, "5": 4, "option 5": 4}
        selected_idx = idx_map.get(msg_lower)

        if selected_idx is not None and selected_idx < len(u_session["last_places"]):
            chosen_item = u_session["last_places"][selected_idx]
            u_session["fsm_context"] = "VIEWING_DETAIL"
            session.modified = True
            last_constraints = u_session.get("last_constraints", {})
            return jsonify({"reply": format_single_place_detail(chosen_item, constraints=last_constraints)})

    if u_session["last_places"]:
        if is_explicit_followup_question(msg_lower) or (detected_feature and len(normalized_tokens(msg_lower)) <= 4):
            followup_reply = handle_followup_feature_question(msg_lower, u_session["last_places"])
            if followup_reply:
                u_session["fsm_context"] = "FOLLOWUP"
                session.modified = True
                return jsonify({"reply": followup_reply})

    if msg_lower in ["okay", "ok"]:
        return jsonify({"reply": "Got it! What place or category would you like to check out next?"})

    if any(phrase in msg_lower for phrase in THINKING_PHRASES):
        u_session["fsm_context"] = "THINKING"
        session.modified = True
        return jsonify({"reply": "No rush at all! Take your time. Just let me know whenever you're ready to search."})

    if any(phrase in msg_lower for phrase in READY_PHRASES):
        u_session["fsm_context"] = "READY"
        session.modified = True
        return jsonify({"reply": "Awesome! What kind of place or category would you like to search for?"})

    if msg_lower in GREETINGS:
        return jsonify({"reply": "Hello! How can I help you explore Ilocos Norte right now?"})

    # 1. Parse NLP Constraints
    constraints = extract_constraints_nlp(msg)

    # 2. Category Context Resolution
    if constraints.get("category"):
        # Explicit new category detected -> Update active state
        u_session["last_category"] = constraints["category"]
    else:
        # Check if query contains explicit new search intents (e.g., "where can i buy X", "where is Y")
        new_intent_query = any(phrase in msg_lower for phrase in [
            "where", "find", "buy", "looking for", "search", "check", "get", "near"
        ])

        if new_intent_query:
            # Clear old category state to avoid sticking to old topics like 'karaoke'
            u_session["last_category"] = None
            constraints["category"] = None
        elif u_session.get("last_category"):
            # Carry over active category only for contextual follow-ups
            constraints["category"] = u_session["last_category"]

    # 3. Location Context Resolution
    if constraints.get("locations"):
        u_session["location"] = constraints["locations"][0]
    elif u_session.get("location"):
        constraints["locations"] = [u_session["location"]]

    session.modified = True

    current_loc = u_session.get("location", "Laoag")
    ranked_results = score_and_rank_places_nlp(constraints, current_loc)

    if ranked_results:
        qualifying = [item for item in ranked_results if item["score"] >= 50.0]
        if qualifying:
            u_session["last_places"] = qualifying[:5]
            u_session["last_constraints"] = constraints
            u_session["fsm_context"] = "SEARCH_RESULTS"
            session.modified = True
            
            reply = format_place_output(ranked_results, custom_prefix=None, constraints=constraints, current_location=current_loc)
            return jsonify({"reply": reply})

    u_session["fsm_context"] = "NO_RESULTS"
    session.modified = True

    location_words = "|".join([m.lower() for m in MUNICIPALITIES] + ["city", "ilocos", "norte"])
    raw_clean = re.sub(rf"\b(where|can|i|find|buy|in|at|the|a|an|near|spot|spots|{location_words})\b", "", msg_lower).strip()
    raw_clean = re.sub(r"\s+", " ", raw_clean).strip()

    query_item = constraints.get("category") or constraints.get("dish") or raw_clean or "matching places"
    loc_display = current_loc.title()
    
    return jsonify({
        "reply": f"I couldn't find any places offering <b>'{query_item}'</b> in <b>{loc_display}</b>.<br><br>Are you still searching in <b>{loc_display}</b>, or would you like to check a different location?"
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)