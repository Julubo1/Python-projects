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

from shared.core import search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate

def show():
    st.title(f"Activiteiten & Volgende Acties")

    st.subheader("Periodefilter")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", value=date.today().replace(day=1), key="start")
    with col2:
        end_date = st.date_input("Einddatum", value=date.today(), key="end")

    if start_date > end_date:
        st.warning("Startdatum ligt na de einddatum.")

    df_activities = search_read(
        'mail.activity',
        domain=[],
        fields=['id', 'related_model_instance', 'res_id', 'res_model', 'user_id', 'activity_type_id', 'date_deadline',
                'summary', 'note', 'state'],
        context={'lang': 'en_GB'},
        limit=5000
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
    else:
        df_activities['date_deadline'] = pd.to_datetime(df_activities['date_deadline'], errors='coerce')
        df_activities = df_activities[
            (df_activities['date_deadline'].dt.date >= start_date) &
            (df_activities['date_deadline'].dt.date <= end_date)
            ]

        if df_activities.empty:
            st.warning(f"Geen activiteiten voor gekozen periode.")
        else:
            df_activities['note'] = df_activities['note'].apply(strip_html)
            df_activities['user'] = df_activities['user_id'].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) == 2 else str(x))
            df_activities['type'] = df_activities['activity_type_id'].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) == 2 else str(x))
            df_activities['deadline'] = pd.to_datetime(df_activities['date_deadline']).dt.date

            st.subheader("Geplande activiteiten")
            planned = df_activities[df_activities['state'] == 'planned']
            st.dataframe(planned[['res_model', 'Record Naam', 'user', 'deadline', 'summary', 'note']])

            st.subheader("Overdue Activiteiten")
            missed = df_activities[
                (df_activities['state'] == 'overdue') & (df_activities['deadline'] < datetime.now().date())]
            st.dataframe(missed[['res_model', 'Record Naam', 'user', 'deadline', 'summary', 'note']])

            # Bepaal 'today' als aparte status
            today = datetime.now().date()
            df_activities['state_clean'] = df_activities.apply(
                lambda row: 'today' if row['state'] == 'planned' and row['deadline'] == today
                else row['state'],
                axis=1
            )

            # Maak een overzichtstabel: aantal per user en state
            user_summary = (
                df_activities
                .groupby(['user', 'state_clean'])
                .size()
                .unstack(fill_value=0)
                .reset_index()
                .rename_axis(None, axis=1)
            )

            for col in ['planned', 'overdue', 'today']:
                if col not in user_summary.columns:
                    user_summary[col] = 0

            user_summary['Totaal'] = user_summary[['planned', 'overdue', 'today']].sum(axis=1)
            user_summary = user_summary.sort_values(by='Totaal', ascending=False)

            # Gebruikerslijst voor filter
            gebruikers = user_summary['user'].dropna().unique().tolist()
            # Eén gebruiker selecteren
            gekozen_gebruiker = st.selectbox("Selecteer gebruiker", ["Alle"] + gebruikers)

            # Filter toepassen
            if gekozen_gebruiker != "Alle":
                filtered_summary = user_summary[user_summary['user'] == gekozen_gebruiker]
            else:
                filtered_summary = user_summary

            # Toon de gefilterde user summary
            st.subheader("Aantal activiteiten per gebruiker (status)")
            st.dataframe(filtered_summary)