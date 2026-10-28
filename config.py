# config.py
# 1. APPLICATION & SYSTEM STATE INITIALIZATION
STATE_AWAITING_NAME = "AWAITING_NAME"
STATE_IDLE = "IDLE"

# 2. LOCAL ENTITIES GAZETTEER & SCOPE DEFINITIONS
MUNICIPALITIES = [
    "laoag", "batac", "san nicolas", "bacarra", "paoay",
    "badoc", "pinili", "sarrat", "vintar", "pagudpud", "marcos",
    "adams", "solsona", "nueva era", "bangui", "burgos", "banna"
]

MUNICIPALITY_ALIASES = {
    'laoag': ['laoag', 'laoag city'],
    'batac': ['batac', 'batac city'],
    'san nicolas': ['san nicolas'],
    'bacarra': ['bacarra'],
    'paoay': ['paoay'],
    'badoc': ['badoc'],
    'pinili': ['pinili'],
    'sarrat': ['sarrat'],
    'vintar': ['vintar'],
    'pagudpud': ['pagudpud'],
    'marcos': ['marcos'],
    'adams': ['adams'],
    'solsona': ['solsona'],
    'nueva era': ['nueva era'],
    'bangui': ['bangui'],
    'burgos': ['burgos'],
    'banna': ['banna'],
}

UNSUPPORTED_LOCATIONS = [
    "piddig", "pasuquin", "currimao", "dingras"
]

# config.py

CATEGORY_SYNONYMS = {
    "tourist spot": [
        "tourist spot", "tourist spots", "attraction", "attractions", "sightseeing",
        "sand dunes", "sand dune", "dunes", "beach", "park", "landmark", "monument",
        "church", "historical site", "destination", "place to visit"
    ],
    "restaurant": [
        "restaurant", "restaurants", "resto", "bistro", "eatery",
        "dining", "diner", "grill", "steak", "food", "foods",
        "wings", "pasta", "sushi", "ramen", "seafood",
        "samgyupsal", "samgyup", "bbq", "barbecue", "eat",
        "fastfood", "fast food", "food place", "empanada", "empanadaan",
        "bagnet", "poqui-poqui", "poquipoqui", "poqui poqui", "ilocano food", "local dishes"
    ],
    "cafe": [
        "cafe", "cafes", "coffee", "coffee shop", "bakeshop",
        "bakery", "espresso", "latte", "tea", "tea shop", "cozy cafe", "cozy café", "café"
    ],
    "mall": [
        "mall", "malls", "shopping mall", "shopping center", "department store", "plaza"
    ],
    "karaoke": [
        "karaoke", "ktv", "singing", "music lounge", "videoke"
    ],
    "dealership": [
        "dealership", "motorcycle", "motorcycles", "car dealership", "showroom", "auto sales", "toyota", "honda", "yamaha"
    ],
    "auto parts": [
        "motorparts", "motor parts", "auto parts", "spare parts", "car parts", "hardware"
    ],
    "gym": [
        "gym", "fitness", "workout", "fitness center"
    ],
    "hotel": [
        "hotel", "hotels", "resort", "resorts", "inn",
        "lodging", "stay", "accommodation", "place to stay"
    ],
    "hospital": [
        "hospital", "medical center", "clinic", "health center",
        "infirmary", "healthcare"
    ],
    "bank": [
        "bank", "banks", "atm", "banking"
    ],
    "gas station": [
        "gas station", "gasoline station", "gasoline",
        "gas", "fuel", "petrol", "petrol station"
    ],
    "supermarket": [
        "supermarket", "supermarkets", "grocery", "grocery store", "groceries",
        "mart", "convenience store", "hypermarket"
    ]
}

LOCAL_DISHES = [
    "salmon","empanada", "bagnet", "poqui poqui", "poqui-poqui", "poquipoqui",
    "longganisa", "igado", "dinakdakan", "pinakbet", "royal bibingka", "miki"
]

FEATURE_ALIASES = {
    "parking": ["parking", "parking space", "car park", "parking lot", "with parking", "has parking"],
    "wifi": ["wifi", "wi-fi", "internet", "free wifi", "free wi-fi", "internet access", "good wifi", "good wi-fi", "working"],
    "ktv": ["ktv", "karaoke", "singing room", "videoke"],
    "pet-friendly": ["pet", "pets", "pet-friendly", "pet friendly", "dog friendly", "cat friendly"],
    "aircon": ["aircon", "air conditioning", "air conditioned", "air-conditioned", "ac"],
    "outdoor": ["outdoor", "al fresco", "outdoor seating", "outside seating"],
    "card": ["card", "credit card", "debit card", "gcash", "cashless", "card payment"],
    "delivery": ["delivery", "deliver", "takeout", "takeaway", "food delivery"],
}

FEATURE_KEYWORDS = list(FEATURE_ALIASES.keys())
THINKING_PHRASES = ["still thinking", "wait", "hold on", "give me a sec", "give me a minute", "thinking", "not sure yet", "wait a bit"]
READY_PHRASES = ["im ready", "i'm ready", "ready", "ok ready", "okay ready"]
GREETINGS = {"hello", "hi", "hey", "sup", "good morning", "good afternoon", "good evening"}

STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "i", "me",
    "my", "to", "for", "in", "at", "of", "and", "or",
    "with", "that", "this", "there", "any", "some",
    "place", "places", "looking", "find", "show",
    "give", "want", "need", "near", "around"
}