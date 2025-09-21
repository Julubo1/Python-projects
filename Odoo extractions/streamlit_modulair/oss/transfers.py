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
    st.header("Transfers Overview")

    df_transfers = search_read(
        'stock.picking',
        domain=[],
        fields=[
            'id', 'name', 'location_id', 'location_dest_id', 'partner_id', 'scheduled_date', 'origin', 'date_done',
            'company_id', 'move_type', 'state'
        ],
        context={'lang': 'en_GB'})

    if not df_transfers.empty:
        # Datumvelden voorbereiden
        df_transfers['date_done'] = pd.to_datetime(df_transfers['date_done'], errors='coerce')
        df_transfers['scheduled_date'] = pd.to_datetime(df_transfers['scheduled_date'], errors='coerce')
        df_transfers['week_done'] = df_transfers['date_done'].dt.isocalendar().week
        df_transfers['year_done'] = df_transfers['date_done'].dt.year
        df_transfers['week_scheduled'] = df_transfers['scheduled_date'].dt.isocalendar().week
        df_transfers['year_scheduled'] = df_transfers['scheduled_date'].dt.year
        today = pd.to_datetime(pd.Timestamp.today().date())

        filter_type = st.selectbox("Filter op type (IN, OUT, DS)", options=["Alle", "IN", "OUT", "DS"], index=0)


        def filter_by_name(df):
            if filter_type == "Alle":
                return df
            else:
                return df[df['name'].str.upper().str.contains(filter_type)]

        # -------- VOLTOOID --------
        st.subheader("Finished Transfers")
        date_range_done = st.date_input("Datumrange (finished)", value=[today, today])

        done_transfers = filter_by_name(df_transfers[df_transfers['date_done'].notna()].copy())



        if date_range_done:
            start, end = date_range_done
            done_transfers = done_transfers[
                (done_transfers['date_done'] >= pd.to_datetime(start)) &
                (done_transfers['date_done'] <= pd.to_datetime(end))
            ]
            done_transfers = done_transfers.astype(str)

        st.dataframe(done_transfers)
        st.markdown(f"**Aantal Finished Transfers in range:** {len(done_transfers)}")

        # -------- TOEKOMSTIGE --------
        st.subheader("Planned Transfers")
        date_range_scheduled = st.date_input("Datumrange (planned)", value=[today, today])

        future_transfers = filter_by_name(df_transfers[
            (df_transfers['scheduled_date'] >= pd.to_datetime('today')) &
            (df_transfers['state'] != 'cancel') & (df_transfers['state'] != 'done')
            ])


        if date_range_scheduled:
            start, end = date_range_scheduled
            future_transfers = future_transfers[
                (future_transfers['scheduled_date'] >= pd.to_datetime(start)) &
                (future_transfers['scheduled_date'] <= pd.to_datetime(end))
            ]
            future_transfers = future_transfers.astype(str)
        st.dataframe(future_transfers)
        st.markdown(f"**Aantal Planned Transfers in range:** {len(future_transfers)}")

        # -------- OVERDUE --------
        st.subheader("Overdue Transfers")
        overdue_transfers = filter_by_name(df_transfers[
                                               (df_transfers['scheduled_date'] < pd.to_datetime('today')) &
                                               (df_transfers['date_done'].isna()) &
                                               (df_transfers['state'] != 'cancel') &
                                               (df_transfers['state'] != 'done')
                                               ])

        overdue_transfers = overdue_transfers.astype(str)
        st.dataframe(overdue_transfers)
        st.markdown(f"**Aantal Overdue Transfers:** {len(overdue_transfers)}")
