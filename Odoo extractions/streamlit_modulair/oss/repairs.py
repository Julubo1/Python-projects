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
    st.title("Reparaties bij OEM – Overzicht van uitbestede herstellingen")

    # Stap 1: Haal repair orders op met status 'waiting_for_subcontract_product'
    df_repairs = search_read(
        'repair.order',
        domain=[('state', '=', 'waiting_for_subcontract_product')],
        fields=['id', 'name', 'product_id', 'partner_id', 'subcontract_product_partner'],
        context={'lang': 'en_GB'}
    )

    if df_repairs.empty:
        st.info("Geen reparaties in status 'Wait for Supplier'.")
        st.stop()

    df_repairs = pd.DataFrame(df_repairs)

    def extract_id(val):
        if isinstance(val, list) and len(val) > 0:
            return val[0]
        return None

    def extract_name(val):
        if isinstance(val, list) and len(val) > 1:
            return val[1]
        elif isinstance(val, dict) and 'name' in val:
            return val['name']
        return str(val)

    df_repairs['Repair Order ID'] = df_repairs['id']
    df_repairs['Repair Order'] = df_repairs['name']
    df_repairs['Product'] = df_repairs['product_id'].apply(extract_name)
    df_repairs['Partner'] = df_repairs['partner_id'].apply(extract_name)
    df_repairs['OEM'] = df_repairs['subcontract_product_partner'].apply(extract_name)
    df_repairs['OEM_ID'] = df_repairs['subcontract_product_partner'].apply(extract_id)

    # Stap 2: Zoek per repair order naar de bijhorende stock.picking (transfer)
    transfer_infos = []
    for _, row in df_repairs.iterrows():
        repair_name = row['Repair Order']
        oem_partner_id = row['OEM_ID']

        # Zoek stock.picking met origin == repair_name en location_id == oem_partner_id
        pickings = search_read(
            'stock.picking',
            domain=[
                ('origin', '=', repair_name),
                ('partner_id', '=', oem_partner_id),
                ('picking_type_code', '=', 'incoming')
            ],
            fields=['name', 'scheduled_date'],
            context={'lang': 'en_GB'}
        )

        if not pickings.empty:
            # Neem de eerste transfer (er zou er normaal maar één zijn)
            picking = pickings.iloc[0]
            transfer_infos.append({
                'Repair Order': repair_name,
                'Transfer': picking.get('name'),
                'Expected Return': picking.get('scheduled_date')
            })
        else:
            transfer_infos.append({
                'Repair Order': repair_name,
                'Transfer': None,
                'Expected Return': None
            })

    df_transfer = pd.DataFrame(transfer_infos)

    # Merge met originele repair-informatie
    df_merged = pd.merge(df_repairs, df_transfer, on='Repair Order', how='left')

    df_show = df_merged[[
        'Repair Order', 'Product', 'Partner', 'OEM', 'Transfer', 'Expected Return'
    ]]

    st.subheader("Repair orders die wachten op leverancier")
    st.dataframe(df_show)