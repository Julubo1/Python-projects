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
    st.title("Verkoopteam Insights")

    # Datumfilter: begin- en einddatum selecteren
    col_start, col_end = st.columns(2)
    start_date = col_start.date_input("Startdatum", value=datetime(datetime.now().year, 1, 1))
    end_date = col_end.date_input("Einddatum", value=datetime.now().date())

    if start_date > end_date:
        st.error("Startdatum moet voor de einddatum liggen.")
    else:
        # Haal verkooporders met veld x_studio_result_responsable
        df_sales = search_read(
            'sale.order',
            domain=[('state', 'in', ['sale', 'done'])],
            fields=['name', 'amount_total', 'date_order', 'x_studio_result_responsable']
        )

        if df_sales.empty:
            st.warning("Geen verkoopdata gevonden.")
        else:
            df_sales['date_order'] = pd.to_datetime(df_sales['date_order'], errors='coerce')
            df_sales = filter_on_date_range(df_sales, 'date_order', start_date, end_date)

            # Helper om naam uit [id, naam] te halen
            def get_name(x):
                if not x or x is False:
                    return 'Onbekend'
                if isinstance(x, (list, tuple)) and len(x) == 2:
                    return x[1]
                return str(x)

            df_sales = df_sales[
                df_sales['x_studio_result_responsable'].notnull() & (df_sales['x_studio_result_responsable'] != False)
                ]
            df_sales['result_responsible_name'] = df_sales['x_studio_result_responsable'].apply(get_name)

            # Filter: lijst unieke verantwoordelijken
            verantwoordelijken = df_sales['result_responsible_name'].unique().tolist()
            verantwoordelijken = ['Alle verantwoordelijken'] + [v for v in verantwoordelijken if v != 'Onbekend']

            selected_responsible = st.selectbox("Selecteer verantwoordelijke:", verantwoordelijken)

            if selected_responsible != 'Alle verantwoordelijken':
                df_sales = df_sales[df_sales['result_responsible_name'] == selected_responsible]

            if df_sales.empty:
                st.info(f"Geen verkooporders gevonden voor {selected_responsible} in de gekozen periode.")
            else:
                # KPI's
                totaal_orders = df_sales['name'].nunique()
                totaal_omzet = df_sales['amount_total'].sum()
                gemiddelde_omzet = df_sales['amount_total'].mean()

                col1, col2, col3 = st.columns(3)
                col1.metric("Aantal Orders", f"{totaal_orders}")
                col2.metric("Totale Omzet (€)", f"€ {totaal_omzet:,.2f}")
                col3.metric("Gem. Orderwaarde (€)", f"€ {gemiddelde_omzet:,.2f}")

                # Maandelijkse omzet
                df_sales['month'] = df_sales['date_order'].dt.to_period('M').astype(str)
                omzet_maand = df_sales.groupby('month')['amount_total'].sum().reset_index()

                fig = px.bar(
                    omzet_maand,
                    x='month',
                    y='amount_total',
                    labels={'month': 'Maand', 'amount_total': 'Omzet (€)'},
                    title=f"Maandelijkse omzet {selected_responsible}"
                )
                st.plotly_chart(fig, use_container_width=True)

                st.subheader(f"Details orders - {selected_responsible}")
                st.dataframe(
                    df_sales[['name', 'date_order', 'amount_total', 'result_responsible_name']]
                    .sort_values('date_order', ascending=False)
                    .rename(columns={
                        'name': 'Order',
                        'date_order': 'Date',
                        'amount_total': 'Amount (€)',
                        'result_responsible_name': 'Result Responsible'
                    })
                )