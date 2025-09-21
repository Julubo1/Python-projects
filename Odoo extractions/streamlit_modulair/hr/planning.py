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
    st.header("Planning Overzicht")

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
        df_planning = search_read(
            'planning.slot',
            domain=[
                ('start_datetime', '>=', start_date.strftime('%Y-%m-%d 00:00:00')),
                ('end_datetime', '<=', end_date.strftime('%Y-%m-%d 23:59:59'))
            ],
            fields=[
                'employee_id',
                'role_id',
                'start_datetime',
                'end_datetime',
                'allocated_hours',
                'state'
            ],
            context={'lang': 'en_GB'}
        )

        if not df_planning.empty:
            # --- TRANSFORMATIE ---
            # --- TRANSFORMATIE ---
            df_planning['Employee'] = df_planning['employee_id'].apply(
                lambda x: x[1] if isinstance(x, list) else str(x))

            def normalize_role(role):
                if not role:
                    return None
                name = role[1] if isinstance(role, list) else str(role)
                if name.lower() in ["office", "office & opening", "office & closing"]:
                    return "Office"
                return name

            df_planning['Role'] = df_planning['role_id'].apply(normalize_role)
            df_planning['Start'] = pd.to_datetime(df_planning['start_datetime'], errors='coerce')
            df_planning['End'] = pd.to_datetime(df_planning['end_datetime'], errors='coerce')
            df_planning['Hours'] = df_planning['allocated_hours']

            # --- FILTERS ---
            all_roles = df_planning['Role'].dropna().unique().tolist()
            selected_roles = st.multiselect("Filter op rol", options=all_roles, default=all_roles)

            df_planning = df_planning[df_planning['Role'].isin(selected_roles)]

            # --- AGGREGATIE PER DAG EN ROL ---
            st.subheader("Aantal medewerkers per dag per rol")

            df_agg = df_planning.copy()
            df_agg['Date'] = df_agg['Start'].dt.date  # Alleen de datum, geen tijd
            agg_table = df_agg.groupby(['Date', 'Role']).size().unstack(fill_value=0)

            st.dataframe(agg_table.style.format(na_rep="-"), use_container_width=True)

            # --- TABEL ---
            st.subheader("Planning Tabel")
            st.dataframe(
                df_planning[['Employee', 'Role', 'Start', 'End', 'Hours', 'state']]
                .sort_values(by='Start')
                .reset_index(drop=True)
            )

            # --- GANTT GRAFIEK ---
            st.subheader("Planning Gantt Chart")

            import plotly.express as px

            fig = px.timeline(
                df_planning,
                x_start="Start",
                x_end="End",
                y="Employee",
                color="Role",
                hover_data=["Hours", "state"],
                title="Planningsoverzicht per medewerker"
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=600, margin=dict(t=30, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Geen geplande medewerkers gevonden in de geselecteerde periode.")