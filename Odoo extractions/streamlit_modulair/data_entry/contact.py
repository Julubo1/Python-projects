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

from shared.core import search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping,get_label, extract_country_name
def show():
    st.title("Data Entry Fouten Monitor - Contact Module")

    df_partner = search_read(
        'res.partner',
        domain=[],
        fields=['name', 'country_id', 'email', 'phone', 'industry_id', 'team_id', 'is_company', 'parent_id',
                'x_oem_vendor_ids'],
        context={'lang': 'en_GB'}
    )

    if df_partner.empty:
        st.warning("Geen partnerrecords gevonden.")
    else:
        df_partner['country'] = df_partner['country_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
        df_partner['industry'] = df_partner['industry_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
        df_partner['team'] = df_partner['team_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
        df_partner['parent'] = df_partner['parent_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
        df_partner['OEMs'] = df_partner['x_oem_vendor_ids'].apply(map_oem)

        personen_met_email = df_partner[
            (~df_partner['is_company']) &
            df_partner['email'].notnull() &
            (~df_partner['email'].str.strip().isin(["", "-", "."]))
            ]

        # Groepeer en zoek dubbele e-mails
        email_counts = personen_met_email['email'].str.lower().value_counts()
        dubbele_emails = email_counts[email_counts > 1].index.tolist()

        # ------------------ Checks ------------------

        def is_valid_email(email):
            if not isinstance(email, str) or len(email.strip()) == 0:
                return False
            return re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()) is not None

        def is_valid_phone(phone):
            if not isinstance(phone, str) or len(phone.strip()) < 3:
                return False
            stripped = re.sub(r"[\s\-\(\)\+\.]", "", phone)
            return stripped.isdigit() and len(stripped) >= 5

        fouten = []

        for _, row in df_partner.iterrows():
            issues = []

            if not isinstance(row['name'], str) or row['name'].strip() == "":
                issues.append("Naam ontbreekt")

            if not isinstance(row['country'], str) or row['country'].strip() == "":
                issues.append("Land ontbreekt")

            if row['industry'] == "":
                issues.append("Industry ontbreekt")

            if row['team'] == "":
                issues.append("Business Line ontbreekt")

            if row['email'] and not is_valid_email(row['email']):
                issues.append("Ongeldig e-mailadres")

            if row['phone'] and not is_valid_phone(row['phone']):
                issues.append("Ongeldig telefoonnummer")

            if not row['is_company'] and not row['parent']:
                issues.append("Individu zonder gekoppeld bedrijf")

            if not row['is_company'] and row['parent']:
                if not row.get('OEMs'):
                    issues.append("OEM ontbreekt bij individu")

            if not row['is_company'] and isinstance(row['email'], str):
                if row['email'].strip().lower() in dubbele_emails:
                    issues.append("Dubbel e-mailadres bij meerdere individuen")

            if issues:
                fouten.append({
                    "Naam": row['name'],
                    "Is Bedrijf": "Ja" if row['is_company'] else "Nee",
                    "Bedrijf (parent)": row['parent'],
                    "OEM": row['OEMs'],
                    "Land": row['country'],
                    "Industry": row['industry'],
                    "Business Line": row['team'],
                    "Email": row['email'],
                    "Telefoon": row['phone'],
                    "Fouten": "; ".join(issues)
                })

        if not fouten:
            st.success("Geen data entry fouten gevonden.")
        else:
            fout_df = pd.DataFrame(fouten)
            unieke_fouten = sorted({f for foutenlijst in fout_df['Fouten'] for f in foutenlijst.split("; ")})
            # Contact-pagina
            fout_filter = st.selectbox(
                "Filter op fouttype (Contact)",
                ["Toon alles"] + unieke_fouten,
                key="contact_fout_filter"
            )

            if fout_filter != "Toon alles":
                fout_df = fout_df[fout_df['Fouten'].str.contains(fout_filter)]

            st.warning(f"{len(fout_df)} foutieve records gevonden.")
            st.dataframe(fout_df)