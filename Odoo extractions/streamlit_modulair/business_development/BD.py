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
    st.title("Business Development Monitor")

    # --- Filters ---
    today = pd.to_datetime("today")
    date_range = st.date_input("Selecteer datumrange", [today - pd.Timedelta(days=30), today])
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

    # --- Team filter (optioneel) ---
    df_users = search_read('res.users', fields=['id', 'name'])
    df_users = pd.DataFrame(df_users)
    user_map = dict(zip(df_users['id'], df_users['name']))
    selected_user = st.selectbox("Filter op gebruiker (optioneel)", options=["Alle"] + df_users['name'].tolist())
    selected_user_ids = [uid for uid, name in user_map.items() if
                         name == selected_user] if selected_user != "Alle" else None

    # --- Filter op is_company ---
    company_filter = st.selectbox("Toon", options=["Alle", "Alleen Bedrijven", "Alleen Personen"])

    # --- Nieuwe contacten ---
    st.subheader("Nieuwe Contacten")
    domain_contacts = [('create_date', '>=', str(start_date)), ('create_date', '<=', str(end_date))]
    if selected_user_ids:
        domain_contacts.append(('create_uid', '=', selected_user_ids[0]))
    if company_filter == "Alleen Bedrijven":
        domain_contacts.append(('is_company', '=', True))
    elif company_filter == "Alleen Personen":
        domain_contacts.append(('is_company', '=', False))

    df_contacts = search_read(
        'res.partner',
        domain=domain_contacts,
        fields=['id', 'name', 'create_date', 'create_uid', 'industry_id', 'parent_id', 'is_company'],
        context={'lang': 'en_GB'}
    )
    df_contacts = pd.DataFrame(df_contacts)
    if not df_contacts.empty:
        df_contacts['create_date'] = pd.to_datetime(df_contacts['create_date'])
        df_contacts['parent_id'] = df_contacts['parent_id'].apply(
            lambda x: x[1] if isinstance(x, list) else 'Onbekend')
        df_contacts['industry_id'] = df_contacts['industry_id'].apply(
            lambda x: x[1] if isinstance(x, list) else 'Onbekend')
        df_contacts['create_by'] = df_contacts['create_uid'].apply(
            lambda x: x[1] if isinstance(x, list) else 'Onbekend')
        st.dataframe(df_contacts[['name', 'parent_id', 'industry_id', 'create_by', 'create_date']].rename(
            columns={'name': 'Contact'}))
        st.markdown(f"**Totaal nieuwe contacten:** {len(df_contacts)}")
    else:
        st.info("Geen nieuwe contacten in deze periode.")

    # --- Nieuwe Leads ---
    st.subheader("Nieuwe Leads")
    domain_leads = [('type', '=', 'lead'), ('create_date', '>=', str(start_date)), ('create_date', '<=', str(end_date))]
    if selected_user_ids:
        domain_leads.append(('user_id', '=', selected_user_ids[0]))

    df_leads = search_read(
        'crm.lead',
        domain=domain_leads,
        fields=['name', 'create_date', 'user_id', 'stage_id'],
        context={'lang': 'en_GB'}
    )
    df_leads = pd.DataFrame(df_leads)
    if not df_leads.empty:
        df_leads['create_date'] = pd.to_datetime(df_leads['create_date'])
        df_leads['aangemaakt_door'] = df_leads['user_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')
        df_leads['stage'] = df_leads['stage_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')
        st.dataframe(df_leads[['name', 'aangemaakt_door', 'create_date', 'stage']].rename(columns={'name': 'Lead'}))
        st.markdown(f"**Totaal nieuwe leads:** {len(df_leads)}")
    else:
        st.info("Geen nieuwe leads in deze periode.")