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
    st.header("Helpdesk Overzicht")

    df_tickets = search_read(
        'helpdesk.ticket',
        domain=[],
        fields=[
            'id', 'name', 'create_date', 'close_date', 'team_id', 'user_id',
            'stage_id', 'priority', 'partner_id', 'write_date'
        ],
        context={'lang': 'nl_NL'}
    )

    df = pd.DataFrame(df_tickets)

    # Datums omzetten
    df['create_date'] = pd.to_datetime(df['create_date'], errors='coerce')
    df['close_date'] = pd.to_datetime(df['close_date'], errors='coerce')
    df['write_date'] = pd.to_datetime(df['write_date'], errors='coerce')

    # Stage-naam extraheren
    df['stage'] = df['stage_id'].apply(lambda x: x[1] if isinstance(x, (list, tuple)) else str(x))

    # Aparte tabel met 'Afgewezen door OEM'
    df_afgewezen = df[df['stage'].str.contains('afgewezen door oem', case=False, na=False)].copy()

    # Hoofdtabel zonder afgewezen tickets
    df = df[~df['stage'].str.contains('afgewezen door oem', case=False, na=False)].copy()

    # Extra kolommen
    df['opgelost'] = ~df['close_date'].isna()
    df['doorlooptijd'] = (df['close_date'] - df['create_date']).dt.days
    df['dagen_open'] = (pd.Timestamp.now() - df['create_date']).dt.days
    df['stagnatie'] = (pd.Timestamp.now() - df['write_date']).dt.days > 7

    # Filters
    teams = sorted(df['team_id'].dropna().astype(str).unique())
    selected_team = st.selectbox("Selecteer Team", ["Alle"] + teams)
    if selected_team != "Alle":
        df = df[df['team_id'].astype(str) == selected_team]
        df_afgewezen = df_afgewezen[df_afgewezen['team_id'].astype(str) == selected_team]

    # Verdeling
    df_open = df[df['opgelost'] == False].copy()
    df_closed = df[df['opgelost'] == True].copy()

    # KPI's
    col1, col2, col3 = st.columns(3)
    col1.metric("Open Tickets", len(df_open))
    col2.metric("Tickets met Stagnatie", df_open['stagnatie'].sum())
    col3.metric("Gem. Afhandelingstijd (d)", round(df_closed['doorlooptijd'].mean(), 1))

    # Tabellen
    st.subheader("Open Tickets")
    st.dataframe(df_open[['name', 'create_date', 'priority', 'stage', 'dagen_open', 'stagnatie']])

    st.subheader("Afgehandelde Tickets")
    st.dataframe(df_closed[['name', 'create_date', 'close_date', 'priority', 'stage', 'doorlooptijd']])

    st.subheader("Afgewezen door OEM")
    st.dataframe(df_afgewezen[['name', 'create_date', 'priority', 'stage', 'write_date']])