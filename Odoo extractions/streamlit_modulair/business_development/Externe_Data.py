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

from shared.core import (
    search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping,
    filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names,
    get_exchange_rate, industry_to_wikidata_q, build_osm_query, wikidata_country_codes,
    query_wikidata, industry_osm_mapping
)

STOPWORDS = {
    "bv", "de", "en", "van", "company", "ltd", "inc", "the", "and",
    "sa", "gmbh", "limited", "co", "nv", "ziekenhuis", "groep", "group","&", "clinic", "centrum", "hospital", "location", "lokatie", "locatie", "medisch"
}

def remove_stopwords(text):
    if not isinstance(text, str):
        return ""
    words = re.findall(r'\w+', text.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    return " ".join(filtered)

def tokenize_name(name):
    if not isinstance(name, str):
        return set()
    words = re.findall(r'\w+', name.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    return set(filtered)

def is_partial_token_match(odoo_name, ext_name, threshold=0.6):
    odoo_tokens = tokenize_name(odoo_name)
    ext_tokens = tokenize_name(ext_name)
    if not odoo_tokens or not ext_tokens:
        return False
    overlap = len(odoo_tokens.intersection(ext_tokens))
    min_len = min(len(odoo_tokens), len(ext_tokens))
    ratio = overlap / min_len
    return ratio >= threshold

def show():

    st.title("Externe Data vs Odoo")

    # --- Bedrijven uit Odoo ophalen ---
    odoo_partners = search_read(
        'res.partner',
        domain=[('is_company', '=', True), ('industry_id', '!=', False)],
        fields=['name', 'industry_id', 'country_id'],
        context={'lang': 'en_GB'}
    )
    df_odoo = pd.DataFrame(odoo_partners)
    df_odoo['country'] = df_odoo['country_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else '')
    df_odoo['industry'] = df_odoo['industry_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else '')

    # Filters
    selected_country = st.selectbox("Land", sorted(df_odoo['country'].dropna().unique()))
    selected_industries = st.multiselect("Industrieën", sorted(df_odoo['industry'].dropna().unique()))
    filtered_odoo = df_odoo[(df_odoo['country'] == selected_country) & (df_odoo['industry'].isin(selected_industries))]
    st.success(f"{len(filtered_odoo)} bedrijven geselecteerd uit Odoo")

    source_choice = st.selectbox("Kies bron", ["OpenStreetMap", "Wikidata", "Eigen bestand"])

    uploaded_file = None
    if source_choice == "Eigen bestand":
        uploaded_file = st.file_uploader("Upload een extern bedrijvenbestand (CSV of Excel)", type=["csv", "xlsx"])

    if st.button("Vergelijk data"):
        if filtered_odoo.empty:
            st.warning("Geen Odoo-bedrijven om te matchen.")
            st.stop()

        all_data = []
        df = pd.DataFrame()
        if source_choice == "OpenStreetMap":
            st.info("Zoekt via Overpass (OSM)...")
            iso_map = {"Netherlands": "NL", "Belgium": "BE", "France": "FR", "Germany": "DE"}
            iso = iso_map.get(selected_country)

            overpass_servers = [
                "https://overpass-api.de/api/interpreter",
                "https://lz4.overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter"
            ]

            for industry in selected_industries:
                query = build_osm_query(industry, iso, industry_osm_mapping)

                response = None
                for server_url in overpass_servers:
                    try:
                        resp = requests.get(server_url, params={"data": query}, timeout=60)
                        resp.raise_for_status()
                        response = resp
                        break  # Succes, stop met proberen van andere servers
                    except requests.exceptions.RequestException as e:
                        st.warning(f"Fout bij server {server_url}: {e}, probeer volgende server...")

                if response is None:
                    st.error(f"Alle Overpass API servers faalden voor industrie {industry}.")
                    continue

                elems = response.json().get("elements", [])
                for el in elems:
                    tags = el.get("tags", {})
                    if not tags.get("name"):
                        continue
                    lat = el.get("lat") or el.get("center", {}).get("lat")
                    lon = el.get("lon") or el.get("center", {}).get("lon")
                    all_data.append({
                        "name": tags.get("name"),
                        "city": tags.get("addr:city", ""),
                        "lat": lat,
                        "lon": lon,
                        "country": selected_country
                    })

            df = pd.DataFrame(all_data)
            st.write(df)

        elif source_choice == "Wikidata":
            st.info("Zoekt via Wikidata SPARQL...")
            for industry in selected_industries:
                df_part = query_wikidata(industry, selected_country)
                df_part["industry"] = industry
                all_data.append(df_part)
            df = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
            if not df.empty:
                st.write(df[["name", "type", "lat", "lon"]])
            else:
                st.warning("Geen resultaten gevonden voor Wikidata.")

        elif source_choice == "Eigen bestand":
            if uploaded_file is not None:
                # Bestand inlezen
                if uploaded_file.name.endswith(".csv"):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".xlsx"):
                    df = pd.read_excel(uploaded_file)
                else:
                    st.error("Ongeldig bestandstype.")
                    st.stop()

                # Kolomnamen naar lowercase
                df.columns = df.columns.str.lower()

                # Mapping alternatieve kolomnamen -> standaardnamen
                column_mapping = {
                    'naam': 'name',
                    'bedrijf': 'name',
                    'bedrijfsnaam': 'name',
                    'land': 'country',
                    'plaats': 'city',
                }

                # Hernoemen waar nodig
                df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns}, inplace=True)

                # Country check
                if 'country' in df.columns:
                    df['country_final'] = df['country']
                elif 'city' in df.columns:
                    df['country_final'] = df['city']
                else:
                    st.error("Bestand mist kolom 'country' of 'city'. Eén van beide is verplicht.")
                    st.stop()

                df['country_final'] = df['country_final'].astype(str).str.strip().str.lower()
                selected_country_normalized = selected_country.strip().lower()
                df = df[df['country_final'] == selected_country_normalized]

                # Name check
                if 'name' not in df.columns:
                    st.error("Bestand moet een kolom 'name' bevatten (of een alternatief zoals 'naam' of 'bedrijf').")
                    st.stop()

                st.success(f"{len(df)} bedrijven geladen uit upload.")
                st.dataframe(df)

        # Voeg 'name_lower' kolom toe met stopwoorden verwijderd
        ext = df.copy()
        if 'name' in ext.columns:
            ext['name_lower'] = ext['name'].apply(remove_stopwords)
        else:
            ext['name_lower'] = ''

        odoo = filtered_odoo.copy()
        odoo['name_lower'] = odoo['name'].apply(remove_stopwords)

        # Exacte matches (op name_lower)
        exact = pd.merge(
            odoo, ext, on='name_lower', how='inner', suffixes=('_odoo', '_ext')
        )
        exact = exact.drop(columns=['industry_id'], errors='ignore')
        exact = exact.drop(columns=['country_id'], errors='ignore')
        st.subheader(f"Exacte matches: {len(exact)}")
        st.write(exact)

        # Fuzzy match voor Odoo-namen zonder exacte match
        unmatched = odoo.loc[~odoo['name_lower'].isin(exact['name_lower'])]
        choices = ext['name_lower'].dropna().unique().tolist()

        fuzzy_matches = []
        for idx, row in unmatched.iterrows():
            match = process.extractOne(
                row['name_lower'], choices, scorer=fuzz.token_sort_ratio, score_cutoff=50
            )
            if match:
                matched_name, score = match[0], match[1]

                # Accepteer match als hoge score of token-overlap voldoet
                if score >= 50 and is_partial_token_match(row['name_lower'], matched_name, threshold=0.5):
                    fuzzy_matches.append({
                        #'odoo_index': idx,
                        #'odoo_name': row['name'],
                        'odoo_name_lower': row['name_lower'],
                        'matched_external_name': matched_name,
                        #'score': score,
                        'industry': row.get('industry', '')
                    })
                elif score >= 85:
                    fuzzy_matches.append({
                        #'odoo_index': idx,
                        #'odoo_name': row['name'],
                        'odoo_name_lower': row['name_lower'],
                        'matched_external_name': matched_name,
                        #'score': score,
                        'industry': row.get('industry', '')
                    })


        df_fuzzy = pd.DataFrame(fuzzy_matches)
        st.subheader(f"Fuzzy matches: {len(df_fuzzy)}")
        st.write(df_fuzzy)

        # Bepaal alle gematchte Odoo namen (exact + fuzzy)
        matched_odoo_names = set(exact['name_lower'])
        if not df_fuzzy.empty:
            matched_odoo_names.update(df_fuzzy['odoo_name_lower'])

        # Odoo bedrijven zonder match
        not_matched = odoo.loc[~odoo['name_lower'].isin(matched_odoo_names)]
        st.subheader(f"Odoo bedrijven zonder match (exact of fuzzy): {len(not_matched)}")
        if not not_matched.empty:
            st.dataframe(not_matched[['name', 'industry', 'country']])
        else:
            st.info("Alle Odoo bedrijven zijn gematcht met de externe dataset.")

if __name__ == "__main__":
    show()
