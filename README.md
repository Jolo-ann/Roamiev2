Roamie - Local Place Finder
Roamie is a custom-built Natural Language Processing (NLP) Local Place Finder web application designed to help users explore local venues, landmarks, restaurants, hotels, and services across Ilocos Norte, Philippines.

The application is built entirely from scratch without external AI APIs, external cloud search services, or pre-made machine learning classification libraries.

Features
Rule-Based NLP Query Parsing: Custom intent extraction, category matching, budget extraction, time bound detection, and municipality tag parsing.

Gazetteer and Synonym Engine: Recognizes local dialect terms, municipality aliases, and custom feature tags across Ilocos Norte.

Proximity and Radius Search: Haversine distance formula algorithm to locate places within a specified radius (e.g., 2 km) from a target landmark or city center.

Session Memory State Machine: Preserves selected municipality, category filters, and operating hour constraints across sequential follow-up queries.

Zero Heavy AI Dependencies: 0% dependence on third-party generative models, API keys, or cloud-hosted classifiers.

Architecture Overview
User Interface (templates/index.html, static/style.css, static/script.js): Interactive web frontend supporting place preview cards, detail modals, and weather widgets.

Flask Application (app.py): Web server routing queries, maintaining user session states, evaluating budget limits, and formatting response structures.

NLP Engine (nlp_engine.py): Core processing module responsible for tokenization, n-gram lexical scoring, fuzzy string matching, entity extraction, and Haversine distance calculations.

Configuration (config.py): Centralized repository of supported municipalities, local dish gazetteers, category synonym tables, feature aliases, and stopword dictionaries.

Local Dataset (dataset.json): Structured dataset containing place entries with business names, categories, municipal locations, geographic coordinates, opening/closing schedules, price ranges, features, and keyword tags.

Supported Municipalities and Cities
Cities: Laoag City, Batac City

Municipalities: Adams, Bacarra, Badoc, Bangui, Banna, Burgos, Carasi, Currimao, Dingras, Dumalneg, Marcos, Nueva Era, Pagudpud, Paoay, Pasuquin, Piddig, Pinili, San Nicolas, Sarrat, Solsona, Vintar


Plaintext
roamie-place-finder/
├── app.py
├── nlp_engine.py
├── config.py
├── dataset.json
├── templates/
│   └── index.html
└── static/
    ├── style.css
    ├── script.js
    └── assets/
        └── roamielg.png

Credits
Developed by BSCS4 Group 2 (BSCS4 G2wo) for the CS Elective III Midterm-Final Project.
