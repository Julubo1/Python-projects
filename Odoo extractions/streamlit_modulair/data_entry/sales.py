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
    st.title("Data Entry Fouten Monitor - Sales Module")

    # Gegevens inladen
    df_sales = search_read(
        'sale.order',
        domain=[('partner_id', '!=', 77), ('state', 'not in', ['sale', 'done', 'cancel'])],
        fields=[
            'name', 'partner_id', 'validity_date', 'x_studio_result_responsable', 'team_id',
            'state', 'amount_total', 'x_studio_rd_poc', 'date_order', 'client_order_ref'
        ],
        context={'lang': 'en_GB'}
    )

    # Mapping
    df_sales['team'] = df_sales['team_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_sales['klant'] = df_sales['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_sales['resultresponsible'] = df_sales['x_studio_result_responsable'].apply(
        lambda x: x[1] if isinstance(x, list) else '')

    issues = []
    today = pd.Timestamp.today().normalize()

    for _, row in df_sales.iterrows():
        row_issues = []

        if not row['name']:
            row_issues.append("Ordernaam ontbreekt")

        if not row['team']:
            row_issues.append("Sales Team ontbreekt")

        if row['team'] in ['Order', 'Office', 'Info', 'Odoo', 'MarCom']:
            row_issues.append(f"Ongeldig Sales Team: {row['team']}")

        if not row['resultresponsible']:
            row_issues.append("Geen Result Responsible toegewezen")

        if not row['x_studio_rd_poc'] and row['client_order_ref']:
            row_issues.append("Geen POC Receive Date ingevuld")

        if row['x_studio_rd_poc'] and not row['client_order_ref']:
            row_issues.append("Geen POC reference ingevuld")

        if not row['klant']:
            row_issues.append("Geen klant gekoppeld")

        if not row['date_order']:
            row_issues.append("Orderdatum ontbreekt")
        else:
            try:
                d = pd.to_datetime(row['date_order']).normalize()
                if d > today:
                    row_issues.append("Orderdatum ligt in de toekomst")
            except Exception:
                row_issues.append("Orderdatum is ongeldig formaat")

        if not row['validity_date']:
            row_issues.append("Quote expiration ontbreekt")
        else:
            try:
                d = pd.to_datetime(row['validity_date']).normalize()
                if d < today:
                    row_issues.append("Quote is Expired")
            except Exception:
                row_issues.append("Orderdatum is ongeldig formaat")

        if row_issues:
            issues.append({
                "Order": row['name'],
                "Result Responsible": row['resultresponsible'],
                "Sales Team": row['team'],
                "Expiration Date": row['validity_date'],
                "RD-POC": row['x_studio_rd_poc'],
                "POC Ref": row['client_order_ref'],
                "Klant": row['klant'],
                "Fouten": "; ".join(row_issues)
            })

    if not issues:
        st.success("Geen data entry fouten in Sales gevonden.")
    else:
        fout_df = pd.DataFrame(issues)

        # Zet alle kolommen naar string om pyarrow fout te voorkomen
        fout_df = fout_df.astype(str)

        unieke_fouten = sorted({f for issuelijst in fout_df['Fouten'] for f in issuelijst.split("; ")})

        fout_filter = st.selectbox(
            "Filter op fouttype (Sales)",
            ["Toon alles"] + unieke_fouten,
            key="sales_fout_filter"
        )

        if fout_filter != "Toon alles":
            fout_df = fout_df[fout_df['Fouten'].str.contains(fout_filter)]

        st.warning(f"{len(fout_df)} foutieve Sales-records gevonden.")
        st.dataframe(fout_df)