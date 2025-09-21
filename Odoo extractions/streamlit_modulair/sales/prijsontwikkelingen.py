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
    st.title("Prijsontwikkelingen & Margedruk")

    # Stap 1: Ophalen van sale.order.line records
    lines = search_read(
        "sale.order.line",
        [
            ["product_id.detailed_type", "=", "product"],
            ["order_id.state", "in", ["sale", "done"]],
            ["order_id.partner_id.name", "not in", ["PEO B.V. (B)"]],  # intercompany klanten uitsluiten
        ],
        [
            "id",
            "order_id",
            "product_id",
            "price_unit",
            "product_uom_qty",
            "x_studio_net_peo_purchase_price_euro",
            "x_studio_effective_margin"
        ]

    )
    df = pd.DataFrame(lines)

    if df.empty:
        st.warning("Geen verkooporderregels gevonden.")
        st.stop()

    # Stap 2: Ophalen van order-informatie uit sale.order
    order_ids = df['order_id'].apply(lambda x: x[0] if isinstance(x, list) else x).dropna().unique().tolist()

    if not order_ids:
        st.warning("Geen gekoppelde verkooporders gevonden.")
        st.stop()

    orders = search_read(
        "sale.order",
        [["id", "in", order_ids]],
        ["id", "date_order", "team_id", "partner_id"]
    )
    df_orders = pd.DataFrame(orders).rename(columns={"id": "order_id"})

    # Merge order-informatie terug naar sale.order.line
    df['order_id'] = df['order_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
    df_merged = df.merge(df_orders, on="order_id", how="left")

    # Normaliseren van velden
    df_merged['order_date'] = pd.to_datetime(df_merged['date_order'])
    df_merged['team_id'] = df_merged['team_id'].apply(lambda x: x[1] if isinstance(x, list) else None)
    df_merged['order_partner_id'] = df_merged['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else None)
    df_merged['product_id'] = df_merged['product_id'].apply(lambda x: x[1] if isinstance(x, list) else None)

    df = df_merged.copy()

    # Filters
    df['order_date'] = pd.to_datetime(df['order_date'])
    df_filtered = df.copy()

    # Filter: Periode
    start_date = st.date_input("Startdatum", value=df['order_date'].min().date())
    end_date = st.date_input("Einddatum", value=df['order_date'].max().date())
    df_filtered = df_filtered[
        (df_filtered['order_date'] >= pd.to_datetime(start_date)) &
        (df_filtered['order_date'] <= pd.to_datetime(end_date))
        ]

    # Filter: Verkoopteam
    teams = df_filtered['team_id'].dropna().unique()
    selected_teams = st.multiselect("Verkoopteam(s)", options=teams, default=teams)
    df_filtered = df_filtered[df_filtered['team_id'].isin(selected_teams)]

    # Filter: Product
    products = df_filtered['product_id'].dropna().unique()
    selected_products = st.multiselect("Product(en)", options=products, default=products[:10])
    df_filtered = df_filtered[df_filtered['product_id'].isin(selected_products)]

    # Berekeningen
    df_filtered['maand'] = df_filtered['order_date'].dt.to_period('M').astype(str)
    df_filtered['verkoopbedrag'] = df_filtered['price_unit'] * df_filtered['product_uom_qty']
    df_filtered['inkoopbedrag'] = df_filtered['x_studio_net_peo_purchase_price_euro'] * df_filtered['product_uom_qty']
    df_filtered['brutomarge_eur'] = df_filtered['verkoopbedrag'] - df_filtered['inkoopbedrag']
    df_filtered['marge_perc'] = (df_filtered['brutomarge_eur'] / df_filtered['verkoopbedrag'].replace(0, pd.NA)) * 100

    # Aggregatie per maand/product
    pivot = df_filtered.groupby(['maand', 'product_id']).agg({
        'price_unit': 'mean',
        'x_studio_net_peo_purchase_price_euro': 'mean',
        'brutomarge_eur': 'sum',
        'verkoopbedrag': 'sum',
        'inkoopbedrag': 'sum',
        'marge_perc': 'mean'
    }).reset_index().rename(columns={
        'price_unit': 'Gem. verkoopprijs',
        'x_studio_net_peo_purchase_price_euro': 'Gem. inkoopprijs',
        'brutomarge_eur': 'Tot. marge €',
        'verkoopbedrag': 'Tot. omzet',
        'inkoopbedrag': 'Tot. inkoop',
        'marge_perc': 'Gem. marge %'
    })

    # Tabelweergave
    st.subheader("Maandelijkse prijs- en margestatistieken")
    st.dataframe(
        pivot.style.format({
            "Gem. verkoopprijs": "€{:.2f}",
            "Gem. inkoopprijs": "€{:.2f}",
            "Tot. marge €": "€{:.2f}",
            "Tot. omzet": "€{:.2f}",
            "Tot. inkoop": "€{:.2f}",
            "Gem. marge %": "{:.1f}%"
        }),
        use_container_width=True
    )

    # Grafieken
    st.subheader("Prijsontwikkeling per product")
    if not df_filtered['product_id'].dropna().empty:
        selected_product_for_chart = st.selectbox("Kies product voor grafiek",
                                                  sorted(df_filtered['product_id'].unique()))
        df_chart = pivot[pivot['product_id'] == selected_product_for_chart]

        st.line_chart(
            df_chart.set_index('maand')[['Gem. verkoopprijs', 'Gem. inkoopprijs']],
            use_container_width=True
        )

        st.line_chart(
            df_chart.set_index('maand')[['Gem. marge %', 'Gem. marge %']],
            use_container_width=True
        )

        # Signalen margedruk - verbeterd
        st.subheader("Margedruk Signalen")
        months_sorted = sorted(df_chart['maand'].unique())
        if len(months_sorted) < 2:
            st.info("Minimaal twee maanden nodig voor margedrukvergelijking.")
        else:
            last_month = months_sorted[-1]
            prev_month = months_sorted[-2]

            last = df_chart[df_chart['maand'] == last_month].iloc[0]
            prev = df_chart[df_chart['maand'] == prev_month].iloc[0]

            marge_daling = last['Gem. marge %'] < prev['Gem. marge %']
            marge_stijging = last['Gem. marge %'] > prev['Gem. marge %']

            verkoopprijs_verandering = ((last['Gem. verkoopprijs'] - prev['Gem. verkoopprijs']) / prev[
                'Gem. verkoopprijs']) * 100 if prev['Gem. verkoopprijs'] != 0 else None
            inkoopprijs_verandering = ((last['Gem. inkoopprijs'] - prev['Gem. inkoopprijs']) / prev[
                'Gem. inkoopprijs']) * 100 if prev['Gem. inkoopprijs'] != 0 else None
            marge_verandering = ((last['Gem. marge %'] - prev['Gem. marge %']) / abs(prev['Gem. marge %'])) * 100 if \
                prev['Gem. marge %'] != 0 else None

            st.write(f"**Periode:** {prev_month} → {last_month}")
            st.write(f"- Marge verandering: {marge_verandering:.1f}%")
            st.write(f"- Verkoopprijs verandering: {verkoopprijs_verandering:.1f}%")
            st.write(f"- Inkoopprijs verandering: {inkoopprijs_verandering:.1f}%")

            # Analyse margedruk scenario's
            if marge_daling:
                if verkoopprijs_verandering is not None and inkoopprijs_verandering is not None:
                    if verkoopprijs_verandering < 0 and inkoopprijs_verandering > 0:
                        st.warning(
                            "Margedruk: marge daalt door stijgende inkoopprijs en dalende verkoopprijs (prijsdruk).")
                    elif verkoopprijs_verandering > 0 and inkoopprijs_verandering > 0:
                        st.warning(
                            "Margedruk: marge daalt ondanks stijgende verkoopprijs door nog sterkere stijging inkoopprijs.")
                    elif verkoopprijs_verandering < 0 and inkoopprijs_verandering <= 0:
                        st.warning("Margedaling door dalende verkoopprijs, inkoopprijs blijft stabiel of daalt.")
                    else:
                        st.warning("Margedaling zonder duidelijke verkoop- of inkoopprijs verandering.")
                else:
                    st.warning(
                        "Margedaling gedetecteerd, maar onvoldoende data voor verkoop- of inkoopprijs verandering.")
            elif marge_stijging:
                st.success("Marge is gestegen ten opzichte van vorige maand.")
            else:
                st.info("Marge blijft gelijk ten opzichte van vorige maand.")




    else:
        st.info("Geen productgegevens beschikbaar voor grafieken.")

    # Verkoopvolume per maand voor gekozen product
    st.subheader("Verkochte aantallen per maand")
    volume_per_maand = df_filtered[df_filtered['product_id'] == selected_product_for_chart] \
        .groupby('maand')['product_uom_qty'].sum().reset_index()
    st.dataframe(volume_per_maand.rename(columns={'product_uom_qty': 'Aantal verkocht'}))
    # st.bar_chart(volume_per_maand.set_index('maand'), use_container_width=True)

    # Jaarlijkse verkoop per geselecteerd product
    st.subheader("Jaaroverzicht verkopen per product")

    df_filtered['jaar'] = df_filtered['order_date'].dt.year
    jaaroverzicht = df_filtered[df_filtered['product_id'] == selected_product_for_chart] \
        .groupby('jaar')['product_uom_qty'].sum().reset_index()
    jaaroverzicht = jaaroverzicht.rename(columns={'product_uom_qty': 'Aantal verkocht'})
    st.dataframe(jaaroverzicht)
    # st.bar_chart(jaaroverzicht.set_index('jaar'), use_container_width=True)