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
    st.title("Offertes & Orderstatus")

    # Dynamische datumfilter
    start_date = st.date_input("Startdatum", pd.to_datetime("2024-01-01"))
    end_date = st.date_input("Einddatum", pd.to_datetime("2024-12-31"))

    if start_date > end_date:
        st.error("Startdatum moet voor de einddatum liggen.")
    else:
        df_quotes = search_read(
            'sale.order',
            domain=[('state', 'in', ['draft', 'sent'])],
            fields=['name', 'partner_id', 'user_id', 'amount_total', 'date_order', 'validity_date', 'state',
                    'x_studio_result_responsable', 'amount_untaxed']
        )

    if df_quotes.empty:
        st.info("Geen openstaande offertes gevonden.")
    else:
        df_quotes = filter_on_date_range(df_quotes, 'date_order', start_date, end_date)
        if df_quotes.empty:
            st.warning(f"Geen offertes tussen {start_date} en {end_date}.")
        else:
            df_quotes['partner'] = df_quotes['partner_id'].apply(lambda x: x[1] if x else 'Onbekend')

            def get_name(x):
                if x is None or x is False:
                    return 'Onbekend'
                elif isinstance(x, (list, tuple)) and len(x) == 2:
                    return x[1]
                elif isinstance(x, str):
                    return x
                else:
                    return str(x)

            df_quotes = df_quotes[df_quotes['x_studio_result_responsable'].notnull() & (
                    df_quotes['x_studio_result_responsable'] != False)]
            df_quotes['Result Responsible'] = df_quotes['x_studio_result_responsable'].apply(get_name)
            df_quotes['validity_date'] = pd.to_datetime(df_quotes['validity_date']).dt.date

            today = datetime.now().date()

            # Geldige offertes
            valid_quotes = df_quotes[df_quotes['validity_date'] >= today].copy().sort_values('validity_date')
            # Verlopen offertes
            expired_quotes = df_quotes[df_quotes['validity_date'] < today].copy().sort_values('validity_date')

            st.subheader("Geldige offertes")
            st.dataframe(valid_quotes[
                             ['name', 'partner', 'Result Responsible', 'amount_total', 'date_order', 'validity_date',
                              'state']])

            st.subheader("Verlopen offertes")
            if expired_quotes.empty:
                st.write("Geen verlopen offertes.")
            else:
                st.dataframe(expired_quotes[['name', 'partner', 'Result Responsible', 'amount_total', 'date_order',
                                             'validity_date', 'state']])

            # Overzicht per business line
            df_sales = search_read(
                'sale.order',
                domain=[('state', 'in', ['draft', 'sent'])],
                fields=['name', 'date_order', 'team_id', 'amount_untaxed', 'state'],
                context={'lang': 'en_GB'}
            )

            if df_sales.empty:
                st.warning("Geen openstaande offertes gevonden.")
            else:
                df_sales['team_name'] = df_sales['team_id'].apply(
                    lambda x: x[1] if isinstance(x, list) and len(x) == 2 else 'Onbekend')
                quotes = df_sales[df_sales['state'].isin(['draft', 'sent'])]

                count_summary = quotes.groupby(['team_name', 'state']).size().unstack(fill_value=0).reset_index()
                amount_summary = quotes.groupby('team_name')['amount_untaxed'].sum().reset_index(
                    name='Total Amount Untaxed')

                quote_summary = pd.merge(count_summary, amount_summary, on='team_name', how='outer').fillna(0)
                quote_summary = quote_summary.rename(columns={
                    'team_name': 'Business Line',
                    'draft': 'Draft Count',
                    'sent': 'Sent Count'
                })
                quote_summary['Draft Count'] = quote_summary['Draft Count'].astype(int)
                quote_summary['Sent Count'] = quote_summary['Sent Count'].astype(int)

                total_row = pd.DataFrame([{
                    'Business Line': 'Totaal',
                    'Draft Count': quote_summary['Draft Count'].sum(),
                    'Sent Count': quote_summary['Sent Count'].sum(),
                    'Total Amount Untaxed': quote_summary['Total Amount Untaxed'].sum()
                }])

                quote_summary = pd.concat([quote_summary, total_row], ignore_index=True)
                quote_summary['Total Amount Untaxed'] = quote_summary['Total Amount Untaxed'].apply(
                    lambda x: f"€ {x:,.0f}".replace(',', '.'))

                st.subheader("Open Quotes Overview")
                st.dataframe(quote_summary)
