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
    st.title(f"Klantkwaliteit & Segmentatie")

    # Stap 1: Klantgegevens ophalen
    df_customers = search_read(
        'res.partner',
        domain=[('customer_rank', '>', 0)],
        fields=['name', 'country_id', 'email', 'phone', 'industry_id', 'sale_order_count', 'currency_id']
    )
    currency_rates = search_read(
        'res.currency.rate',
        fields=['name', 'currency_id', 'rate']
    )
    df_eur = search_read('res.currency', domain=[('name', '=', 'EUR')], fields=['id'])
    eur_id = df_eur.iloc[0]['id'] if not df_eur.empty else None

    if df_customers.empty:
        st.info("Geen klanten gevonden.")
    else:
        # Data voorbereiden
        df_customers['industry'] = df_customers['industry_id'].apply(lambda x: x[1] if x else 'Onbekend')
        df_customers['country_name'] = df_customers['country_id'].apply(
            lambda x: x[1] if isinstance(x, list) and len(x) == 2 else 'Onbekend')

        # Pie chart klanten per land
        country_counts = df_customers.groupby('country_name').size().reset_index(name='aantal')
        fig4 = px.pie(country_counts, values='aantal', names='country_name', title='Klanten per land')
        st.plotly_chart(fig4, use_container_width=True)

        # Filters toepassen
        excluded_names = ['PEO B.V. (B)', 'PEO B.V.']
        filtered_customers = df_customers[~df_customers['name'].isin(excluded_names)]

        # Top 10 klanten op aantal orders
        st.subheader("Top 10 klanten op basis van aantal orders")
        top_klanten = filtered_customers.sort_values('sale_order_count', ascending=False).head(10)
        st.dataframe(top_klanten[['name', 'industry', 'sale_order_count']])

        # Datumfilter: selecteer periode
        st.subheader("Selecteer periode voor orderdata")
        date_range = st.date_input("Periode (start - eind)",
                                   value=[pd.to_datetime('2023-01-01'), pd.to_datetime('2023-12-31')],
                                   key="order_date_filter")
        if len(date_range) != 2:
            st.error("Selecteer een start- en einddatum.")
            st.stop()

        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

        # Stap 2: Aanvullende data ophalen voor totaalbedrag per klant
        df_orders = search_read(
            'sale.order',
            domain=[('state', 'in', ['sale', 'done'])],
            fields=['partner_id', 'amount_total', 'date_order', 'currency_id']
        )

        if not df_orders.empty:
            # Datumkolom omzetten naar datetime
            df_orders['date_order'] = pd.to_datetime(df_orders['date_order'], errors='coerce')
            # Filter op geselecteerde datumrange
            df_orders = df_orders[(df_orders['date_order'] >= start_date) & (df_orders['date_order'] <= end_date)]

            # Partnernaam extraheren
            df_orders['partner_name'] = df_orders['partner_id'].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) == 2 else 'Onbekend'
            )
            df_orders['euro_amount'] = df_orders.apply(
                lambda row: row['amount_total'] * get_exchange_rate(currency_rates, row['currency_id'][0],
                                                                    row['date_order']),
                axis=1
            )

            # Zelfde filtering op partnernamen
            df_orders = df_orders[~df_orders['partner_name'].isin(excluded_names)]

            # Totaalbedrag per klant berekenen in euro's
            df_top_amount = df_orders.groupby('partner_name', as_index=False)['euro_amount'].sum()
            df_top_amount = df_top_amount.sort_values('euro_amount', ascending=False).head(10)
            df_top_amount['euro_amount'] = df_top_amount['euro_amount'].apply(
                lambda x: f"€ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            )

            st.subheader("Top 10 klanten op basis van totaal orderbedrag (in EUR)")
            st.dataframe(df_top_amount.rename(columns={
                'partner_name': 'Klant',
                'euro_amount': 'Totaalbedrag (EUR)'
            }))
