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
    st.title("Visits & Demo's - Toekomstig vs Verleden")

    activity_type_ids = {
        'visit': 46,
        'demo': 51
    }

    selected_types = st.multiselect(
        "Selecteer activity types",
        options=list(activity_type_ids.keys()),
        default=['visit', 'demo']
    )

    if not selected_types:
        st.warning("Selecteer minstens één activity type.")
        st.stop()

    selected_ids = [activity_type_ids[t] for t in selected_types]

    # Haal toekomstige activiteiten
    upcoming_activities = search_read(
        'mail.activity',
        domain=[
            ('activity_type_id', 'in', selected_ids),
            ('state', '!=', 'done'),
            ('active', '=', True)
        ],
        fields=[
            'id', 'res_model', 'res_id', 'activity_type_id',
            'summary', 'user_id', 'date_deadline', 'state'
        ]
    )
    # st.write("Upcoming activities raw data:", upcoming_activities)

    # Haal afgeronde activiteiten
    past_activities = search_read(
        'mail.activity',
        domain=[
            ('activity_type_id', 'in', selected_ids),
            ('state', '=', 'done'),
            ('active', '=', False)
        ],
        fields=[
            'id', 'res_model', 'res_id', 'activity_type_id',
            'summary', 'user_id', 'date_deadline', 'state'
        ]
    )
    # st.write("Past activities raw data:", past_activities)

    if not isinstance(upcoming_activities, pd.DataFrame):
        st.error("Ophalen van toekomstige activiteiten gaf geen DataFrame terug.")
        upcoming_activities = pd.DataFrame()

    if not isinstance(past_activities, pd.DataFrame):
        st.error("Ophalen van afgeronde activiteiten gaf geen DataFrame terug.")
        past_activities = pd.DataFrame()

    def fetch_record_names(df):
        record_names = {}

        if df.empty:
            return record_names

        if 'res_model' not in df.columns or 'res_id' not in df.columns:
            st.write("fetch_record_names: vereiste kolommen ontbreken")
            return record_names

        unique_pairs = set(zip(df['res_model'], df['res_id']))
        # st.write(f"Unieke model/id paren voor naam ophalen ({len(unique_pairs)}):", unique_pairs)

        for model, rec_id in unique_pairs:
            try:
                result = search_read(
                    model,
                    domain=[('id', '=', rec_id)],
                    fields=['name', 'display_name'],
                )
                if not result.empty:
                    rec = result.iloc[0]
                    name = rec.get('name') or rec.get('display_name') or 'Geen naam gevonden'
                else:
                    name = 'Geen naam gevonden'
            except Exception as e:
                name = f'Fout: {str(e)}'
                st.write(f"Fout bij ophalen naam voor {model} {rec_id}: {e}")

            record_names[(model, rec_id)] = name

        return record_names

    def to_df(data, label, record_names):
        # Zet lijst om naar DataFrame indien nodig
        if isinstance(data, list):
            if len(data) == 0:
                # st.write(f"Geen data voor label {label}")
                return pd.DataFrame()
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data
            if df.empty:
                # st.write(f"Geen data voor label {label}")
                return df
        else:
            # st.write(f"Data voor label {label} is geen lijst of DataFrame")
            return pd.DataFrame()

        if 'activity_type_id' in df.columns:
            df['activity_type_id'] = df['activity_type_id'].apply(
                lambda x: x[0] if isinstance(x, list) and len(x) > 0 else x)

        df['Datum'] = pd.to_datetime(df['date_deadline'], errors='coerce').dt.date
        df['Gebruiker'] = df['user_id'].apply(lambda x: x[1] if isinstance(x, list) and len(x) > 1 else str(x))

        def record_label(row):
            return f"{row['res_model']} ({row['res_id']}) = {record_names.get((row['res_model'], row['res_id']), 'Onbekend')}"

        df['Record'] = df.apply(record_label, axis=1)
        df['Samenvatting'] = df['summary']
        df['Status'] = label

        return df[['Datum', 'Gebruiker', 'Record', 'Samenvatting', 'Status']]

    record_names_upcoming = fetch_record_names(upcoming_activities)
    record_names_done = fetch_record_names(past_activities)

    df_upcoming = to_df(upcoming_activities, 'Toekomstig', record_names_upcoming)
    df_done = to_df(past_activities, 'Afgerond', record_names_done)

    st.subheader("Toekomstige Activiteiten")
    st.dataframe(df_upcoming, use_container_width=True)

    st.subheader("Afgeronde Activiteiten")
    st.dataframe(df_done, use_container_width=True)
    
