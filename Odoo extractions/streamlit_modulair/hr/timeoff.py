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

from shared.core import format_euro,extract_payment_days,search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping,get_label, extract_country_name
def show():
    st.header("Time Off Overview")

    # --- FILTER PERIODE ---
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", pd.to_datetime("today") - pd.Timedelta(days=7))
    with col2:
        end_date = st.date_input("Einddatum", pd.to_datetime("today") + pd.Timedelta(days=14))

    if start_date > end_date:
        st.warning("Startdatum kan niet na de einddatum liggen.")
    else:
        # --- DATA OPHALEN ---
        df_timeoff = search_read(
            'hr.leave',
            domain=[
                ('state', 'in', ['validate', 'confirm']),
                ('request_date_to', '>=', start_date.strftime('%Y-%m-%d')),
                ('request_date_from', '<=', end_date.strftime('%Y-%m-%d'))
            ],
            fields=[
                'employee_id',
                'holiday_status_id',
                'request_date_from',
                'request_date_to',
                'number_of_days',
                'state',
                'name'
            ],
            context={'lang': 'en_GB'}
        )

        if not df_timeoff.empty:
            # --- TRANSFORMATIE ---
            df_timeoff['Employee'] = df_timeoff['employee_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x))
            df_timeoff['Leave Type'] = df_timeoff['holiday_status_id'].apply(
                lambda x: x[1] if isinstance(x, list) else str(x))
            df_timeoff['From'] = pd.to_datetime(df_timeoff['request_date_from'], errors='coerce')
            df_timeoff['To'] = pd.to_datetime(df_timeoff['request_date_to'], errors='coerce')
            df_timeoff['Days'] = df_timeoff['number_of_days']
            df_timeoff['Status'] = df_timeoff['state'].map({
                'confirm': 'Te bevestigen',
                'validate': 'Goedgekeurd'
            }).fillna(df_timeoff['state'])

            # --- FILTER OP TYPE ---
            all_types = df_timeoff['Leave Type'].dropna().unique().tolist()
            selected_types = st.multiselect("Filter op verloftype", options=all_types, default=all_types)

            # --- FILTER OP STATUS ---
            all_statuses = df_timeoff['Status'].dropna().unique().tolist()
            selected_statuses = st.multiselect("Filter op status", options=all_statuses, default=all_statuses)

            df_timeoff = df_timeoff[
                df_timeoff['Leave Type'].isin(selected_types) &
                df_timeoff['Status'].isin(selected_statuses)
                ]

            # --- TABEL ---
            st.subheader("📋 Time Off Tabel")
            st.dataframe(
                df_timeoff[['Employee', 'Leave Type', 'From', 'To', 'Days', 'Status']]
                .sort_values(by='From')
                .reset_index(drop=True)
            )

            # --- GANTT KALENDER ---
            st.subheader("📅 Verlofkalender")
            import plotly.express as px

            fig = px.timeline(
                df_timeoff,
                x_start="From",
                x_end="To",
                y="Employee",
                color="Leave Type",
                hover_data=["Days", "Status"],
                title="Time Off Planning"
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=600, margin=dict(t=30, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Geen verlofaanvragen gevonden voor de geselecteerde periode.")
