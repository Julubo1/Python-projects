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

from shared.core import search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate
def show():
    st.title("OEM Contact Coverage")

    # 1. Data ophalen
    df_contacts = search_read(
        'res.partner',
        domain=[('is_company', '=', False), ('active', '=', True)],
        fields=['id', 'name', 'parent_id', 'industry_id', 'x_oem_vendor_ids', 'country_id'],
        context={'lang': 'en_GB'}
    )

    # Controle of data beschikbaar is
    if df_contacts.empty:
        st.warning("Geen contactpersonen gevonden.")
        st.stop()

    # 2. Helperfunctie om labels uit Odoo tuples/lists te halen
    def get_label(val):
        if isinstance(val, list) and len(val) == 2:
            return val[1]
        elif isinstance(val, dict) and 'name' in val:
            return val['name']
        elif val is None:
            return None
        else:
            return str(val)

    # 3. Labels extraheren
    df_contacts['industry'] = df_contacts['industry_id'].apply(get_label)
    df_contacts['country'] = df_contacts['country_id'].apply(get_label)
    df_contacts['company'] = df_contacts['parent_id'].apply(get_label)
    df_contacts['parent_id'] = df_contacts['parent_id'].apply(
        lambda x: x[0] if isinstance(x, list) and len(x) > 0 else None)

    # 4. OEM mapping toepassen (oem_ids naar naam)
    df_contacts['oem_names'] = df_contacts['x_oem_vendor_ids'].apply(
        lambda oem_ids: [contact_mapping.get(oem_id, f"OEM-{oem_id}") for oem_id in oem_ids] if isinstance(oem_ids,
                                                                                                           list) else []
    )

    # 5. OEM & Industry selecties
    unique_industries = sorted([i for i in df_contacts['industry'].dropna().unique()])
    selected_industries = st.multiselect("Selecteer Industry(s)", options=unique_industries)

    selected_oem_name = st.selectbox("Selecteer OEM", options=sorted(contact_mapping.values()))

    unique_countries = sorted([c for c in df_contacts['country'].dropna().unique()])
    selected_countries = st.multiselect("Optioneel: Filter op Land(en)", options=unique_countries)

    # 6. Verwerking bij selectie
    if selected_industries and selected_oem_name:
        # Zoek de OEM-id bij de geselecteerde OEM-naam
        selected_oem_id = next((k for k, v in contact_mapping.items() if v == selected_oem_name), None)

        # Filter op Industry
        df_filtered = df_contacts[df_contacts['industry'].isin(selected_industries)]

        # Optioneel: filter op Land
        if selected_countries:
            df_filtered = df_filtered[df_filtered['country'].isin(selected_countries)]

        # Bedrijven waarvan minstens één contactpersoon deze OEM heeft
        companies_with_oem = df_filtered[
            df_filtered['x_oem_vendor_ids'].apply(lambda x: selected_oem_id in x if isinstance(x, list) else False)
        ]['parent_id'].dropna().unique()

        # Alle bedrijven in scope
        all_companies = df_filtered['parent_id'].dropna().unique()

        # Bedrijven zonder enige contactpersoon met deze OEM
        companies_without_oem = [c for c in all_companies if c not in companies_with_oem]

        # Resultaat tonen
        df_result = df_filtered[df_filtered['parent_id'].isin(companies_without_oem)]
        df_result = df_result.groupby('parent_id').first().reset_index()
        df_result = df_result[['parent_id', 'company', 'country']].rename(
            columns={'parent_id': 'Bedrijf ID', 'company': 'Bedrijfsnaam'})

        st.subheader(f"Bedrijven zonder contactpersoon voor OEM '{selected_oem_name}'")
        st.dataframe(df_result.reset_index(drop=True))
    else:
        st.info("Selecteer minimaal één Industry en een OEM om het overzicht te tonen.")