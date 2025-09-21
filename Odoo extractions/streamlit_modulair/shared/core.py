import streamlit as st
import xmlrpc.client
import pandas as pd
from datetime import datetime, date, timedelta
import re
import numpy as np
from dateutil import parser
import plotly.express as px
from streamlit_plotly_events import plotly_events
import requests
from rapidfuzz import fuzz, process

# Odoo config
url = ""
db = ""
username = ""
password = ""
api=""


common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")


def strip_html(text):
    if pd.isnull(text):
        return text
    return re.sub(r'<.*?>', '', str(text))

def extract_country_name(x):
    if isinstance(x, (list, tuple)) and len(x) == 2:
        return x[1]
    elif pd.isna(x):
        return 'Onbekend'
    else:
        return str(x)

def get_label(val):
    if isinstance(val, list) and len(val) == 2:
        return val[1]
    elif isinstance(val, dict) and 'name' in val:
        return val['name']
    elif val is None:
        return 'Onbekend'
    else:
        return str(val)


def filter_df_on_search(df, search_term):
    if not search_term or len(search_term) < 2:
        return df
    search_term = search_term.lower()
    return df[df.apply(lambda row: row.astype(str).str.lower().str.contains(search_term, na=False).any(), axis=1)]


def filter_on_date_range(df, date_field, start_date, end_date):
    df[date_field] = pd.to_datetime(df[date_field], errors='coerce')
    mask = (df[date_field] >= pd.to_datetime(start_date)) & (df[date_field] <= pd.to_datetime(end_date))
    return df.loc[mask]


def categorize_activity_state(row):
    today = date.today()
    if row['state'] == 'done':
        return 'done'
    elif row['state'] == 'planned':
        return 'planned'
    elif row['date_deadline'] is pd.NaT or row['date_deadline'] is None:
        return 'planned'
    else:
        if row['date_deadline'] == today:
            return 'today'
        elif row['date_deadline'] < today:
            return 'overdue'
        else:
            return 'planned'


def format_currency(x):
    if pd.notnull(x):
        return f"€ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return ""


# ----------------- DATA OPHALEN ------------------

# Functie om mapping toe te passen
def map_oem(value):
    if isinstance(value, list):
        return ', '.join(contact_mapping.get(int(v), str(v)) for v in value)
    elif pd.notnull(value):
        return contact_mapping.get(int(value), str(value))
    else:
        return None

# Functie om vertalingen op te halen via name_get
def get_translated_names(model, ids, context={'lang': 'en_GB'}):
    if not ids:
        return {}
    try:
        name_tuples = models.execute_kw(
            db, uid, password,
            model, 'name_get',
            [ids],
            {'context': context}
        )
        return {item[0]: item[1] for item in name_tuples}
    except Exception:
        return {}


def get_exchange_rate(currency_rates, currency_id, date):
    try:
        # Filter op juiste valuta
        rates = [r for r in currency_rates if r['currency_id'][0] == currency_id]
        if not rates:
            return 1.0  # fallback: geen koers gevonden

        # Sorteer op datum (meest recent vóór of op opgegeven datum)
        rates_sorted = sorted(
            [r for r in rates if r['name'] <= date],
            key=lambda r: r['name'],
            reverse=True
        )
        if rates_sorted:
            return rates_sorted[0]['rate']
        else:
            return 1.0  # fallback: geen datum vóór opgegeven datum
    except Exception as e:
        return 1.0  # veilige fallback


# Caching van Odoo zoekopdrachten
@st.cache_data(ttl=300)
def search_read(model, domain=None, fields=None, context=None, order=None):
    domain = domain or []
    fields = fields or []
    context = context or {'lang': 'en_GB'}
    order = order or []
    try:
        records = models.execute_kw(
            db, uid, password,
            model, 'search_read',
            [domain],
            {'fields': fields, 'order': order, 'context': context}
        )
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Fout bij ophalen data van {model}: {e}")
        return pd.DataFrame()


# Filter functie op jaartal
def filter_on_year(df, date_columns, year):
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    mask = pd.Series(False, index=df.index)
    for col in date_columns:
        if col in df.columns:
            mask = mask | (df[col].dt.year == year)
    return df[mask]

# Mapping van contact_id naar OEM naam
contact_mapping = {252311: '2QuartMedical',
                   254869: '3D-PLUS',
                   64872: 'Ametek Advanced Measurement Technology',
                   64873: 'Ametek GmbH',
                   64874: 'Ametek Inc. Advanced Measurement Technology',
                   181721: 'Argon Electronics',
                   252041: 'Argon Simulators',
                   64916: 'Ashland Industries Europe GmbH',
                   64917: 'Ashland Industries Nederland BV',
                   249275: 'Ashland Specialty Ingredients G.P.',
                   64923: 'Astrophysics Inc.',
                   64924: 'Astrophysics Intl. Ltd.',
                   257477: 'Baltic Scientific Instruments (BSI)',
                   65042: 'Bertin GmbH',
                   99408: 'Bertin GmbH, Damian Holzmann',
                   248395: 'Bertin Technologies',
                   65240: 'Centronic Limited (Exosens)',
                   65448: 'Digital River International S.a.r.l.',
                   65549: 'Electronic Control Concepts',
                   65701: 'GEORADIS s.r.o.',
                   65707: 'GL OPTIC Polska Sp. z.o.o. S.k',
                   256223: 'HTSL - High Technology Sources Limited',
                   256224: 'HTSL - High Technology Sources Limited, Gareth Belton',
                   255499: 'Herado',
                   66013: 'Inspired Energy LLC',
                   251857: 'International Specialty Products (Ashland)',
                   257539: 'KALCIO Healthcare',
                   66080: 'KMWE Precision B.V.',
                   66133: 'Kromek Ltd.',
                   66160: 'LND Inc',
                   249666: 'LRQA Nederland',
                   66209: 'Logos Imaging LLC',
                   250020: 'Ludiqx B.V.',
                   249481: 'Ludlum GmbH',
                   66215: 'Ludlum Measurements Inc.',
                   251752: 'Meicen',
                   251828: 'Mikrocentrum Activiteiten B.V.',
                   66363: 'Mirion Technologies',
                   66365: 'Mirion Technologies BV',
                   66369: 'Mohawk Safety',
                   253611: 'Nucletron Operations B.V. (supplier for filmstrips)',
                   251656: 'PHDS',
                   251704: 'POLIMASTER Europe UAB',
                   66602: 'Peter Timmers Handelsonderneming B.V.',
                   66707: 'QA Benchmark, LLC',
                   66753: 'Radiation Detection Systems AB',
                   66755: 'Radiation Products Design, Inc.',
                   66756: 'Radiation Solutions Inc.',
                   66862: 'S.E. International, Inc.',
                   66868: 'SAIC Exploranium',
                   66877: 'SDEC France',
                   66890: 'SITEK Electro Optics AB',
                   257532: 'SRP The Society for Radiological Protection',
                   67012: 'Spectrum Techniques, LLC.',
                   257259: 'Spectrum Techniques, LLC., Spectrum Order',
                   67067: 'Sun Nuclear B.V.',
                   65152: 'Sun Nuclear Corp. (CIRS department)',
                   67068: 'Sun Nuclear Corporation',
                   251607: 'Sun Nuclear GMbH',
                   67172: 'Tracerco',
                   67214: 'Ultra Nuclear Limited',
                   67294: 'Van Dam Handelsonderneming B.V.',
                   67332: 'Vehant Technologies Pvt. Ltd.',
                   255486: 'WERMA Benelux B.V.',
                   252756: 'YONGLI BELTING Nederland Echt B.V.',}

 # --- Dynamische mapping Odoo-industrieën naar OSM-tags ---
industry_osm_mapping = {
    "Hospitals | RT": {
        "keys": [
            ("healthcare", "radiotherapy"),
            ("healthcare:speciality", "radiotherapy"),
            ("amenity", "clinic"),
            ("amenity", "hospital")
        ],
        "fuzzy_keywords": ["radiotherapy", "radio", "oncology", "clinic", "hospital"]
    },
    "Hospitals": {
        "keys": [("amenity", "hospital")],
        "fuzzy_keywords": ["hospital", "clinic", "medical center"]
    },
    "Blood Bank": {
        "keys": [("healthcare", "blood_donation"), ("amenity", "blood_donation")],
        "fuzzy_keywords": ["blood", "donation", "transfusion"]
    },
    "Oil & Gas": {
        "keys": [
            ("industrial", "oil"),
            ("industrial", "gas"),
            ("office", "oil_company"),
            ("man_made", "storage_tank")
        ],
        "brands": ["Shell", "BP", "TotalEnergies", "ExxonMobil", "Chevron"],
        "fuzzy_keywords": ["oil", "gas", "petrochemical", "refinery"]
    },
    "Logistics / freight / parcels / cargo / offshore / ports / airports": {
        "keys": [
            ("building", "warehouse"),
            ("office", "logistics"),
            ("landuse", "industrial"),
            ("aeroway", "terminal"),
            ("man_made", "pier"),
            ("harbour", "yes"),
            ("aeroway", "aerodrome")
        ],
        "fuzzy_keywords": ["logistics", "freight", "cargo", "port", "airport", "terminal", "warehouse"]
    },
    "Airports": {
        "keys": [("aeroway", "aerodrome")],
        "fuzzy_keywords": ["airport", "aerodrome", "runway", "terminal"]
    },
    "Veterinary": {
        "keys": [("amenity", "veterinary")],
        "fuzzy_keywords": ["vet", "veterinary", "animal clinic"]
    },
    "Dental": {
        "keys": [("healthcare", "dentist"), ("amenity", "dentist")],
        "fuzzy_keywords": ["dentist", "dental"]
    },
    "Nuclear energy": {
        "keys": [("power", "nuclear"), ("generator:source", "nuclear")],
        "fuzzy_keywords": ["nuclear", "plant", "power"]
    },
    "Power plant": {
        "keys": [("power", "plant")],
        "fuzzy_keywords": ["power plant", "electricity", "station"]
    },
    "Renewable Energy": {
        "keys": [("generator:source", "solar"), ("generator:source", "wind"), ("power", "plant")],
        "fuzzy_keywords": ["solar", "wind", "renewable", "turbine"]
    },
    "Security companies": {
        "keys": [("office", "security")],
        "fuzzy_keywords": ["security", "guard", "surveillance"]
    },
    "Hotels": {
        "keys": [("tourism", "hotel")],
        "fuzzy_keywords": ["hotel", "resort", "hostel"]
    },
    "Retail": {
        "keys": [("shop", None)],
        "fuzzy_keywords": ["retail", "store", "supermarket", "mall"]
    },
    "Food & agri": {
        "keys": [("landuse", "farmland"), ("shop", "farm"), ("craft", "butcher")],
        "fuzzy_keywords": ["farm", "agriculture", "food", "produce"]
    },
    "Textile & laundry": {
        "keys": [("shop", "laundry"), ("amenity", "laundry"), ("craft", "tailor")],
        "fuzzy_keywords": ["laundry", "textile", "tailor", "clothing"]
    },
    "Medical OEM": {
        "keys": [("office", "company"), ("industrial", "medical")],
        "fuzzy_keywords": ["medical", "device", "equipment"]
    },
    "Research & laboratories": {
        "keys": [("office", "research"), ("amenity", "research_institute"), ("building", "laboratory")],
        "fuzzy_keywords": ["research", "lab", "laboratory", "institute"]
    },
    "Educational institutions": {
        "keys": [("amenity", "school"), ("amenity", "university")],
        "fuzzy_keywords": ["school", "university", "education", "college"]
    },
    "Construction": {
        "keys": [("office", "construction")],
        "fuzzy_keywords": ["construction", "builder", "contractor"]
    },
    "Courts": {
        "keys": [("amenity", "courthouse")],
        "fuzzy_keywords": ["court", "justice", "courthouse"]
    },
    "Prisons": {
        "keys": [("amenity", "prison")],
        "fuzzy_keywords": ["prison", "jail", "correction"]
    },
    "ICT": {
        "keys": [("office", "it"), ("office", "software")],
        "fuzzy_keywords": ["ICT", "software", "tech", "digital", "IT"]
    },
    "Software & ICT": {
        "keys": [("office", "software"), ("office", "it")],
        "fuzzy_keywords": ["software", "IT", "technology", "digital"]
    },
    "Reseller": {
        "keys": [("shop", None)],
        "fuzzy_keywords": ["reseller", "sales", "distribution"]
    },
    "Medical Industry": {
        "keys": [("industrial", "medical")],
        "fuzzy_keywords": ["medical", "device", "pharma"]
    },
    "Ship Supplier": {
        "keys": [("man_made", "pier"), ("shop", "ship_chandler")],
        "fuzzy_keywords": ["ship", "marine", "supplier"]
    },
    "Ports": {
        "keys": [("harbour", "yes"), ("man_made", "pier")],
        "fuzzy_keywords": ["port", "harbour", "terminal", "dock"]
    },
    "First responders": {
        "keys": [("amenity", "fire_station"), ("amenity", "police"), ("emergency", "ambulance_station")],
        "fuzzy_keywords": ["emergency", "fire", "police", "ambulance"]
    },
    "Defence": {
        "keys": [("military", "barracks"), ("military", "office")],
        "fuzzy_keywords": ["military", "army", "navy", "airforce"]
    }
}

# Wikidata Q-codes voor industrie types (meest gebruikte instanties)
industry_to_wikidata_q = {
    "Hospitals | RT": "Q16917",  # hospital
    "Hospitals": "Q16917",
    "Blood Bank": "Q4830453",  # blood bank niet standaard, fallback naar health organization Q16917
    "Oil & Gas": "Q11652",  # oil and gas company
    "Logistics / freight / parcels / cargo / offshore / ports / airports": "Q728937",  # logistics company
    "Airports": "Q1248784",  # airport
    "Veterinary": "Q155223",  # veterinary practice
    "Dental": "Q74127",  # dentist
    "Nuclear energy": "Q16965",  # nuclear power plant
    "Power plant": "Q16965",  # power plant (general)
    "Renewable Energy": "Q1048835",  # renewable energy company
    "Security companies": "Q1393554",  # security company
    "Hotels": "Q27686",  # hotel
    "Retail": "Q431289",  # retail company
    "Food & agri": "Q15642541",  # agricultural company
    "Textile & laundry": "Q431289",  # retail company fallback
    "Medical OEM": "Q16917",  # medical device manufacturer fallback
    "Research & laboratories": "Q1577339",  # research institute
    "Educational institutions": "Q2385804",  # educational institution
    "Construction": "Q41298",  # construction company
    "Courts": "Q13226383",  # court of law
    "Prisons": "Q4099036",  # prison
    "ICT": "Q82594",  # IT company
    "Software & ICT": "Q82594",
    "Reseller": "Q431289",
    "Medical Industry": "Q16917",  # medical device fallback
    "Ship Supplier": "Q728937",  # logistics company fallback
    "Ports": "Q1754927",  # port
    "First responders": "Q494122",  # emergency services
    "Defence": "Q101352",  # military organization
}


def build_osm_query(industry, country_iso=None, mapping=None):
    mapping_entry = mapping.get(industry, {})
    osm_tags = mapping_entry.get("keys", [])
    fuzzy_keywords = mapping_entry.get("fuzzy", [])
    brands = mapping_entry.get("brands", [])

    area_filter = f'area["ISO3166-1"="{country_iso}"]->.searchArea;' if country_iso else ""

    queries = []

    # OSM key/value pairs
    for key, value in osm_tags:
        for element in ["node", "way", "relation"]:
            if value:
                queries.append(f'{element}["{key}"="{value}"](area.searchArea);')
            else:
                queries.append(f'{element}["{key}"](area.searchArea);')

    # Fuzzy matching on name and description
    for keyword in fuzzy_keywords:
        for element in ["node", "way", "relation"]:
            queries.append(f'{element}["name"~"{keyword}",i](area.searchArea);')
            queries.append(f'{element}["description"~"{keyword}",i](area.searchArea);')

    # Brand or operator match
    for brand in brands:
        for element in ["node", "way", "relation"]:
            queries.append(f'{element}["brand"~"{brand}",i](area.searchArea);')
            queries.append(f'{element}["operator"~"{brand}",i](area.searchArea);')

    # Combine all queries
    overpass_query = f"""
       [out:json][timeout:25];
       {area_filter}
       (
           {''.join(queries)}
       );
       out center tags;
       """

    return overpass_query.strip()


wikidata_country_codes = {
    "Netherlands": "Q55",
    "Belgium": "Q31",
    "France": "Q142",
    "Germany": "Q183",
    "United States": "Q30"}


def query_wikidata(industry, country_label):
    country_code = wikidata_country_codes.get(country_label)
    instance_q = industry_to_wikidata_q.get(industry)
    if not country_code or not instance_q:
        print(f"Geen wikidata code voor land '{country_label}' of industrie '{industry}'")
        return pd.DataFrame()
    sparql = f"""
       SELECT ?org ?orgLabel ?coord WHERE {{
         ?org wdt:P31/wdt:P279* wd:{instance_q} ;
              wdt:P17 wd:{country_code} ;
              wdt:P625 ?coord .
         SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
       }}
       LIMIT 100
       """
    url = "https://query.wikidata.org/sparql"
    headers = {'Accept': 'application/sparql-results+json'}
    resp = requests.get(url, params={'query': sparql}, headers=headers)
    if resp.status_code != 200:
        print(f"Wikidata query fout: {resp.status_code}")
        return pd.DataFrame()
    results = resp.json().get("results", {}).get("bindings", [])
    data = []
    for item in results:
        label = item['orgLabel']['value']
        coord = item['coord']['value']
        coord = coord.replace("Point(", "").replace(")", "")
        lon, lat = coord.split()
        data.append({"name": label, "lat": float(lat), "lon": float(lon), "type": industry})
    return pd.DataFrame(data)

def extract_payment_days(payment_term_id):
    if isinstance(payment_term_id, list) and len(payment_term_id) == 2:
        term_name = payment_term_id[1]
        for part in term_name.split():
            if part.isdigit():
                return int(part)
    return 30

def format_euro(value):
    try:
        return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return value

def get_team_name_by_user(user_id):
    if user_id is None:
        return 'Geen Team'
    for team in team_users_map.values():
        if user_id in team['users']:
            return team['name']
    return 'Geen Team'

def extract_hours(name):
    if not isinstance(name, str):
        return 40.0
    match = re.search(r'(\d+)\s*Hours', name, re.IGNORECASE)
    if match:
        return float(match.group(1))
    else:
        return 40.0

def safe_get_currency_id(row):
    if isinstance(row['currency_id'], list) and len(row['currency_id']) == 2:
        return row['currency_id'][0]
    return None

def get_calendar_name(val):
    if isinstance(val, (list, tuple)) and len(val) > 1:
        return val[1]
    return ''


