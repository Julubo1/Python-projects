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
    st.title("Best Verkochte Producten")

    # Dynamische datumfilter (periode)
    periode = st.date_input(
        "Selecteer periode",
        value=(pd.to_datetime("2025-01-01"), pd.to_datetime("2025-12-31")),
        help="Selecteer de start- en einddatum"
    )
    if not (isinstance(periode, tuple) and len(periode) == 2):
        st.warning("Selecteer een geldige periode (start en einddatum).")
        st.stop()

    start_datum, eind_datum = periode
    start_datum = pd.to_datetime(start_datum)
    eind_datum = pd.to_datetime(eind_datum)

    # 1) Verkooporderregels ophalen (bevestigde orders)
    df_order_lines = search_read(
        'sale.order.line',
        domain=[('order_id.state', 'in', ['sale', 'done'])],
        fields=['order_id', 'product_id', 'product_uom_qty', 'price_total', 'currency_id'],
        context={'lang': 'en_GB'}
    )

    df_orders = search_read(
        'sale.order',
        domain=[('state', 'in', ['sale', 'done'])],
        fields=['id', 'team_id', 'date_order', 'partner_id'],
        context={'lang': 'en_GB'}
    )

    # 2) Repair orders ophalen (done status) - met alleen benodigde velden
    df_repairs = search_read(
        'repair.order',
        domain=[('state', '=', 'done')],
        fields=['fees_lines', 'operations', 'x_studio_many2one_field_maTCd', 'x_studio_order_date', 'partner_id'],
        context={'lang': 'en_GB'}
    )

    if (df_order_lines.empty if df_order_lines is not None else True) and (
            df_repairs.empty if df_repairs is not None else True):
        st.warning("Geen verkooporders of reparatieorders gevonden.")
    else:
        # --- Sales orders voorbereiden ---
        if df_order_lines is not None and not df_order_lines.empty:
            # Filter partner 'company B.V.(B)'
            df_orders = df_orders[
                df_orders['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x)) != 'company B.V.(B)'
                ]
            df_order_lines['order_id'] = df_order_lines['order_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
            df_orders['date_order'] = pd.to_datetime(df_orders['date_order'], errors='coerce')

            # Filter op gekozen periode
            df_orders = df_orders[(df_orders['date_order'] >= start_datum) & (df_orders['date_order'] <= eind_datum)]

            df = df_order_lines.merge(df_orders, left_on='order_id', right_on='id', suffixes=('_line', '_order'))

            df['Team'] = df['team_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) == 2 else str(x))
            df['Product'] = df['product_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) == 2 else str(x))

            df_sales_prepared = df[['Product', 'product_uom_qty', 'price_total', 'Team']]
        else:
            df_sales_prepared = pd.DataFrame(columns=['Product', 'product_uom_qty', 'price_total', 'Team'])

        # --- Repair orders voorbereiden ---
        repair_rows = []
        if df_repairs is not None and not df_repairs.empty:
            df_repairs = df_repairs[
                df_repairs['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x)) != 'company B.V.(B)'
                ]
            df_repairs['x_studio_order_date'] = pd.to_datetime(df_repairs['x_studio_order_date'], errors='coerce')

            # Filter op gekozen periode
            df_repairs = df_repairs[
                (df_repairs['x_studio_order_date'] >= start_datum) & (df_repairs['x_studio_order_date'] <= eind_datum)]

            fees_ids = []
            operations_ids = []
            for _, r in df_repairs.iterrows():
                fees_ids.extend(r['fees_lines'] if isinstance(r['fees_lines'], list) else [])
                operations_ids.extend(r['operations'] if isinstance(r['operations'], list) else [])

            df_fees = pd.DataFrame()
            if fees_ids:
                df_fees = search_read(
                    'repair.fee',
                    domain=[('id', 'in', fees_ids)],
                    fields=['id', 'product_id', 'price_subtotal'],
                    context={'lang': 'en_GB'}
                )

            df_ops = pd.DataFrame()
            if operations_ids:
                df_ops = search_read(
                    'repair.line',
                    domain=[('id', 'in', operations_ids)],
                    fields=['id', 'product_id', 'price_total'],
                    context={'lang': 'en_GB'}
                )

            for _, row in df_repairs.iterrows():
                team_name = (row['x_studio_many2one_field_maTCd'][1]
                             if isinstance(row['x_studio_many2one_field_maTCd'], list) and len(
                    row['x_studio_many2one_field_maTCd']) == 2
                             else str(row['x_studio_many2one_field_maTCd']))

                if row['fees_lines']:
                    for fee_id in row['fees_lines']:
                        fee_line = df_fees[df_fees['id'] == fee_id]
                        if not fee_line.empty:
                            product_field = fee_line.iloc[0]['product_id']
                            product_name = product_field[1] if isinstance(product_field, list) and len(
                                product_field) == 2 else str(product_field)
                            price = fee_line.iloc[0]['price_subtotal'] if 'price_subtotal' in fee_line.columns else 0
                            repair_rows.append({
                                'Product': product_name,
                                'product_uom_qty': 1,
                                'price_total': price,
                                'Team': team_name
                            })

                if row['operations']:
                    for op_id in row['operations']:
                        op_line = df_ops[df_ops['id'] == op_id]
                        if not op_line.empty:
                            product_field = op_line.iloc[0]['product_id']
                            product_name = product_field[1] if isinstance(product_field, list) and len(
                                product_field) == 2 else str(product_field)
                            price = op_line.iloc[0]['price_total'] if 'price_total' in op_line.columns else 0
                            repair_rows.append({
                                'Product': product_name,
                                'product_uom_qty': 1,
                                'price_total': price,
                                'Team': team_name
                            })

            df_repair_prepared = pd.DataFrame(repair_rows)
        else:
            df_repair_prepared = pd.DataFrame(columns=['Product', 'product_uom_qty', 'price_total', 'Team'])

        # --- Combineer sales en repair data ---
        combined_df = pd.concat([df_sales_prepared, df_repair_prepared], ignore_index=True)

        # Team filter opties
        teams = combined_df['Team'].dropna().unique().tolist()
        selected_team = st.selectbox("Filter op Business Line", options=["Alle"] + teams)

        if selected_team != "Alle":
            combined_df = combined_df[combined_df['Team'] == selected_team]

        # Aggregatie
        product_summary = combined_df.groupby('Product').agg({
            'product_uom_qty': 'sum',
            'price_total': 'sum'
        }).sort_values(by='price_total', ascending=False).reset_index()

        st.subheader("Top Verkochte Producten (totaalbedrag)")
        st.dataframe(product_summary.style.format({'price_total': '€ {:,.2f}', 'product_uom_qty': '{:,.0f}'}))

        # Grafiek
        import plotly.express as px

        st.subheader("Visualisatie")
        fig = px.bar(
            product_summary.head(15),
            x='price_total',
            y='Product',
            orientation='h',
            labels={'price_total': 'Totale Opbrengst (€)'},
            title=f"Top 15 Producten ({selected_team})"
        )
        st.plotly_chart(fig, use_container_width=True)

