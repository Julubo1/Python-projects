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
    st.title("Contactpersonen in Odoo met OEM")

    # contact_mapping omzetten naar DataFrame
    df_oem = pd.DataFrame(contact_mapping.items(), columns=['oem_id', 'oem_name']).set_index('oem_id')

    # Contactpersonen ophalen met OEM ids
    df_contacts = search_read(
        'res.partner',
        domain=[('x_oem_vendor_ids', '!=', False)],
        fields=['id', 'name', 'x_studio_contactperson_for', 'parent_id'],
        context={'lang': 'en_GB'}
    )

    if df_contacts.empty:
        st.warning("Geen contactpersonen met OEM gevonden.")
        st.stop()

    # OEM ID's exploderen
    df_contacts = df_contacts.explode('x_studio_contactperson_for')
    df_contacts = df_contacts[df_contacts['x_studio_contactperson_for'].notna()]

    # OEM naam toevoegen
    df_contacts['oem_name'] = df_contacts['x_studio_contactperson_for'].map(df_oem['oem_name'])

    # Contactpersoon ID & Bedrijf ID groeperen per OEM
    oem_contact_counts = df_contacts.groupby('oem_name')['id'].nunique()
    oem_company_counts = df_contacts.groupby('oem_name')['parent_id'].apply(
        lambda x: x.dropna().apply(lambda v: v[0] if isinstance(v, (list, tuple)) else v).nunique()
    )

    # Combineer in één DataFrame
    oem_counts = pd.DataFrame({
        'Aantal Contactpersons': oem_contact_counts,
        'Unieke Companies': oem_company_counts
    }).reset_index().rename(columns={'oem_name': 'OEM'})

    st.subheader("Aantal contactpersons per OEM")
    st.dataframe(oem_counts)

    # Dropdown voor OEM selectie
    selected_oem = st.selectbox("Selecteer OEM", options=oem_counts['OEM'].tolist())

    if selected_oem:
        contacts_filtered = df_contacts[df_contacts['oem_name'] == selected_oem][['name', 'parent_id']].copy()

        def extract_name(val):
            if isinstance(val, (list, tuple)) and len(val) > 1:
                return val[1]
            elif isinstance(val, dict) and 'name' in val:
                return val['name']
            elif pd.isna(val):
                return ''
            else:
                return str(val)

        contacts_filtered['Company'] = contacts_filtered['parent_id'].apply(extract_name)
        contacts_filtered = contacts_filtered.drop(columns=['parent_id'])

        # Toon contactpersonen
        st.subheader(f"Contactspersons voor {selected_oem}")
        st.dataframe(
            contacts_filtered.rename(columns={'name': 'Contact'}).reset_index(drop=True)
        )

        # Nieuw: checkbox voor bedrijven tonen
        if st.checkbox(f"Toon bedrijven voor {selected_oem}"):
            bedrijven = contacts_filtered['Company'].dropna().unique()
            df_bedrijven = pd.DataFrame({'Bedrijf': bedrijven})
            st.subheader(f"Unieke bedrijven met contacten voor {selected_oem}")
            st.dataframe(df_bedrijven)