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
    st.header("Verzuimanalyse")

    # --- PERIODE FILTER ---
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", date.today() - timedelta(days=90))
    with col2:
        end_date = st.date_input("Einddatum", date.today())

    if start_date > end_date:
        st.warning("Startdatum kan niet na einddatum liggen.")
        st.stop()

    # --- Verloftypes ophalen ---
    df_leave_types = search_read(
        'hr.leave.type',
        fields=['id', 'name']
    )

    if df_leave_types is None or df_leave_types.empty:
        st.error("Kan verloftypes niet ophalen.")
        st.stop()

    # Mapping id -> naam
    leave_type_dict = dict(zip(df_leave_types['id'], df_leave_types['name']))

    # Default selectie: types met 'Sick' of 'Ziek' in naam
    default_verzuim = [id for id, name in leave_type_dict.items() if 'Sick' in name or 'Ziek' in name]

    selected_verzuim_types = st.multiselect(
        "Selecteer verloftypes die als verzuim gelden",
        options=df_leave_types['id'],
        format_func=lambda x: leave_type_dict.get(x, str(x)),
        default=default_verzuim
    )

    if not selected_verzuim_types:
        st.info("Selecteer minimaal één verloftype als verzuim.")
        st.stop()

    # --- Verzuimregistraties ophalen ---
    df_verzuim = search_read(
        'hr.leave',
        domain=[
            ('holiday_status_id', 'in', selected_verzuim_types),
            ('state', 'in', ['validate', 'confirm']),
            ('request_date_from', '<=', end_date.strftime('%Y-%m-%d')),
            ('request_date_to', '>=', start_date.strftime('%Y-%m-%d')),
        ],
        fields=[
            'employee_id',
            'holiday_status_id',
            'request_date_from',
            'request_date_to',
            'number_of_days',
            'state',
            'name'
        ]
    )

    if df_verzuim is None or df_verzuim.empty:
        st.info("Geen verzuimregistraties gevonden in de geselecteerde periode.")
        st.stop()

    # --- Data transformeren ---
    df_verzuim['Employee'] = df_verzuim['employee_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x))
    df_verzuim['Leave Type'] = df_verzuim['holiday_status_id'].apply(
        lambda x: leave_type_dict.get(x[0] if isinstance(x, list) else x, 'Onbekend'))
    df_verzuim['From'] = pd.to_datetime(df_verzuim['request_date_from'], errors='coerce')
    df_verzuim['To'] = pd.to_datetime(df_verzuim['request_date_to'], errors='coerce')
    df_verzuim['Days'] = df_verzuim['number_of_days']
    df_verzuim['Status'] = df_verzuim['state'].map({'confirm': 'Te bevestigen', 'validate': 'Goedgekeurd'}).fillna(
        df_verzuim['state'])

    # Filter op verloftype en status (optioneel)
    all_types = df_verzuim['Leave Type'].unique().tolist()
    # selected_types = st.multiselect("Filter op verloftype (optioneel)", options=all_types, default=all_types)

    all_statuses = df_verzuim['Status'].unique().tolist()
    # selected_statuses = st.multiselect("Filter op status (optioneel)", options=all_statuses, default=all_statuses)

    df_filtered = df_verzuim[
        df_verzuim['Leave Type'].isin(all_types) &
        df_verzuim['Status'].isin(all_statuses)
        ]

    # --- Resultaat tonen ---
    st.subheader("Verzuimregistraties")
    st.dataframe(
        df_filtered[['Employee', 'Leave Type', 'From', 'To', 'Days', 'Status']].sort_values(by='From').reset_index(
            drop=True))

    # --- Samenvatting per werknemer ---
    st.subheader("Verzuim per medewerker")
    verzuim_per_medewerker = df_filtered.groupby('Employee')['Days'].sum().reset_index().sort_values(by='Days',
                                                                                                     ascending=False)
    st.bar_chart(verzuim_per_medewerker.rename(columns={'Days': 'Aantal dagen verzuim'}).set_index('Employee'))