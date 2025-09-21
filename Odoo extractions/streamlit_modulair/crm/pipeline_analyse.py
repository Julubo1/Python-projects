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
    st.title("Pipeline Analyse")

    # Datumfilter
    #col1, col2 = st.columns(2)
    #with col1:
    #    start_date = st.date_input("Startdatum", value=datetime.today().replace(day=1))
    #with col2:
    #    end_date = st.date_input("Einddatum", value=datetime.today())

    #if start_date > end_date:
    #    st.error("Startdatum mag niet na einddatum liggen.")
    #    st.stop()

    df_leads = search_read(
        'crm.lead',
        domain=[('type', '=', 'opportunity'), ('stage_id.fold', '=', False)],
        fields=[
            'id', 'name', 'stage_id', 'user_id', 'probability', 'expected_revenue',
            'create_date', 'write_date', 'x_studio_result_responsable', 'date_last_stage_update', 'quotation_count',
            'partner_id'
        ],
        context={'lang': 'en_GB'}
    )

    if df_leads.empty:
        st.info("Geen open opportunities gevonden.")
    else:
        # Zet create_date en write_date om naar datetime.date
        df_leads['create_date'] = pd.to_datetime(df_leads['create_date'], errors='coerce').dt.date
        df_leads['write_date'] = pd.to_datetime(df_leads['write_date'], errors='coerce').dt.date

        # Filter op datumrange: create_date of write_date binnen de gekozen periode
        #mask = (
        #               (df_leads['create_date'] >= start_date) & (df_leads['create_date'] <= end_date)
        #       ) | (
        #               (df_leads['write_date'] >= start_date) & (df_leads['write_date'] <= end_date)
        #       )
        #df_leads = df_leads.loc[mask]

        # Filter gesloten/verloren stages eruit
        df_leads = df_leads[
            df_leads['stage_id'].apply(lambda x: x and x[0] != 4 and x[1].lower() != 'lost')
        ]

        if df_leads.empty:
            st.warning(f"Geen relevante opportunities gevonden tussen {start_date} en {end_date}.")
        else:
            unique_stage_ids = list({x[0] for x in df_leads['stage_id'] if x})
            unique_user_ids = list({x[0] for x in df_leads['x_studio_result_responsable'] if x})

            stage_dict = get_translated_names('crm.stage', unique_stage_ids)
            user_dict = get_translated_names('res.users', unique_user_ids)

            df_leads['stage'] = df_leads['stage_id'].apply(
                lambda x: stage_dict.get(x[0], 'Onbekend') if x else 'Onbekend')
            df_leads['Result Responsible'] = df_leads['x_studio_result_responsable'].apply(
                lambda x: user_dict.get(x[0], 'Onbekend') if x else 'Onbekend')
            df_leads['Customer'] = df_leads['partner_id'].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) == 2 else 'Onbekend')

            df_leads['date_last_stage_update'] = pd.to_datetime(df_leads['date_last_stage_update'], errors='coerce')
            today = pd.Timestamp('today').normalize()

            df_leads['create_date'] = pd.to_datetime(df_leads['create_date'], errors='coerce')
            today = pd.Timestamp('today').normalize()

            df_leads['days_in_stage'] = (today - df_leads['date_last_stage_update']).dt.days
            df_leads['days_in_stage'] = df_leads['days_in_stage'].fillna(-1).astype(int)

            df_leads['days_open'] = (today - df_leads['create_date']).dt.days
            df_leads['days_open'] = df_leads['days_open'].fillna(-1).astype(int)

            # Visualisatie potentiële waarde per salesfase
            stage_sum = df_leads.groupby('stage')['expected_revenue'].sum().reset_index()

            st.subheader("Waarde per salesfase")
            fig3 = px.bar(stage_sum, x='stage', y='expected_revenue',
                          labels={'expected_revenue': 'Potentiële waarde (€)', 'stage': 'Salesfase'})
            st.plotly_chart(fig3, use_container_width=True)

            # Opportunities langer dan 30 dagen in fase
            stagnant = df_leads[df_leads['days_in_stage'] > 30]
            st.subheader("Opportunities met stagnatie (>30 dagen in fase)")
            st.dataframe(
                stagnant[['name', 'Customer', 'Result Responsible', 'stage', 'days_in_stage', 'quotation_count']])

            # Aantal dagen de opportunities al open staan.
            st.subheader("Duur openstaande opportunities (dagen)")
            st.dataframe(df_leads[['name', 'Customer', 'Result Responsible', 'stage', 'days_open', 'quotation_count']])