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
    st.title("Sales Performance Overview")

    # Dynamische datumfilter met Streamlit date_input
    start_date = st.date_input("Startdatum", pd.to_datetime("2024-01-01"))
    end_date = st.date_input("Einddatum", pd.to_datetime("2024-12-31"))

    if start_date > end_date:
        st.error("Startdatum moet voor de einddatum liggen.")
    else:
        df_orders = search_read(
            'sale.order',
            domain=[('state', 'in', ['sale', 'done'])],
            fields=['user_id', 'amount_total', 'date_order', 'x_studio_result_responsable']
        )

        if df_orders.empty:
            st.info("Geen verkoopdata gevonden.")
        else:
            df_orders = filter_on_date_range(df_orders, 'date_order', start_date, end_date)
            if df_orders.empty:
                st.warning(f"Geen verkoopdata tussen {start_date} en {end_date}.")
            else:
                def get_name(x):
                    if not x or x is False:
                        return 'Onbekend'
                    if isinstance(x, (list, tuple)) and len(x) == 2:
                        return x[1]
                    return str(x)

                df_orders = df_orders[df_orders['x_studio_result_responsable'].notnull() & (
                        df_orders['x_studio_result_responsable'] != False)]
                df_orders['rr'] = df_orders['x_studio_result_responsable'].apply(get_name)
                df_orders['month'] = pd.to_datetime(df_orders['date_order']).dt.to_period('M').dt.to_timestamp()

                monthly = df_orders.groupby(['rr', 'month']).agg(
                    omzet=('amount_total', 'sum'),
                    aantal_orders=('date_order', 'count')
                ).reset_index()

                totaal_omzet = df_orders['amount_total'].sum()
                totaal_orders = df_orders.shape[0]
                unique_users = df_orders['rr'].nunique()

                st.metric("Totale omzet", f"€ {totaal_omzet:,.2f}")
                st.metric("Aantal orders", f"{totaal_orders}")
                st.metric("Aantal verkopers actief", f"{unique_users}")

                omzet_per_user = df_orders.groupby('rr')['amount_total'].sum().reset_index()
                # fig1 = px.bar(omzet_per_user, x='rr', y='amount_total', labels={'rr': 'Verkoper', 'amount_total': 'Omzet (€)'}, title='Omzet per verkoper')
                # st.plotly_chart(fig1, use_container_width=True)

                # fig2 = px.line(monthly, x='month', y='omzet', color='rr', markers=True, labels={'month': 'Maand', 'omzet': 'Omzet (€)'}, title='Omzet per maand per verkoper')
                # st.plotly_chart(fig2, use_container_width=True)