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

from shared.core import search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping
def show():
    st.title("Activiteiten & Volgende Acties in CRM")

    # Datumfilter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", value=datetime.today().replace(day=1))
    with col2:
        end_date = st.date_input("Einddatum", value=datetime.today())

    if start_date > end_date:
        st.error("Startdatum mag niet na einddatum liggen.")
        st.stop()

    df_activities = search_read(
        'mail.activity',
        domain=[('res_model', '=', 'crm.lead')],
        fields=['id', 'related_model_instance', 'res_id', 'res_model', 'user_id', 'activity_type_id', 'date_deadline',
                'summary', 'note', 'state'],
        context={'lang': 'en_GB'}
    )

    # Groepeer per model alle res_ids
    res_model_map = {}
    for _, row in df_activities.iterrows():
        model = row['res_model']
        res_id = row['res_id']
        if model and res_id:
            res_model_map.setdefault(model, set()).add(res_id)

    # Haal namen per model in bulk op
    res_id_to_name = {}
    for model, ids in res_model_map.items():
        try:
            data_df = search_read(model, domain=[('id', 'in', list(ids))], fields=['name'])
            data = data_df.to_dict(orient='records')

            for record in data:
                key = (model, record['id'])
                res_id_to_name[key] = record.get('name', '')
        except Exception as e:
            st.warning(f"Fout bij ophalen van namen voor model {model}: {e}")

    # Voeg kolom toe aan df_activities
    df_activities['Record Naam'] = df_activities.apply(
        lambda row: res_id_to_name.get((row['res_model'], row['res_id']), ''),
        axis=1
    )

    if df_activities.empty:
        st.info("Geen activiteiten gevonden.")
        st.stop()

    # Converteer deadline naar datetime.date, filter op datumrange
    df_activities['deadline'] = pd.to_datetime(df_activities['date_deadline'], errors='coerce').dt.date
    mask = (df_activities['deadline'] >= start_date) & (df_activities['deadline'] <= end_date)
    df_activities = df_activities.loc[mask]

    if df_activities.empty:
        st.warning(f"Geen activiteiten gevonden tussen {start_date} en {end_date}.")
        st.stop()

    df_activities['note'] = df_activities['note'].apply(strip_html)
    df_activities['user'] = df_activities['user_id'].apply(
        lambda x: x[1] if isinstance(x, list) and len(x) == 2 else str(x))
    df_activities['type'] = df_activities['activity_type_id'].apply(
        lambda x: x[1] if isinstance(x, list) and len(x) == 2 else str(x))

    st.subheader("Geplande activiteiten")
    planned = df_activities[df_activities['state'] == 'planned']
    st.dataframe(planned[['Record Naam', 'user', 'deadline', 'summary', 'note', 'res_model']])

    st.subheader("Overdue Activiteiten")
    missed = df_activities[
        (df_activities['state'] == 'overdue') & (df_activities['deadline'] < datetime.now().date())]
    st.dataframe(missed[['Record Naam', 'user', 'deadline', 'summary', 'note', 'res_model']])