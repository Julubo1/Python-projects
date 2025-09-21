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
    st.title("Backorder-analyse (Open Leveringen)")

    df_transfers = search_read(
        'stock.picking',
        domain=[('state', 'not in', ['done', 'cancel'])],
        fields=['name', 'origin', 'scheduled_date', 'state', 'partner_id', 'picking_type_code'],
        context={'lang': 'en_GB'}
    )

    if df_transfers.empty:
        st.success("Geen openstaande leveringen gevonden.")
    else:
        df_transfers['scheduled_date'] = pd.to_datetime(df_transfers['scheduled_date'], errors='coerce')
        df_transfers['partner'] = df_transfers['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
        df_transfers['dagen_achter'] = (pd.Timestamp.today().normalize() - df_transfers['scheduled_date']).dt.days
        df_transfers['dagen_achter'] = df_transfers['dagen_achter'].fillna(0).astype(int)

        # Filter op type OUT only
        picking_types = df_transfers['picking_type_code'].dropna().unique().tolist()
        gekozen_type = st.selectbox("Filter op Picking Type", ["ALL"] + picking_types)
        if gekozen_type != "ALL":
            df_transfers = df_transfers[df_transfers['picking_type_code'] == gekozen_type]

        st.metric("Aantal openstaande transfers", len(df_transfers))

        # Overzicht per status
        status_counts = df_transfers['state'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Aantal']
        st.subheader("Aantal open transfers per status")
        st.dataframe(status_counts)

        # Backorders ouder dan X dagen
        grens_dagen = st.slider("Toon alleen leveringen ouder dan X dagen", 0, 90, 14)
        vertraagd = df_transfers[df_transfers['dagen_achter'] > grens_dagen]

        st.subheader(f"Vertraagde leveringen (> {grens_dagen} dagen na geplande datum)")
        st.dataframe(vertraagd[['name', 'origin', 'partner', 'scheduled_date', 'state', 'dagen_achter']].sort_values(
            'dagen_achter', ascending=False))