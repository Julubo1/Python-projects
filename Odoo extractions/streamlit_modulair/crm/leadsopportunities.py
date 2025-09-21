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

from shared.core import (search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping)
def show():
    st.header("Leads & Opportunities Analyse")

    # Data ophalen
    df_leads = search_read(
        'crm.lead',
        domain=[],
        fields=['type', 'team_id', 'stage_id', 'expected_revenue'],
        context={'lang': 'en_GB'}

    )

    if df_leads.empty:
        st.warning("Geen leads of opportunities gevonden.")
    else:
        # Extract 'team_name' uit Many2one veld
        df_leads['team_name'] = df_leads['team_id'].apply(
            lambda x: x[1] if isinstance(x, list) and len(x) == 2 else 'Onbekend')

        # Extract 'stage_id_val' voor filtering
        df_leads['stage_id_val'] = df_leads['stage_id'].apply(
            lambda x: x[0] if isinstance(x, list) and len(x) == 2 else None)

        # Splits data
        WON_STAGE_ID=4
        leads = df_leads[df_leads['type'] == 'lead']
        opps = df_leads[(df_leads['type'] == 'opportunity') & (df_leads['stage_id_val'] != WON_STAGE_ID)]

        # Leads en open opps per team
        leads_per_team = leads.groupby('team_name').size().reset_index(name='Leads')
        opps_per_team = opps.groupby('team_name').size().reset_index(name='Open Opportunities')
        revenue_per_team = opps.groupby('team_name')['expected_revenue'].sum().reset_index(name='Expected Revenue')

        summary = pd.merge(leads_per_team, opps_per_team, on='team_name', how='outer')
        summary = pd.merge(summary, revenue_per_team, on='team_name', how='outer').fillna(0)
        summary = summary.rename(columns={'team_name': 'Business Line'})

        # Zorg dat counts integers zijn
        summary['Leads'] = summary['Leads'].astype(int)
        summary['Open Opportunities'] = summary['Open Opportunities'].astype(int)

        total_row = pd.DataFrame([{
            'Business Line': 'Totaal',
            'Leads': summary['Leads'].sum(),
            'Open Opportunities': summary['Open Opportunities'].sum(),
            'Expected Revenue': summary['Expected Revenue'].sum()
        }])

        summary = pd.concat([summary, total_row], ignore_index=True)

        # Format currency
        summary['Expected Revenue'] = summary['Expected Revenue'].apply(lambda x: f"€ {x:,.0f}".replace(',', '.'))

        st.write(summary.style.apply(
            lambda row: ['font-weight: bold; background-color: #e8e8e8; color: black;' if row[
                                                                                              'Business Line'] == 'Totaal' else ''
                         for _ in row],
            axis=1
        ))