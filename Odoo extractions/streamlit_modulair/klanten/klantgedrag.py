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

from shared.core import safe_get_currency_id, search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping,get_label, extract_country_name
def show():
    st.title(f"Klantgedrag & Loyaliteit")

    # --- Stap 1: Verkooporders ophalen (alle jaren) ---
    df_orders_all = search_read(
        'sale.order',
        domain=[('state', 'in', ['sale', 'done']), ('partner_id.is_company', '=', True)],
        fields=['partner_id', 'amount_total', 'date_order', 'currency_id'],
    )

    if df_orders_all.empty:
        st.info("Geen verkooporders gevonden.")
    else:
        # --- Wisselkoersen ophalen ---
        currency_rates = search_read('res.currency.rate', fields=['name', 'currency_id', 'rate'])

        # --- Data opschonen ---
        df_orders_all['partner_name'] = df_orders_all['partner_id'].apply(
            lambda x: x[1] if isinstance(x, list) and len(x) == 2 else 'Onbekend')
        # Specifieke bedrijven uitsluiten
        bedrijven_uitsluiten = ['PEO B.V.', 'PEO B.V. (B)']
        df_orders_all = df_orders_all[~df_orders_all['partner_name'].isin(bedrijven_uitsluiten)]

        df_orders_all['date_order'] = pd.to_datetime(df_orders_all['date_order'])

        # --- Valutaconversie naar EUR ---
        def safe_get_currency_id(row):
            if isinstance(row['currency_id'], list) and len(row['currency_id']) == 2:
                return row['currency_id'][0]
            return None

        df_orders_all['currency_id_clean'] = df_orders_all.apply(safe_get_currency_id, axis=1)
        df_orders_all['euro_amount'] = df_orders_all.apply(
            lambda row: row['amount_total'] * get_exchange_rate(currency_rates, row['currency_id_clean'],
                                                                row['date_order']),
            axis=1
        )

        if df_orders_all.empty:
            st.info(f"Geen verkooporders gevonden.")
        else:
            # --- RFM-analyse (alleen klanten van dit jaar) ---
            rfm = df_orders_all.groupby('partner_name').agg({
                'date_order': [lambda x: (df_orders_all['date_order'].max() - x.max()).days,  # Recency
                               'count'],  # Frequency
                'euro_amount': 'sum'  # Monetary
            }).reset_index()

            rfm.columns = ['Klant', 'Recency (dagen)', 'Aantal orders', 'Totaalbedrag (EUR)']
            rfm['Gemiddelde orderwaarde (EUR)'] = rfm['Totaalbedrag (EUR)'] / rfm['Aantal orders']
            rfm['Totaalbedrag (EUR)'] = rfm['Totaalbedrag (EUR)'].round(2)
            rfm['Gemiddelde orderwaarde (EUR)'] = rfm['Gemiddelde orderwaarde (EUR)'].round(2)

            st.subheader("Klantgedragsoverzicht")
            st.dataframe(rfm.sort_values("Totaalbedrag (EUR)", ascending=False).reset_index(drop=True))

            # --- Gemiddelde tijd tussen orders ---
            st.subheader("Gemiddelde tijd tussen orders")
            df_sorted = df_orders_all.sort_values(['partner_name', 'date_order'])
            df_sorted['days_between_orders'] = df_sorted.groupby('partner_name')['date_order'].diff().dt.days

            avg_days = df_sorted.groupby('partner_name')['days_between_orders'].mean().dropna().reset_index()
            avg_days.columns = ['Klant', 'Gem. dagen tussen orders']
            avg_days['Gem. dagen tussen orders'] = avg_days['Gem. dagen tussen orders'].round(1)

            # Toon alleen klanten die in dit jaar actief waren
            klanten_in_jaar = df_orders_all['partner_name'].unique()
            avg_days = avg_days[avg_days['Klant'].isin(klanten_in_jaar)]

            st.dataframe(avg_days.sort_values('Gem. dagen tussen orders'))

            # --- RFM visualisatie ---
            st.subheader(f"RFM Verdeling")
            import plotly.express as px

            fig = px.scatter(
                rfm,
                x='Aantal orders',
                y='Totaalbedrag (EUR)',
                size='Gemiddelde orderwaarde (EUR)',
                color='Recency (dagen)',
                hover_name='Klant',
                title="RFM Klantsegmentatie",
                color_continuous_scale='Bluered_r'
            )
            st.plotly_chart(fig, use_container_width=True)