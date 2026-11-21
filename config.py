# config.py
STATE_AWAITING_NAME = "AWAITING_NAME"
STATE_IDLE = "IDLE"

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

UNSUPPORTED_LOCATIONS = ["piddig", "pasuquin", "currimao", "dingras"]

CATEGORY_SYNONYMS = {
    "barbershop": ["barbershop", "barber shop", "barber", "salon", "haircut", "hair salon"],
    "tourist spot": [
        "tourist spot", "tourist spots", "attraction", "attractions", "sightseeing",
        "sand dunes", "sand dune", "dunes", "beach", "park", "landmark", "monument",
        "church", "historical site", "destination", "place to visit",
        "museum", "heritage site", "viewpoint", "eco-tourism", "scenic spot", "nature preserve"
    ],
    "restaurant": [
        "restaurant", "restaurants", "resto", "bistro", "eatery",
        "dining", "diner", "grill", "steak", "wings", "pasta", "sushi", "ramen", "seafood",
        "bbq", "barbecue", "fastfood", "fast food", "empanada", "empanadaan",
        "bagnet", "poqui-poqui", "poquipoqui", "poqui poqui", "ilocano food", "local dishes",
        "carinderia", "snack bar", "food stall", "food stalls",
        "catering", "catering services", "food court", "foodcourt", "street food", "local delicacy stall"
    ],
    "bakery": [
        "bakery", "bakeshop", "cake", "cakes", "pastry", "pastries", "bread", "breads", "dessert", "desserts"
    ],
    "samgyupsal": ["samgyupsal", "samgyup", "korean bbq", "korean barbecue", "k-grill", "korean restaurant"],
    "cafe": [
        "cafe", "cafes", "coffee", "coffee shop", "coffee shops", 
        "espresso", "latte", "tea", "tea shop", "cozy cafe", "cozy café", "café",
        "confectionery", "confectionery shop", "beverage", "beverage spot", "milk tea bar",
        "smoothie", "smoothies", "frappe", "frappes", "drink", "drinks",
        "thirsty", "refreshment", "refreshments", "want to drink", "want a drink"
    ],
    "bar": ["bar", "bars", "pub", "pubs", "nightclub", "restobar", "beer", "alcohol", "cocktail", "cocktails", "nightlife"],
    "airport": ["airport", "airplanes", "airplane", "flights", "flight", "fly", "flying", "plane", "planes", "travel by air", "travel via airplane"],
    "mall": [
        "mall", "malls", "shopping mall", "shopping center", "department store", "plaza",
        "public market", "marketplace", "commercial center", "souvenir shop", "pasalubong center", "pasalubong", "retail"
    ],
    "karaoke": ["karaoke", "ktv", "singing", "music lounge", "videoke"],
    "dealership": ["dealership", "motorcycle", "motorcycles", "car dealership", "showroom", "auto sales", "toyota", "honda", "yamaha"],
    "auto parts": ["motorparts", "motor parts", "auto parts", "spare parts", "motorcycle repair", "auto repair", "vulcanizing", "vulcanizing shop", "repair shop"],
    "hardware": ["hardware", "hardware store", "hardware stores", "construction supplies", "lumber", "tools"],
    "computer shop": ["computer shop", "internet cafe", "cyber cafe", "gaming hub", "pc shop", "piso net", "computer repair"],
    "gym": ["gym", "fitness", "workout", "fitness center"],
    "hotel": ["hotel", "hotels", "resort", "resorts", "inn", "lodging", "stay", "accommodation", "place to stay", "transient", "homestay"],
    "hospital": [
        "hospital", "medical center", "clinic", "health center", "infirmary", "healthcare", "medical clinic", "surgical specialist", "doctor"
    ],
    "vet": ["vet", "veterinary", "animal clinic", "pet clinic"],
    "pharmacy": ["pharmacy", "pharmacies", "drugstore"],
    "bank": [
        "bank", "banks", "atm", "banking", "pawnshop", "pawn shop", "pawnshops",
        "transfer", "transfer money", "transfer my money", "send money", "money transfer", 
        "remittance", "western union", "cebuana", "money services", "remittance center"
    ],
    "gas station": ["gas station", "gasoline station", "gasoline", "gas", "fuel", "petrol", "petrol station"],
    "supermarket": [
        "supermarket", "supermarkets", "grocery", "grocery store", "groceries",
        "mart", "convenience store", "hypermarket", "variety store", "general merchandise"
    ],
    "laundry": ["laundry", "laundry service", "laundry shop", "dry cleaning", "wash and fold"],
    "school": ["school", "elementary school", "high school", "integrated school", "educational network"],
    "government": ["government", "municipal hall", "town hall", "government office", "civic center"]
}

LOCAL_DISHES = [
    "salmon", "empanada", "bagnet", "poqui poqui", "poqui-poqui", "poquipoqui",
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
    "smoothies": ["smoothie", "smoothies", "frappe", "frappes", "cold beverage"]
}

FEATURE_KEYWORDS = list(FEATURE_ALIASES.keys())
THINKING_PHRASES = {"still thinking", "wait", "hold on", "give me a sec", "give me a minute", "thinking", "not sure yet", "wait a bit"}
READY_PHRASES = {"im ready", "i'm ready", "ready", "ok ready", "okay ready"}
GREETINGS = {"hello", "hi", "hey", "sup", "good morning", "good afternoon", "good evening"}
# REMOVED "ty" TO FIX THE "thirsty" BUG
THANKS_PHRASES = {"thanks", "thank you", "thx", "thank you so much", "salamat"}
CONVERSATIONAL_FILLER = {
    "i dont know", "i don't know", "sure", "searching for laoag", "yes", "no", "maybe", 
    "ok", "okay", "alright", "idk", "not sure", "help", "what can you do"
}

STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "i", "me",
    "my", "to", "for", "in", "at", "of", "and", "or",
    "with", "that", "this", "there", "any", "some",
    "place", "places", "looking", "find", "show",
    "give", "want", "need", "near", "around"
}