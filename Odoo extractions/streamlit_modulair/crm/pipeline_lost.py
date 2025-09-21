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

from shared.core import search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping
def show():
    st.title("Pipeline Lost Analyse")

    # Datumfilter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", value=datetime.today().replace(day=1))
    with col2:
        end_date = st.date_input("Einddatum", value=datetime.today())

    if start_date > end_date:
        st.error("Startdatum mag niet na einddatum liggen.")
        st.stop()

    df_opportunities = search_read(
        'crm.lead',
        domain=[('type', '=', 'opportunity'), ('active', 'in', [True, False]), ('stage_id', '!=', 4)],
        fields=[
            'id', 'active', 'name', 'user_id', 'stage_id', 'lost_reason', 'date_closed', 'date_last_stage_update',
            'company_id', 'country_id', 'expected_revenue', 'probability', 'x_studio_result_responsable', 'partner_id'
        ],
        context={'lang': 'en_GB'}
    )

    if df_opportunities.empty:
        st.warning("Geen opportunities gevonden.")
        st.stop()

    # Zet date_closed om naar datetime.date
    df_opportunities['date_closed'] = pd.to_datetime(df_opportunities['date_closed'], errors='coerce').dt.date

    # Filter op datumrange voor date_closed
    df_opportunities = df_opportunities[
        (df_opportunities['date_closed'] >= start_date) & (df_opportunities['date_closed'] <= end_date)
        ]

    df_lost = df_opportunities[df_opportunities['lost_reason'].notnull()]

    if df_lost.empty:
        st.info(f"Geen verloren opportunities gevonden tussen {start_date} en {end_date}.")
    else:
        def get_label(val):
            if isinstance(val, list) and len(val) == 2:
                return val[1]
            elif isinstance(val, dict) and 'name' in val:
                return val['name']
            elif val is None:
                return 'Onbekend'
            else:
                return str(val)

        lost_reason_counts = df_lost['lost_reason'].apply(get_label).value_counts().reset_index()
        lost_reason_counts.columns = ['Reden', 'Aantal verloren']
        fig1 = px.bar(lost_reason_counts, x='Reden', y='Aantal verloren', title='Verliesredenen',
                      text='Aantal verloren')
        fig1.update_traces(textposition='outside')
        st.plotly_chart(fig1, use_container_width=True)

        # Maak opgeschoonde Fase aan
        df_lost['Fase'] = df_lost['stage_id'].apply(get_label).str.strip().str.lower()

        lost_stage_counts = df_lost['Fase'].value_counts().reset_index()
        lost_stage_counts.columns = ['Fase', 'Aantal verloren']

        st.write(lost_stage_counts)

        fig2 = px.bar(
            lost_stage_counts, x='Fase', y='Aantal verloren',
            title='Verlies per Fase',
            text=None
        )
        fig2.update_traces(
            hovertemplate='Fase: %{x}<br>Aantal verloren: %{y}<extra></extra>',
            textposition='outside'
        )
        st.plotly_chart(fig2, use_container_width=True)

        fases = sorted(lost_stage_counts['Fase'].unique())
        selected_fases = st.multiselect("Filter op Fase", options=fases, default=fases)

        df_filtered = df_lost[df_lost['Fase'].isin(selected_fases)].copy()

        df_filtered['Verliesreden'] = df_filtered['lost_reason'].apply(get_label)
        df_filtered['Opportunity'] = df_filtered['name']
        df_filtered['Result Responsible'] = df_filtered['x_studio_result_responsable'].apply(get_label)
        df_filtered['Customer'] = df_filtered['partner_id'].apply(get_label)

        st.markdown(f"**Aantal gefilterde verloren opportunities:** {len(df_filtered)}")

        st.dataframe(
            df_filtered[['Customer', 'Opportunity', 'Verliesreden', 'Result Responsible', 'date_closed', 'Fase']]
        )

        lost_user_counts = df_lost['x_studio_result_responsable'].apply(get_label).value_counts().reset_index()
        lost_user_counts.columns = ['Result Responsible', 'Aantal verloren']
        fig3 = px.bar(lost_user_counts, x='Result Responsible', y='Aantal verloren',
                      title='Verlies per Result Responsible',
                      text='Aantal verloren')
        fig3.update_traces(textposition='outside')
        st.plotly_chart(fig3, use_container_width=True)