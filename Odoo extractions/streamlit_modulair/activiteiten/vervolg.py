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
    st.title("Activiteiten & Vervolgacties")

    # Periode filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", value=datetime.today().replace(day=1))
    with col2:
        end_date = st.date_input("Einddatum", value=datetime.today())

    if start_date > end_date:
        st.error("Startdatum mag niet na einddatum liggen.")
        st.stop()

    if st.button("Activiteiten analyseren"):

        with st.spinner("Data ophalen uit Odoo..."):

            # Stap 1: activiteiten die zijn afgerond in deze periode
            done_activities = search_read(
                'mail.activity',
                domain=[('active', '=', False),
                        ('state', '=', 'done'),
                        ('date_done', '>=', str(start_date)),
                        ('date_done', '<=', str(end_date))
                        ],
                fields=[
                    'id', 'res_model', 'res_id', 'activity_type_id',
                    'summary', 'create_date', 'user_id', 'date_done'
                ]
            )

            df_done = pd.DataFrame(done_activities)
            if df_done.empty:
                st.info("Geen afgeronde activiteiten gevonden.")
                st.stop()

            def get_name(row):
                model = row['res_model']
                rid = row['res_id']
                return names_per_model.get(model, {}).get(rid, '')

            # Maak een lege dict om namen per model op te slaan
            names_per_model = {}

            # Haal alle unieke modellen op uit df_done
            unique_models_done = df_done['res_model'].unique()

            for model in unique_models_done:
                ids = df_done.loc[df_done['res_model'] == model, 'res_id'].unique().tolist()
                records = search_read(
                    model,
                    domain=[('id', 'in', ids)],
                    fields=['id', 'name']
                )
                df_names = pd.DataFrame(records)
                names_per_model[model] = df_names.set_index('id')['name'].to_dict()

            # Voeg helperkolommen toe
            df_done['activity_type'] = df_done['activity_type_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            df_done['user'] = df_done['user_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            df_done['date_done'] = pd.to_datetime(df_done['date_done'])
            df_done['res_uid'] = df_done['res_model'] + '/' + df_done['res_id'].astype(str)
            df_done['res_name'] = df_done.apply(get_name, axis=1)

            st.subheader(f"Afgeronde activiteiten ({len(df_done)})")
            st.dataframe(df_done[['date_done', 'res_name', 'user', 'activity_type', 'summary', 'res_model', 'res_id']])

            # Stap 2: check of er vervolgactiviteiten zijn aangemaakt op zelfde objecten (res_model/res_id)
            res_pairs = df_done[['res_model', 'res_id']].drop_duplicates().to_dict(orient='records')

            # Actieve activiteiten ophalen
            df_active = search_read(
                'mail.activity',
                domain=[('active', '=', True)],
                fields=['id', 'res_model', 'res_id', 'create_date', 'user_id', 'activity_type_id', 'summary', 'state']
            )
            if not isinstance(df_active, pd.DataFrame):
                df_active = pd.DataFrame(df_active)

            # Inactieve activiteiten ophalen
            df_inactive = search_read(
                'mail.activity',
                domain=[('active', '=', False)],
                fields=['id', 'res_model', 'res_id', 'create_date', 'user_id', 'activity_type_id', 'summary', 'state']
            )
            if not isinstance(df_inactive, pd.DataFrame):
                df_inactive = pd.DataFrame(df_inactive)

            # Combineer de DataFrames
            df_followup = pd.concat([df_active, df_inactive], ignore_index=True)

            if df_followup.empty:
                st.warning("Geen vervolgactiviteiten gevonden.")
            else:
                if 'create_date' not in df_followup.columns:
                    st.warning("Veld 'create_date' ontbreekt in opgehaalde data.")
                else:
                    df_followup = df_followup[df_followup['create_date'].notna()]
                    df_followup['create_date'] = pd.to_datetime(df_followup['create_date'], errors='coerce')
                    df_followup = df_followup[df_followup['create_date'].notna()]

                    # Filter op periode
                    df_followup = df_followup[
                        (df_followup['create_date'] >= pd.to_datetime(start_date)) &
                        (df_followup['create_date'] <= pd.to_datetime(end_date))
                        ]

                    # Voeg kolommen toe
                    df_followup['activity_type'] = df_followup['activity_type_id'].apply(
                        lambda x: x[1] if isinstance(x, list) else '')
                    df_followup['user'] = df_followup['user_id'].apply(
                        lambda x: x[1] if isinstance(x, list) else '')
                    df_followup['res_uid'] = df_followup['res_model'] + '/' + df_followup['res_id'].astype(str)

                    # Match op objecten van afgeronde activiteiten
                    done_uids = df_done['res_uid'].unique()
                    df_followup = df_followup[df_followup['res_uid'].isin(done_uids)]

                    # Haal alle unieke modellen op in je data
                    unique_models = df_followup['res_model'].unique()

                    for model in unique_models:
                        # Haal alle unieke res_id's voor dit model
                        ids = df_followup.loc[df_followup['res_model'] == model, 'res_id'].unique().tolist()

                        # Haal de namen op via search_read van Odoo, let op veld 'name' is meestal de display naam
                        records = search_read(
                            model,
                            domain=[('id', 'in', ids)],
                            fields=['id', 'name']
                        )
                        # Zet om naar DataFrame
                        df_names = pd.DataFrame(records)

                        # Sla op in dict per model, met id als key en name als value
                        names_per_model[model] = df_names.set_index('id')['name'].to_dict()

                    df_followup['res_name'] = df_followup.apply(get_name, axis=1)

                    st.subheader(f"Vervolgacties binnen dezelfde periode ({len(df_followup)})")
                    st.dataframe(
                        df_followup[
                            ['create_date', 'res_name', 'user', 'activity_type', 'summary', 'res_model', 'res_id',
                             'state']]
                    )
