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
    st.header("Accounting Inzichten")

    # --- HELPER FUNCTIE VOOR EURO-FORMAT ---
    def format_euro(value):
        try:
            return f"€ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return value

    # --- DATUMFILTERS ---
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", pd.to_datetime("today") - pd.Timedelta(days=90))
    with col2:
        end_date = st.date_input("Einddatum", pd.to_datetime("today"))

    if start_date > end_date:
        st.warning("Startdatum kan niet na einddatum liggen.")
    else:
        # --- DATA OPHALEN: FACTUREN ---
        df_invoices = search_read(
            'account.move',
            domain=[
                ('move_type', 'in', ['out_invoice', 'in_invoice']),
                ('invoice_date', '>=', start_date.strftime('%Y-%m-%d')),
                ('invoice_date', '<=', end_date.strftime('%Y-%m-%d'))
            ],
            fields=[
                'name', 'move_type', 'partner_id', 'invoice_date', 'invoice_date_due',
                'amount_total', 'amount_residual', 'currency_id', 'state'
            ]
        )

        if not df_invoices.empty:
            # --- TRANSFORMATIE ---
            df_invoices['Partner'] = df_invoices['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x))
            df_invoices['Type'] = df_invoices['move_type'].map({
                'out_invoice': 'Klantfactuur',
                'in_invoice': 'Inkoopfactuur'
            })
            df_invoices['Date'] = pd.to_datetime(df_invoices['invoice_date'], errors='coerce')
            df_invoices['Due Date'] = pd.to_datetime(df_invoices['invoice_date_due'], errors='coerce')
            df_invoices['Open Amount'] = df_invoices['amount_residual']
            df_invoices['Total'] = df_invoices['amount_total']
            df_invoices['Days Overdue'] = (pd.to_datetime("today") - df_invoices['Due Date']).dt.days
            df_invoices['Status'] = df_invoices['state']

            # --- OVERDUE FILTER ---
            st.subheader("Overzicht openstaande facturen (bottleneck)")

            overdue_df = df_invoices[
                (df_invoices['Open Amount'] > 0) &
                (df_invoices['Due Date'] < pd.to_datetime("today"))
                ]

            st.metric("Aantal openstaande facturen", len(overdue_df))
            st.metric("Totaal open bedrag (€)", format_euro(overdue_df['Open Amount'].sum()))

            st.dataframe(
                overdue_df[['Partner', 'Type', 'Date', 'Due Date', 'Open Amount', 'Days Overdue', 'Status']]
                .assign(**{'Open Amount': lambda df: df['Open Amount'].apply(format_euro)}),
                use_container_width=True
            )

            # --- OMZET & KOSTEN ---
            st.subheader("Omzet & Kosten Overzicht")

            omzet_df = df_invoices[df_invoices['Type'] == 'Klantfactuur']
            kosten_df = df_invoices[df_invoices['Type'] == 'Inkoopfactuur']

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Totale omzet", format_euro(omzet_df['Total'].sum()))
            with col2:
                st.metric("Totale kosten", format_euro(kosten_df['Total'].sum()))

            # --- CASHFLOW HISTORIE GRAFIEK ---
            st.subheader("Factuurbedragen per maand")

            df_invoices['Month'] = df_invoices['Date'].dt.to_period("M").astype(str)
            df_chart = df_invoices.groupby(['Month', 'Type'])['Total'].sum().unstack().fillna(0)
            st.bar_chart(df_chart)

            # --- AGING BUCKETS ---
            st.subheader("Aging Buckets")

            df_aging = df_invoices[
                (df_invoices['Open Amount'] > 0) &
                (df_invoices['Due Date'] < pd.to_datetime("today")) &
                (df_invoices['Type'] == 'Klantfactuur')
                ].copy()

            df_aging['Aging Bucket'] = pd.cut(
                df_aging['Days Overdue'],
                bins=[0, 30, 60, 90, 9999],
                labels=['0–30 dagen', '31–60 dagen', '61–90 dagen', '90+ dagen']
            )

            bucket_summary = df_aging.groupby('Aging Bucket')['Open Amount'].sum().reset_index()
            bucket_summary['Open Amount'] = bucket_summary['Open Amount'].apply(format_euro)

            st.table(bucket_summary)

            # --- DSO ANALYSE ---
            st.subheader("DSO Analyse (gem. dagen open per klant)")

            dso_df = df_invoices[
                (df_invoices['Type'] == 'Klantfactuur') &
                (df_invoices['Open Amount'] == 0) &
                (df_invoices['Date'].notna()) &
                (df_invoices['Due Date'].notna())
                ].copy()

            dso_df['DSO'] = (dso_df['Due Date'] - dso_df['Date']).dt.days
            avg_dso = dso_df.groupby('Partner')['DSO'].mean().sort_values(ascending=False).reset_index()

            st.dataframe(avg_dso.rename(columns={"Partner": "Klant", "DSO": "Gem. Dagen Open"}))

            # --- CREDITNOTA'S ZONDER VERREKENING ---
            st.subheader("Creditnota's zonder verrekening")

            df_credit = search_read(
                'account.move',
                domain=[
                    ('move_type', '=', 'out_refund'),
                    ('state', '=', 'posted'),
                    ('amount_residual', '>', 0.0),
                    ('invoice_date', '>=', start_date.strftime('%Y-%m-%d')),
                    ('invoice_date', '<=', end_date.strftime('%Y-%m-%d'))
                ],
                fields=[
                    'name', 'partner_id', 'invoice_date', 'amount_total', 'amount_residual', 'currency_id'
                ]
            )

            if not df_credit.empty:
                df_credit['Partner'] = df_credit['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x))
                df_credit['Date'] = pd.to_datetime(df_credit['invoice_date'], errors='coerce')
                df_credit['Open Amount'] = df_credit['amount_residual']
                df_credit['Total'] = df_credit['amount_total']
                df_credit['Open Amount'] = df_credit['Open Amount'].apply(format_euro)
                df_credit['Total'] = df_credit['Total'].apply(format_euro)

                st.dataframe(
                    df_credit[['name', 'Partner', 'Date', 'Total', 'Open Amount']],
                    use_container_width=True
                )
            else:
                st.info("Geen openstaande creditnota’s gevonden in deze periode.")

        else:
            st.info("Geen factuurdata beschikbaar voor de geselecteerde periode.")