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
    st.title("Multi-year Trend Analyses (Sales + Repair)")

    # Sales Orders
    df_sales = search_read(
        'sale.order',
        domain=[('state', 'in', ['sale', 'done'])],
        fields=['date_order', 'amount_total', 'team_id', 'partner_id'],
        context={'lang': 'en_GB'}
    )

    # Repair Orders
    df_repair = search_read(
        'repair.order',
        domain=[('state', 'not in', ['cancel'])],
        fields=['x_studio_order_date', 'amount_untaxed', 'partner_id', 'x_studio_many2one_field_maTCd'],
        context={'lang': 'en_GB'}
    )

    if df_sales.empty and df_repair.empty:
        st.warning("Geen verkoop- of reparatiegegevens gevonden.")
    else:
        # --- SALES ---
        df_sales['datum'] = pd.to_datetime(df_sales['date_order'], errors='coerce')
        df_sales['jaar'] = df_sales['datum'].dt.year
        df_sales['team'] = df_sales['team_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')
        df_sales['klant'] = df_sales['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')
        df_sales['bedrag'] = df_sales['amount_total']
        df_sales['bron'] = 'Sales'

        df_sales = df_sales[['datum', 'jaar', 'team', 'klant', 'bedrag', 'bron']]

        # --- REPAIR ---
        if not df_repair.empty:
            df_repair['datum'] = pd.to_datetime(df_repair['x_studio_order_date'], errors='coerce')
            df_repair = df_repair[df_repair['datum'].notna()]
            df_repair['jaar'] = df_repair['datum'].dt.year
            df_repair['team'] = df_repair['x_studio_many2one_field_maTCd'].apply(
                lambda x: x[1] if isinstance(x, list) else 'Onbekend')
            df_repair['klant'] = df_repair['partner_id'].apply(
                lambda x: x[1] if isinstance(x, list) else 'Onbekend')
            df_repair['bedrag'] = df_repair['amount_untaxed']
            df_repair['bron'] = 'Repair'

            df_repair = df_repair[['datum', 'jaar', 'team', 'klant', 'bedrag', 'bron']]

            # Combineer sales + repair
            df_all = pd.concat([df_sales, df_repair], ignore_index=True)
        else:
            df_all = df_sales.copy()

        jaren_beschikbaar = sorted(df_all['jaar'].dropna().unique())
        st.write(f"Beschikbare jaren: {jaren_beschikbaar[0]} - {jaren_beschikbaar[-1]}")

        # ==== Omzet per jaar per Business Line ====
        omzet_team = (
            df_all.groupby(['jaar', 'team'])['bedrag']
            .sum()
            .reset_index()
            .sort_values(['team', 'jaar'])
        )
        fig1 = px.line(omzet_team, x='jaar', y='bedrag', color='team',
                       labels={'jaar': 'Jaar', 'bedrag': 'Omzet (€)', 'team': 'Business Line'},
                       title='Omzet per jaar per Business Line (incl. Repair)', markers=True)
        st.plotly_chart(fig1, use_container_width=True)

        # ==== Omzet per jaar per klant (top 10 klanten) ====
        # top_klanten = df_all.groupby('klant')['bedrag'].sum().nlargest(10).index.tolist()
        # df_topklanten = df_all[df_all['klant'].isin(top_klanten)]

        # omzet_klant = (
        #    df_topklanten.groupby(['jaar', 'klant'])['bedrag']
        #    .sum()
        #    .reset_index()
        #    .sort_values(['klant', 'jaar'])
        # )
        # fig2 = px.line(omzet_klant, x='jaar', y='bedrag', color='klant',
        #               labels={'jaar': 'Jaar', 'bedrag': 'Omzet (€)', 'klant': 'Klant'},
        #               title='Omzet per jaar - Top 10 Klanten (Sales + Repair)', markers=True)
        # st.plotly_chart(fig2, use_container_width=True)

        # ==== KPI: Orders per jaar ====
        kpi = df_all.groupby('jaar').agg(
            aantal_orders=('datum', 'count'),
            totaal_omzet=('bedrag', 'sum')
        ).reset_index()

        kpi['Gemiddelde orderwaarde (€)'] = kpi['totaal_omzet'] / kpi['aantal_orders']
        kpi['totaal_omzet'] = kpi['totaal_omzet'].apply(lambda x: f"€ {x:,.0f}".replace(',', '.'))
        kpi['Gemiddelde orderwaarde (€)'] = kpi['Gemiddelde orderwaarde (€)'].apply(
            lambda x: f"€ {x:,.0f}".replace(',', '.'))

        st.subheader("Overzicht KPI's per jaar (Sales + Repair)")
        st.dataframe(kpi.rename(columns={
            'jaar': 'Jaar',
            'aantal_orders': 'Aantal Orders',
            'totaal_omzet': 'Totale Omzet (€)'
        }))
