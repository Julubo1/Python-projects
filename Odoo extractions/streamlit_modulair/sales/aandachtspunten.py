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
    st.title("Aandachtspunten & Exception Reports")

    # Datumfilter: begin- en einddatum selecteren
    col_start, col_end = st.columns(2)
    start_date = col_start.date_input("Startdatum", value=datetime(datetime.now().year, 1, 1))
    end_date = col_end.date_input("Einddatum", value=datetime.now().date())

    if start_date > end_date:
        st.error("Startdatum moet voor de einddatum liggen.")
    else:
        # Data ophalen, inclusief result responsible veld
        df_orders = search_read(
            'sale.order',
            domain=[('state', '!=', 'sale'), ('state', '!=', 'cancel')],
            fields=['name', 'date_order', 'x_studio_result_responsable', 'amount_total', 'validity_date', 'state']
        )

        if df_orders.empty:
            st.info("Geen openstaande orders.")
        else:
            df_orders['date_order'] = pd.to_datetime(df_orders['date_order'], errors='coerce')
            df_orders = filter_on_date_range(df_orders, 'date_order', start_date, end_date)

            if df_orders.empty:
                st.warning("Geen openstaande orders in de gekozen periode.")
            else:
                # Naam extractie
                def get_name(x):
                    return x if isinstance(x, str) else ('Onbekend' if x is None else str(x))

                df_orders['result_responsible'] = df_orders['x_studio_result_responsable'].apply(get_name)

                # Filter op verantwoordelijke (optioneel)
                verantwoordelijken = ['Alle'] + sorted(df_orders['result_responsible'].unique())
                gekozen_verantwoordelijke = st.selectbox("Filter op verantwoordelijke", verantwoordelijken, index=0)
                if gekozen_verantwoordelijke != 'Alle':
                    df_orders = df_orders[df_orders['result_responsible'] == gekozen_verantwoordelijke]

                # Bereken aantal dagen open
                df_orders['days_open'] = (pd.Timestamp.now() - df_orders['date_order']).dt.days

                # Bereken verlopen offertes (validity_date)
                df_orders['validity_date'] = pd.to_datetime(df_orders['validity_date'], errors='coerce')
                df_orders['is_validity_expired'] = df_orders['validity_date'].notnull() & (
                        df_orders['validity_date'] < pd.Timestamp.now())

                st.subheader("Orders langer dan 30 dagen open")
                orders_lang_open = df_orders[df_orders['days_open'] > 30].sort_values('days_open', ascending=False)
                st.dataframe(
                    orders_lang_open[['name', 'date_order', 'result_responsible', 'amount_total', 'days_open']])

                st.subheader("Orders met verlopen geldigheidsdatum")
                verlopen_offertes = df_orders[df_orders['is_validity_expired']].sort_values('validity_date')
                st.dataframe(
                    verlopen_offertes[['name', 'date_order', 'result_responsible', 'amount_total', 'validity_date']])

                # Extra alert: Grote openstaande orders (> 10.000 bijvoorbeeld)
                st.subheader("Grote openstaande orders (> 10.000)")
                grote_orders = df_orders[df_orders['amount_total'] > 10000].sort_values('amount_total', ascending=False)
                st.dataframe(grote_orders[['name', 'date_order', 'result_responsible', 'amount_total']])
