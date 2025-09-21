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
    st.title("OSS Controle: Verschil tussen besteld en geleverd")

    # Datumfilter toevoegen (periode)
    date_range = st.date_input("Selecteer periode (bestellingen):",
                               value=[pd.Timestamp.today() - pd.Timedelta(days=30), pd.Timestamp.today()])
    if len(date_range) != 2:
        st.warning("Selecteer een start- en einddatum.")
        st.stop()
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

    # 1. Verkooporders ophalen met filtering op datum
    df_sales = search_read(
        'sale.order',
        domain=[('state', 'in', ['sale']), ('date_order', '>=', start_date.strftime('%Y-%m-%d')),
                ('date_order', '<=', end_date.strftime('%Y-%m-%d'))],
        fields=['id', 'name', 'date_order'],
        context={'lang': 'en_GB'}
    )
    sales_ids = df_sales['id'].tolist()

    # Als er geen sales zijn, melden en stoppen
    if not sales_ids:
        st.info("Geen verkooporders gevonden binnen geselecteerde periode.")
    else:
        df_sale_order_lines = search_read(
            'sale.order.line',
            domain=[('order_id', 'in', sales_ids)],
            fields=['order_id', 'product_id', 'product_uom_qty', 'qty_delivered'],
            context={'lang': 'en_GB'}
        )

        if not df_sale_order_lines.empty:
            df_sale_order_lines['order_id'] = df_sale_order_lines['order_id'].apply(
                lambda x: x[1] if isinstance(x, list) else x)
            df_sale_order_lines['product_id'] = df_sale_order_lines['product_id'].apply(
                lambda x: x[1] if isinstance(x, list) else str(x))

            # Filter regels zonder transport/verzend
            df_sale_order_lines = df_sale_order_lines[
                ~df_sale_order_lines['product_id'].str.lower().str.contains('transport|verzend')
            ]

            df_sale_order_lines['verschil'] = df_sale_order_lines['product_uom_qty'] - df_sale_order_lines[
                'qty_delivered']
            df_verschil_verkoop = df_sale_order_lines[df_sale_order_lines['verschil'].abs() > 0.01]

            st.subheader("Verkooporderregels met verschil")
            st.dataframe(df_verschil_verkoop.rename(columns={
                'order_id': 'Verkooporder',
                'product_id': 'Product',
                'product_uom_qty': 'Besteld',
                'qty_delivered': 'Geleverd',
                'verschil': 'Verschil'
            }), use_container_width=True)
        else:
            st.info("Geen verkooporderregels gevonden.")

    # 2. Inkooporders ophalen met filtering op datum
    df_purchases = search_read(
        'purchase.order',
        domain=[('state', 'in', ['purchase', 'done']), ('date_order', '>=', start_date.strftime('%Y-%m-%d')),
                ('date_order', '<=', end_date.strftime('%Y-%m-%d'))],
        fields=['id', 'name', 'date_order'],
        context={'lang': 'en_GB'}
    )
    purchase_ids = df_purchases['id'].tolist()

    if not purchase_ids:
        st.info("Geen inkooporders gevonden binnen geselecteerde periode.")
    else:
        df_purchase_order_lines = search_read(
            'purchase.order.line',
            domain=[('order_id', 'in', purchase_ids)],
            fields=['order_id', 'product_id', 'product_qty', 'qty_received'],
            context={'lang': 'en_GB'}
        )

        if not df_purchase_order_lines.empty:
            df_purchase_order_lines['order_id'] = df_purchase_order_lines['order_id'].apply(
                lambda x: x[1] if isinstance(x, list) else x)
            df_purchase_order_lines['product_id'] = df_purchase_order_lines['product_id'].apply(
                lambda x: x[1] if isinstance(x, list) else x)
            df_purchase_order_lines = df_purchase_order_lines[
                ~df_purchase_order_lines['product_id']
                .str.lower()
                .str.contains('shipping|transport|verzend|discount', na=False)
            ]
            df_purchase_order_lines['verschil'] = df_purchase_order_lines['product_qty'] - df_purchase_order_lines[
                'qty_received']
            df_verschil_inkoop = df_purchase_order_lines[df_purchase_order_lines['verschil'].abs() > 0.01]

            st.subheader("Inkooporderregels met verschil")
            st.dataframe(df_verschil_inkoop.rename(columns={
                'order_id': 'Inkooporder',
                'product_id': 'Product',
                'product_qty': 'Besteld',
                'qty_received': 'Ontvangen',
                'verschil': 'Verschil'
            }), use_container_width=True)
        else:
            st.info("Geen inkooporderregels gevonden.")
