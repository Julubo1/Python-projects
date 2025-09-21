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
    st.title("OEM's per Bedrijf")

    # contact_mapping omzetten naar DataFrame
    df_oem = pd.DataFrame(contact_mapping.items(), columns=['oem_id', 'oem_name']).set_index('oem_id')

    # Contactpersonen ophalen met OEM ids
    df_contacts = search_read(
        'res.partner',
        domain=[('x_oem_vendor_ids', '!=', False)],
        fields=['id', 'name', 'x_oem_vendor_ids', 'parent_id'],
        context={'lang': 'en_GB'}
    )

    if df_contacts.empty:
        st.warning("Geen contactpersonen met OEM gevonden.")
        st.stop()

    # OEM ID's exploderen
    df_contacts = df_contacts.explode('x_oem_vendor_ids')
    df_contacts = df_contacts[df_contacts['x_oem_vendor_ids'].notna()]

    # OEM naam toevoegen
    df_contacts['OEM'] = df_contacts['x_oem_vendor_ids'].map(df_oem['oem_name'])

    # Bedrijfsnaam extraheren uit parent_id
    def extract_company(val):
        if isinstance(val, (list, tuple)) and len(val) > 1:
            return val[1]
        elif isinstance(val, dict) and 'name' in val:
            return val['name']
        elif pd.isna(val):
            return ''
        else:
            return str(val)

    df_contacts['Bedrijf'] = df_contacts['parent_id'].apply(extract_company)

    # Filter lege bedrijven eruit
    df_contacts = df_contacts[df_contacts['Bedrijf'].notna() & (df_contacts['Bedrijf'] != '')]

    bedrijven_lijst = sorted(df_contacts['Bedrijf'].unique().tolist())
    selected_company = st.selectbox("Selecteer een bedrijf", bedrijven_lijst)

    if selected_company:
        df_filtered = df_contacts[df_contacts['Bedrijf'] == selected_company]

        # Contactpersonen en hun OEMs
        df_resultaat = df_filtered[['name', 'OEM']].rename(columns={'name': 'Contactpersoon'})

        # OEM-matrix per contactpersoon direct tonen
        matrix = df_resultaat.pivot_table(index='Contactpersoon', columns='OEM', aggfunc=lambda x: '✓', fill_value='')
        st.subheader("OEM-matrix per contactpersoon")
        st.dataframe(matrix)

        # ➕ Aantal unieke OEM’s
        unieke_oems = df_filtered['OEM'].nunique()
        st.markdown(f"**Aantal unieke OEM's voor {selected_company}:** {unieke_oems}")

        # Gedetailleerde tabel (alle rijen)
        st.subheader("Contactpersonen en gekoppelde OEM's")
        st.dataframe(df_resultaat.reset_index(drop=True))