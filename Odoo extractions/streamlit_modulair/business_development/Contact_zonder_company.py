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
    st.title("Contactpersonen zonder Company")
    if st.button("Ververs contactpersonen"):
        st.rerun()

    # Filters
    contact_type = st.radio("Type contactpersoon", options=["Alle", "Individu", "Bedrijf"], index=1)
    oem_filter = st.radio("Filter op OEM", options=["Alles", "Met OEM", "Zonder OEM"], index=0)

    # Contactpersonen ophalen zonder gekoppelde company
    df_contacts = search_read(
        'res.partner',
        domain=[('parent_id', '=', False)],
        fields=['id', 'name', 'x_oem_vendor_ids', 'is_company', 'create_uid', 'create_date'],
        context={'lang': 'en_GB'}
    )

    if df_contacts.empty:
        st.warning("Geen contactpersonen zonder bedrijf gevonden.")
        st.stop()

    # OEM info
    df_contacts['Aantal OEMs'] = df_contacts['x_oem_vendor_ids'].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )
    df_contacts['Heeft OEM?'] = df_contacts['Aantal OEMs'].apply(lambda x: '✅ Ja' if x > 0 else '❌ Nee')

    # Aangemaakt door
    def extract_creator(val):
        if isinstance(val, list) and len(val) == 2:
            return val[1]
        return "Onbekend"

    df_contacts['Aangemaakt door'] = df_contacts['create_uid'].apply(extract_creator)

    # Conversie datumveld
    df_contacts['Aangemaakt op'] = pd.to_datetime(df_contacts['create_date'])

    # === DATUMFILTER ===
    st.markdown("### Filter op aanmaakdatum")
    min_date = df_contacts['Aangemaakt op'].min()
    max_date = df_contacts['Aangemaakt op'].max()

    start_date = st.date_input("Vanaf", value=min_date.date(), min_value=min_date.date(), max_value=max_date.date())
    end_date = st.date_input("Tot en met", value=max_date.date(), min_value=min_date.date(), max_value=max_date.date())

    df_contacts = df_contacts[
        (df_contacts['Aangemaakt op'] >= pd.to_datetime(start_date)) &
        (df_contacts['Aangemaakt op'] <= pd.to_datetime(end_date) + pd.Timedelta(days=1))
        ]

    # Filter op type (persoon/bedrijf)
    if contact_type == "Individu":
        df_contacts = df_contacts[df_contacts['is_company'] == False]
    elif contact_type == "Bedrijf":
        df_contacts = df_contacts[df_contacts['is_company'] == True]

    # Filter op OEM
    if oem_filter == "Met OEM":
        df_contacts = df_contacts[df_contacts['Aantal OEMs'] > 0]
    elif oem_filter == "Zonder OEM":
        df_contacts = df_contacts[df_contacts['Aantal OEMs'] == 0]

    # Tabel tonen
    aantal_contacten = len(df_contacts)
    st.subheader(f"Contacten zonder gekoppeld bedrijf ({aantal_contacten})")

    st.dataframe(df_contacts[[
        'name', 'is_company', 'Aantal OEMs', 'Heeft OEM?', 'Aangemaakt door', 'Aangemaakt op'
    ]].rename(columns={
        'name': 'Naam',
        'is_company': 'Is Bedrijf'
    }).sort_values("Aangemaakt op", ascending=False).reset_index(drop=True), use_container_width=True)