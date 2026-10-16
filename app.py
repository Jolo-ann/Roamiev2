import json
import re
from difflib import SequenceMatcher
from flask import Flask, request, jsonify, render_template, session

from config import (
    STATE_AWAITING_NAME, STATE_IDLE, MUNICIPALITIES, 
    MUNICIPALITY_ALIASES, CATEGORY_SYNONYMS, FEATURE_ALIASES,
    THINKING_PHRASES, READY_PHRASES, GREETINGS
)
from nlp_engine import (
    normalize_text, normalized_tokens, extract_constraints_nlp,
    detect_location_entities, detect_unsupported_location,
    detect_category_entity, detect_feature_entities,
    parse_hours_range, lexical_overlap_score, phrase_present
)

# Flask server setup
app = Flask(__name__)
app.secret_key = "roamie_production_key_fixed"

# 3. DATASET LOADING & CORPUS CONSTRUCTION
def load_dataset():
    """Loads the database from JSON."""
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

# 9. ATTRIBUTE MATCHING & SCORING RANKER
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

def score_and_rank_places_nlp(constraints, session_location=None, ignore_features=False):
    if not ALL_PLACES:
        return []

    requested_category = constraints.get("category")
    requested_locations = constraints.get("locations") or ([session_location] if session_location else [])
    requested_features = constraints.get("required_features", []) if not ignore_features else []
    requested_dish = constraints.get("dish")
    target_close_min = constraints.get("target_closing_time")
    requested_budget = constraints.get("max_budget")
    query_text = constraints.get("raw_query", "")

    scored_places = []

    for place in ALL_PLACES:
        if requested_locations and not location_matches(place, requested_locations):
            continue

        if requested_category and not category_matches(place, requested_category):
            continue

        place_corpus = build_place_corpus(place)
        score = 0.0

        lexical_score = lexical_overlap_score(query_text, place_corpus, PLACE_CORPUS)
        score += lexical_score * 35.0

        if requested_category:
            score += 25.0
        else:
            score += min(10.0, lexical_score * 10.0)

        if requested_locations:
            score += 15.0

        if requested_features:
            matched_count = sum(1 for feature in requested_features if place_has_feature(place, feature))
            if matched_count == 0 and not ignore_features:
                continue
            feature_ratio = matched_count / len(requested_features)
            score += feature_ratio * 20.0

        if requested_dish:
            p_keywords = str(get_place_attr(place, ["Keywords and synonyms", "keywords_synonyms", "keywords"], "")).lower()
            p_name = str(get_place_attr(place, ["Business name", "business_name", "name"], "")).lower()
            p_desc = str(get_place_attr(place, ["Short description", "short_description", "description"], "")).lower()
            p_cat = str(get_place_attr(place, ["Category", "category"], "")).lower()

            combined_place_text = f"{p_name} {p_keywords} {p_desc}"

            if phrase_present(combined_place_text, requested_dish):
                score += 50.0
            else:
                if any(chain in p_name or chain in p_cat for chain in ["mcdonald", "chowking", "jollibee", "mang inasal", "fastfood"]):
                    score -= 40.0
                else:
                    score -= 15.0

        if requested_budget is not None:
            place_price = price_number_from_place(place)
            if place_price is None:
                score += 2.0
            elif place_price <= requested_budget:
                score += 20.0
            elif place_price <= requested_budget * 1.15:
                score += 5.0
            else:
                score -= 20.0

        if target_close_min is not None:
            hours = str(get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"]))
            _, close_min = parse_hours_range(hours)
            if close_min is not None:
                if close_min >= target_close_min:
                    score += 15.0
                else:
                    score -= 20.0

        business_name = str(get_place_attr(place, ["Business name", "business_name", "name"], ""))
        if business_name:
            name_similarity = SequenceMatcher(None, normalize_text(query_text), normalize_text(business_name)).ratio()
            score += name_similarity * 10.0

        scored_places.append({
            "place": place,
            "score": round(score, 2),
        })

    scored_places.sort(key=lambda item: item["score"], reverse=True)
    return scored_places

def get_partial_matches(constraints, session_location):
    if constraints.get("required_features"):
        partial_results = score_and_rank_places_nlp(constraints, session_location, ignore_features=True)
        if partial_results:
            loc_str = constraints.get('location', 'that area').title()
            return partial_results, f"I couldn't find a place matching all features in {loc_str}, but here are the top matching venues nearby:"
    return [], None

# 10. RESPONSE GENERATORS & FORMATTERS
def format_place_output(ranked_results, user_name, has_category=True, custom_prefix=None, constraints=None):
    top_results = ranked_results[:5]

    if not top_results:
        return f"I couldn't find any places matching all your criteria, {user_name}."

    if custom_prefix:
        reply = f"{custom_prefix}<br><br>"
    elif has_category:
        reply = f"Here are the top options matching your query, {user_name}:<br><br>"
    else:
        reply = f"Here are my suggested places for you, {user_name}:<br><br>"

    constraints = constraints or {}
    req_cat = constraints.get("category")
    req_loc = constraints.get("location") or (constraints.get("locations")[0] if constraints.get("locations") else None)
    req_features = constraints.get("required_features", [])
    target_close_min = constraints.get("target_closing_time")
    req_budget = constraints.get("max_budget")

    for idx, item in enumerate(top_results, 1):
        place = item["place"]
        score = item["score"]
        name = get_place_attr(place, ["Business name", "business_name", "name"])
        cat = get_place_attr(place, ["Category", "category"])
        city = get_place_attr(place, ["Municipality or city", "municipality_city", "city"])
        hours = get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"])
        price = get_place_attr(place, ["Price range", "price_range", "Price Range"])

        reply += f"<b>{idx}. {name}</b> ({cat})<br>"
        reply += f"📍 <b>Location</b>: {city}<br>"
        reply += f"⏰ <b>Hours</b>: {hours}<br>"
        reply += f"💰 <b>Price</b>: {price}<br>"

        # Explainability Insights Block
        reply += f"🔍 <b>Match Insights</b> (Score: {score}):<br>"
        reply += f"• 🎯 <b>Relevance Match</b>: High textual relevance to your search.<br>"
        
        if req_cat:
            reply += f"• ✅ <b>Correct Category</b>: Matches requested category '<i>{req_cat}</i>'.<br>"
        
        if req_loc:
            reply += f"• ✅ <b>Correct Location</b>: Located in matched area '<i>{city}</i>'.<br>"

        if req_features:
            matched_feats = [f for f in req_features if place_has_feature(place, f)]
            if matched_feats:
                reply += f"• ✅ <b>Requested Feature Found</b>: Has {', '.join(matched_feats)}.<br>"
            else:
                reply += f"• ⚠️ <b>Feature Notice</b>: Alternative venue suggested.<br>"

        if target_close_min is not None:
            _, close_min = parse_hours_range(hours)
            if close_min is not None and close_min >= target_close_min:
                reply += f"• ✅ <b>Closing Time Meets Request</b>: Open until late as requested.<br>"

        if req_budget is not None:
            place_price = price_number_from_place(place)
            if place_price is not None and place_price <= req_budget:
                reply += f"• ✅ <b>Within Budget</b>: Estimated price fits your ₱{req_budget} budget.<br>"

        if idx < len(top_results):
            reply += "<hr style='border: 0; border-top: 1px solid #444; margin: 10px 0;'>"

    if len(top_results) == 1:
        reply += "<br><b>Which one suits you?</b> (Reply with 1 to view description and full details!)"
    else:
        reply += f"<br><b>Which one suits you?</b> (Reply with 1 to {len(top_results)} to view description and full details!)"

    return reply

def format_single_place_detail(item, user_name, constraints=None):
    if isinstance(item, dict) and "place" in item:
        place = item["place"]
        score = item.get("score", None)
    else:
        place = item
        score = None

    name = get_place_attr(place, ["Business name", "business_name", "name"])
    cat = get_place_attr(place, ["Category", "category"])
    city = get_place_attr(place, ["Municipality or city", "municipality_city", "city"])
    hours = get_place_attr(place, ["Opening and closing hours", "opening_closing_hours", "Operating Hours", "hours"])
    price = get_place_attr(place, ["Price range", "price_range", "Price Range"])
    features_list = get_place_attr(place, ["Features", "features"], default=[])

    features = ", ".join(str(feature) for feature in features_list) if isinstance(features_list, list) else str(features_list)
    description = get_place_attr(place, ["Short description", "short_description", "Description", "description"], default="No description available.")
    maps_url = get_place_attr(place, ["Google Maps", "google_maps", "maps_link", "GoogleMaps", "maps"], default=None)

    if not maps_url or maps_url == "N/A":
        search_query = f"{name} {city}".replace(" ", "+")
        maps_url = f"https://www.google.com/maps/search/?api=1&query={search_query}"

    reply = f"Here are the full details for <b>{name}</b>, {user_name}:<br><br>"
    reply += f"🏢 <b>Category</b>: {cat}<br>"
    reply += f"📍 <b>Location</b>: {city}<br>"
    reply += f"⏰ <b>Hours</b>: {hours}<br>"
    reply += f"💰 <b>Price Range</b>: {price}<br>"

    if features and features != "N/A":
        reply += f"✨ <b>Features</b>: {features}<br>"

    # Explainability Breakdown for Single Venue View
    if score is not None:
        reply += f"<br>📊 <b>Match Breakdown</b> (Score: {score}):<br>"
        constraints = constraints or {}
        if constraints.get("category"):
            reply += f"• 🎯 <b>Category Match</b>: Matches requested category '<i>{constraints['category']}</i>'<br>"
        if constraints.get("locations"):
            reply += f"• 📍 <b>Location Match</b>: Located in requested area '<i>{city}</i>'<br>"
        if constraints.get("required_features"):
            matched_feats = [f for f in constraints["required_features"] if place_has_feature(place, f)]
            if matched_feats:
                reply += f"• ✨ <b>Features Matched</b>: {', '.join(matched_feats)}<br>"
        if constraints.get("max_budget") is not None:
            reply += f"• 💰 <b>Budget Match</b>: Within specified limit (₱{constraints['max_budget']})<br>"
    else:
        reply += "• 🎯 <b>Relevance Match</b>: Identified as a top match based on search criteria.<br>"

    reply += f"<br>🗺️ <b>Google Maps</b>: <a href='{maps_url}' target='_blank' style='color: #4da6ff; text-decoration: underline;'>Open in Google Maps ↗</a><br>"
    reply += f"<br>📝 <b>Description</b>:<br>{description}"

    return reply

# 11. CONVERSATIONAL FOLLOWUP & SESSION CONTEXT HANDLERS
def find_place_by_name(query_text):
    query_clean = normalize_text(query_text)
    category = detect_category_entity(query_clean)

    search_triggers = ["want", "looking for", "find", "show", "where", "is there", "search", "give me", "recommend"]
    if any(trigger in query_clean for trigger in search_triggers) or category:
        return None

    for place in ALL_PLACES:
        p_name = str(get_place_attr(place, ["Business name", "business_name", "name"], ""))
        p_name_clean = normalize_text(p_name)
        if not p_name_clean:
            continue
            
        if phrase_present(query_clean, p_name_clean):
            return place

    return None

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

def handle_followup_feature_question(msg_lower, last_places, user_name):
    if not is_explicit_followup_question(msg_lower):
        return None

    detected_features = detect_feature_entities(msg_lower)
    if not detected_features:
        return None

    detected_feature = detected_features[0]
    reply = f"Here is the info regarding <b>{detected_feature.title()}</b> for the places listed above, {user_name}:<br><br>"

    for idx, item in enumerate(last_places, 1):
        place = item["place"] if isinstance(item, dict) and "place" in item else item
        name = get_place_attr(place, ["Business name", "business_name", "name"])
        if place_has_feature(place, detected_feature):
            reply += f"✅ <b>{idx}. {name}</b>: Yes, feature/info found matching <i>{detected_feature}</i>.<br>"
        else:
            reply += f"❌ <b>{idx}. {name}</b>: No explicit mention of <i>{detected_feature}</i> in details.<br>"

    reply += f"<br>Reply with 1 to {len(last_places)} to view full details for any option!"
    return reply

def get_user_session():
    if "user_data" not in session:
        session["user_data"] = {
            "name": None,
            "location": None,
            "state": STATE_AWAITING_NAME,
            "last_places": [],
            "last_category": None,
            "last_constraints": {},
            "fsm_context": "IDLE"
        }
    return session["user_data"]

# 12. ROUTING CONTROLLER & DIALOGUE STATE MACHINE (FSM)
@app.route("/")
def home():
    session["user_data"] = {
        "name": None,
        "location": None,
        "state": STATE_AWAITING_NAME,
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

    if u_session["state"] == STATE_AWAITING_NAME or u_session["name"] is None:
        clean_name = re.sub(r"^(hello|hi|hey)?\s*,?\s*(my name is|call me|im|i'm|i am)\s*", "", msg, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r"^(hello|hi|hey)\s+", "", clean_name, flags=re.IGNORECASE).strip()

        u_session["name"] = clean_name.title() if clean_name else "Friend"
        u_session["state"] = STATE_IDLE
        u_session["fsm_context"] = "IDLE"
        session.modified = True

        return jsonify({
            "reply": f"Nice to meet you, {u_session['name']}! What kind of place are you looking for in Ilocos Norte today?"
        })

    display_name = u_session["name"]

    unsupported_town = detect_unsupported_location(msg_lower)
    if unsupported_town:
        supported_str = ", ".join([m.title() for m in MUNICIPALITIES])
        return jsonify({
            "reply": f"Sorry, {display_name}! I don't cover <b>{unsupported_town}</b> yet. I currently cover places in <b>{supported_str}</b>."
        })

    target_place = find_place_by_name(msg)
    detected_features = detect_feature_entities(msg_lower)
    detected_feature = detected_features[0] if detected_features else None

    if target_place and detected_feature and not any(k in msg_lower for k in ["want", "looking for", "find", "show me", "where"]):
        p_name = get_place_attr(target_place, ["Business name", "business_name", "name"])
        if place_has_feature(target_place, detected_feature):
            reply = f"✅ Yes, <b>{p_name}</b> has <b>{detected_feature.title()}</b>, {display_name}!"
        else:
            reply = f"❌ No explicit mention of <b>{detected_feature.title()}</b> for <b>{p_name}</b> in our records, {display_name}."
        return jsonify({"reply": reply})

    if u_session["last_places"] and (msg_lower in ["1", "2", "3", "4", "5", "option 1", "option 2", "option 3", "option 4", "option 5", "first", "second", "third", "fourth", "fifth"]):
        idx_map = {
            "1": 0, "option 1": 0, "first": 0,
            "2": 1, "option 2": 1, "second": 1,
            "3": 2, "option 3": 2, "third": 2,
            "4": 3, "option 4": 3, "fourth": 3,
            "5": 4, "option 5": 4, "fifth": 4,
        }
        selected_idx = idx_map.get(msg_lower)

        if selected_idx is not None and selected_idx < len(u_session["last_places"]):
            chosen_item = u_session["last_places"][selected_idx]
            u_session["fsm_context"] = "VIEWING_DETAIL"
            session.modified = True
            last_constraints = u_session.get("last_constraints", {})
            return jsonify({"reply": format_single_place_detail(chosen_item, display_name, constraints=last_constraints)})

    if u_session["last_places"]:
        if is_explicit_followup_question(msg_lower) or (detected_feature and len(normalized_tokens(msg_lower)) <= 4):
            followup_reply = handle_followup_feature_question(msg_lower, u_session["last_places"], display_name)
            if followup_reply:
                u_session["fsm_context"] = "FOLLOWUP"
                session.modified = True
                return jsonify({"reply": followup_reply})

    if msg_lower in ["okay", "ok"]:
        return jsonify({"reply": f"Got it, {display_name}! What place or category would you like to check out next?"})

    if any(phrase in msg_lower for phrase in THINKING_PHRASES):
        u_session["fsm_context"] = "THINKING"
        session.modified = True
        return jsonify({"reply": f"No rush at all, {display_name}! Take your time. Just let me know whenever you're ready to search."})

    if any(phrase in msg_lower for phrase in READY_PHRASES):
        u_session["fsm_context"] = "READY"
        session.modified = True
        return jsonify({"reply": f"Awesome! What kind of place or category would you like to search for, {display_name}?"})

    if msg_lower in GREETINGS:
        return jsonify({"reply": f"Hello {display_name}! How can I help you explore Ilocos Norte right now?"})

    constraints = extract_constraints_nlp(msg)
    has_explicit_category = bool(constraints["category"])

    if constraints["category"]:
        u_session["last_category"] = constraints["category"]
        session.modified = True
    elif constraints["locations"] and not constraints["category"] and u_session.get("last_category"):
        constraints["category"] = u_session["last_category"]
        has_explicit_category = True

    if constraints["locations"]:
        u_session["location"] = constraints["locations"][0]
        session.modified = True

    ranked_results = score_and_rank_places_nlp(constraints, u_session.get("location"))

    custom_prefix = None
    if not ranked_results:
        ranked_results, custom_prefix = get_partial_matches(constraints, u_session.get("location"))

    if ranked_results:
        u_session["last_places"] = ranked_results[:5]
        u_session["last_constraints"] = constraints
        u_session["fsm_context"] = "SEARCH_RESULTS"
        session.modified = True
        return jsonify({"reply": format_place_output(ranked_results, display_name, has_category=has_explicit_category, custom_prefix=custom_prefix, constraints=constraints)})

    u_session["fsm_context"] = "NO_RESULTS"
    session.modified = True
    return jsonify({"reply": f"I couldn't find any places matching your request, {display_name}."})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)