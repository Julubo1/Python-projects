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
    st.title("Activiteiten & Berichten Overzicht per Record")

    model_mapping = {
        "CRM": "crm.lead",
        "Sales": "sale.order",
        "Purchase": "purchase.order",
        "Repair": "repair.order"
    }
    module = st.selectbox("Kies module", list(model_mapping.keys()))

    col1, col2 = st.columns(2)
    with col1:
        record_id = st.text_input("Record ID (optioneel)")
    with col2:
        record_name = st.text_input("Record Naam (optioneel)")

    if st.button("Overzicht ophalen"):

        if not record_id and not record_name:
            st.error("Vul minstens een Record ID of Record Naam in.")
            st.stop()

        model = model_mapping[module]

        domain = []
        if record_id:
            try:
                record_id_int = int(record_id)
            except ValueError:
                st.error("Record ID moet een getal zijn.")
                st.stop()
            domain = [('id', '=', record_id_int)]
        elif record_name:
            domain = [('name', '=', record_name)]

        record_data = pd.DataFrame(search_read(model, domain=domain, fields=['id', 'name']))
        if record_data.empty:
            st.warning("Geen record gevonden met deze ID of Naam.")
            st.stop()

        record = record_data.iloc[0]
        rec_id = int(record['id'])  # altijd int maken
        rec_name = record.get('name', '')

        st.subheader(f"Record gevonden: {model} ID {rec_id} - {rec_name}")

        # Activiteiten ophalen
        activities = search_read(
            'mail.activity',
            domain=[('res_model', '=', model), ('res_id', '=', rec_id)],
            fields=['id', 'activity_type_id', 'summary', 'user_id', 'create_date', 'date_deadline', 'state',
                    'date_done']
        )

        df_activities = pd.DataFrame(activities)
        if not df_activities.empty:
            df_activities['activity_type'] = df_activities['activity_type_id'].apply(
                lambda x: x[1] if isinstance(x, list) else '')
            df_activities['user'] = df_activities['user_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            df_activities['create_date'] = pd.to_datetime(df_activities['create_date'], errors='coerce')
            df_activities['date_deadline'] = pd.to_datetime(df_activities['date_deadline'], errors='coerce')
            df_activities['date_done'] = pd.to_datetime(df_activities['date_done'], errors='coerce')

            df_activities = df_activities.sort_values('create_date', ascending=True)

            st.subheader("Activiteiten")
            st.dataframe(df_activities[
                             ['create_date', 'date_deadline', 'date_done', 'state', 'activity_type', 'summary',
                              'user']])
        else:
            st.info("Geen activiteiten gevonden voor dit record.")

        # Berichten ophalen
        messages = search_read(
            'mail.message',
            domain=[('model', '=', model), ('res_id', '=', rec_id)],
            fields=['id', 'author_id', 'date', 'body', 'subject', 'message_type', 'subtype_id']
        )
        df_messages = pd.DataFrame(messages)
        if not df_messages.empty:
            df_messages['author'] = df_messages['author_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
            df_messages['date'] = pd.to_datetime(df_messages['date'], errors='coerce')
            df_messages = df_messages.sort_values('date', ascending=True)
            df_messages['body_short'] = df_messages['body'].str.slice(0, 200).apply(strip_html).str.replace('\n', ' ',
                                                                                                            regex=False)
            df_messages['subject'] = df_messages['subject'].apply(
                lambda x: x[1] if isinstance(x, (list, tuple)) else str(x))

            st.subheader("Berichten")
            st.dataframe(df_messages[['date', 'author', 'subject', 'message_type', 'body_short']])
        else:
            st.info("Geen berichten gevonden voor dit record.")
