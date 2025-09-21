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
    st.header("Weekly Leads & Opportunities")

    # Data ophalen
    df_leads = search_read(
        'crm.lead',
        domain=[],
        fields=[
            'type', 'name', 'team_id', 'stage_id', 'expected_revenue',
            'create_date', 'quotation_count', 'order_ids'  # order_ids is m2m met sale.order
        ],
        context={'lang': 'en_GB'}
    )

    df_leads['create_date'] = pd.to_datetime(df_leads['create_date'])
    df_leads['year'] = df_leads['create_date'].dt.year
    df_leads['week'] = df_leads['create_date'].dt.isocalendar().week

    df_leads['team_name'] = df_leads['team_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')
    df_leads['stage_name'] = df_leads['stage_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')

    # Heeft offerte?
    df_leads['Heeft Offerte'] = df_leads['quotation_count'] > 0

    # Jaarfilter via jaarkiezer
    jaren = [2022, 2023, 2024, 2025, 2026]
    jaarkiezer = st.selectbox("Selecteer jaar:", options=jaren, index=len(jaren) - 1 if jaren else 0)
    if jaarkiezer:
        df_leads = df_leads[df_leads['year'] == jaarkiezer]

    # Weekfilter
    beschikbare_weken = sorted(df_leads['week'].unique())
    geselecteerde_week = st.selectbox("Selecteer week:", options=["Alle"] + list(beschikbare_weken))

    beschikbare_stages = sorted(df_leads['stage_name'].dropna().unique())
    geselecteerde_stages = st.multiselect("Filter op Stage:", options=beschikbare_stages, default=beschikbare_stages)

    df_leads = df_leads[df_leads['stage_name'].isin(geselecteerde_stages)]

    if geselecteerde_week != "Alle":
        df_leads = df_leads[df_leads['week'] == geselecteerde_week]

    # Alleen leads
    leads = df_leads

    # Teamnaam extraheren uit many2one
    leads['team_name'] = leads['team_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) == 2 else 'Onbekend')

    # Groeperen per team
    leads_per_team = leads.groupby('team_name').size().reset_index(name='Aantal Leads')

    # Sorteer eventueel op aantal
    leads_per_team = leads_per_team.sort_values(by='Aantal Leads', ascending=False)

    st.subheader("Aantal Inkomende Leads per Team")
    st.dataframe(leads_per_team, use_container_width=True)

    fig = px.bar(
        leads_per_team,
        x='team_name',
        y='Aantal Leads',
        title='Aantal Leads per Team',
        labels={'team_name': 'Team', 'Aantal Leads': 'Aantal Leads'},
        color='Aantal Leads',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Details per Lead / Opportunity in Geselecteerde Week")

    kolommen = [
        'team_name', 'type', 'name', 'stage_name',
        'expected_revenue', 'create_date'
    ]

    # Alleen relevante kolommen
    df_display = df_leads[kolommen].copy()

    # Herbenoemen voor nettere weergave
    df_display = df_display.rename(columns={
        'team_name': 'Team',
        'type': 'Type',
        'name': 'Naam',
        'stage_name': 'Stage',
        'expected_revenue': 'Expected Revenue (€)',
        'create_date': 'Binnengekomen op:'
    })

    # Sorteer eventueel
    df_display = df_display.sort_values(by='Team')

    st.dataframe(df_display, use_container_width=True)