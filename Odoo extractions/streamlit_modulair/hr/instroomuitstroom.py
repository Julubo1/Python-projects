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
    st.header("Instroom & Uitstroom")

    # 1. Haal employees op
    df_employees = search_read(
        'hr.employee',
        domain=['|', ['active', '=', True], ['active', '=', False]],
        fields=['id', 'name', 'create_date', 'departure_date', 'departure_reason_id'],
        context={'lang': 'en_GB'}
    )

    if df_employees.empty:
        st.info("Geen medewerkers gevonden.")
        st.stop()

    # 2. Verwerk datumvelden
    df_employees['Instroom'] = pd.to_datetime(
        df_employees['create_date'].where(df_employees['create_date'].apply(lambda x: isinstance(x, str))),
        errors='coerce'
    )
    df_employees['Uitstroom'] = pd.to_datetime(
        df_employees['departure_date'].where(df_employees['departure_date'].apply(lambda x: isinstance(x, str))),
        errors='coerce'
    )
    df_employees['Reden vertrek'] = df_employees['departure_reason_id'].apply(
        lambda x: x[1] if isinstance(x, list) else None
    )

    # 3. Diensttijd in dagen (indien uitstroom bekend)
    df_employees['Diensttijd (dagen)'] = (
            df_employees['Uitstroom'] - df_employees['Instroom']
    ).dt.days

    # 4. Datumfilter
    min_datum = df_employees['Instroom'].min().date()
    max_datum = datetime.today().date()

    start_datum = st.date_input("Startdatum", min_value=min_datum, value=min_datum)
    eind_datum = st.date_input("Einddatum", min_value=start_datum, value=max_datum)

    start_datum = pd.to_datetime(start_datum)
    eind_datum = pd.to_datetime(eind_datum)

    # 5. Filter medewerkers binnen periode (instroom vóór einddatum of uitstroom na startdatum)
    mask = (
            (df_employees['Instroom'] <= eind_datum) &
            (
                    df_employees['Uitstroom'].isna() |
                    (df_employees['Uitstroom'] >= start_datum)
            )
    )
    df_filtered = df_employees[mask].copy()

    # 6. Instroom binnen periode
    instroom_count = df_filtered[
        (df_filtered['Instroom'] >= start_datum) &
        (df_filtered['Instroom'] <= eind_datum)
        ].shape[0]

    # 7. Uitstroom binnen periode
    uitstroom_count = df_filtered[
        df_filtered['Uitstroom'].notna() &
        (df_filtered['Uitstroom'] >= start_datum) &
        (df_filtered['Uitstroom'] <= eind_datum)
        ].shape[0]

    # 8. Gemiddelde diensttijd
    avg_diensttijd = df_filtered['Diensttijd (dagen)'].dropna().mean()

    # 9. Toon resultaten
    st.subheader("Overzicht")
    col1, col2, col3 = st.columns(3)
    col1.metric("Instroom", instroom_count)
    col2.metric("Uitstroom", uitstroom_count)
    col3.metric("Gem. Diensttijd (dagen)", f"{avg_diensttijd:.0f}" if not pd.isna(avg_diensttijd) else "-")

    # 10. Detailweergave
    st.subheader("Details per medewerker")
    st.dataframe(
        df_filtered[['name', 'Instroom', 'Uitstroom', 'Reden vertrek', 'Diensttijd (dagen)']]
        .rename(columns={'name': 'Medewerker'}),
        use_container_width=True
    )