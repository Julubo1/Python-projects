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
    st.title("Laatste Contact Activiteit per Bedrijf")

    # Contactpersonen ophalen
    contacts = search_read(
        'res.partner',
        domain=[('parent_id', '!=', False)],
        fields=['id', 'name', 'parent_id'],
    )

    df_contacts = pd.DataFrame(contacts)
    if df_contacts.empty:
        st.warning("Geen contactpersonen gevonden.")
        st.stop()

    # Parent (bedrijf) extraheren
    def extract_company(val):
        if isinstance(val, list) and len(val) > 1:
            return {'id': val[0], 'name': val[1]}
        return {'id': None, 'name': None}

    df_contacts['company'] = df_contacts['parent_id'].apply(extract_company)
    df_contacts['company_id'] = df_contacts['company'].apply(lambda x: x['id'])
    df_contacts['company_name'] = df_contacts['company'].apply(lambda x: x['name'])

    # Alle contact IDs
    contact_ids = df_contacts['id'].tolist()

    # Mail messages ophalen
    mail_messages = search_read(
        'mail.message',
        domain=[
            ('res_id', 'in', contact_ids),
            ('model', '=', 'res.partner'),
            ('message_type', 'in', ['comment', 'email']),
            ('subject', 'not ilike', 'archived')
        ],
        fields=['id', 'res_id', 'date', 'subject', 'body'],
    )

    df_messages = pd.DataFrame(mail_messages)
    df_messages['date'] = pd.to_datetime(df_messages['date'])

    # Laatste activiteit per contact
    latest_msg = df_messages.sort_values('date').groupby('res_id').tail(1)

    # Merge met contactpersonen
    df_result = pd.merge(df_contacts, latest_msg, left_on='id', right_on='res_id', how='left')

    # Laatste activiteit per bedrijf bepalen
    # Bewaar expliciet het contactpersoon ID
    df_result['contact_id'] = df_result['id_x']
    df_latest_per_company = df_result.sort_values('date').groupby('company_id').tail(1)

    # Mail activities ophalen (geplande acties)
    mail_activities = search_read(
        'mail.activity',
        domain=[('res_id', 'in', contact_ids), ('res_model', '=', 'res.partner')],
        fields=['res_id', 'date_deadline', 'summary', 'note'],
    )

    df_activities = pd.DataFrame(mail_activities)
    df_activities['date_deadline'] = pd.to_datetime(df_activities['date_deadline'])

    # Koppel geplande activiteit per contactpersoon
    df_activities_latest = df_activities.sort_values('date_deadline').groupby('res_id').tail(1)
    df_result_with_act = pd.merge(
        df_latest_per_company,
        df_activities_latest,
        left_on='contact_id', right_on='res_id',
        how='left',
        suffixes=('', '_planned')
    )

    df_result_with_act['body'] = df_result_with_act['body'].apply(strip_html)

    # Toon resultaat
    st.subheader("Bedrijven met laatste contactactiviteit")
    df_display = df_result_with_act[[
        'company_name', 'name', 'date', 'subject', 'body', 'date_deadline', 'summary', 'note'
    ]].rename(columns={
        'company_name': 'Bedrijf',
        'name': 'Laatste contact met',
        'date': 'Laatste Activiteit',
        'subject': 'Onderwerp',
        'body': 'Bericht',
        'date_deadline': 'Deadline Volgende Actie',
        'summary': 'Volgende Actie',
        'note': 'Toelichting'
    }).sort_values('Laatste Activiteit', ascending=False)

    st.dataframe(df_display, use_container_width=True)