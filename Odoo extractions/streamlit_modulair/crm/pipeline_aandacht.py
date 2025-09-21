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
    st.title("Pipeline Aandachtspunten")

    # Datumfilter invoegen in sidebar
    start_date = st.sidebar.date_input("Startdatum", pd.Timestamp.now() - pd.Timedelta(days=90))
    end_date = st.sidebar.date_input("Einddatum", pd.Timestamp.now())

    if start_date > end_date:
        st.error("Startdatum mag niet na einddatum liggen.")
        st.stop()

    df_opportunities = search_read(
        'crm.lead',
        domain=[('type', '=', 'opportunity'), ('stage_id', '!=', 4)],
        fields=['id', 'active', 'name', 'user_id', 'stage_id', 'lost_reason', 'date_closed', 'date_last_stage_update',
                'company_id', 'country_id', 'expected_revenue', 'probability', 'x_studio_result_responsable'],
        context={'lang': 'en_GB'}
    )

    if df_opportunities.empty:
        st.warning("Geen actieve opportunities gevonden.")
        st.stop()

    # Datumkolom naar datetime
    df_opportunities['date_closed'] = pd.to_datetime(df_opportunities['date_closed'], errors='coerce')

    # Filteren op geselecteerde periode
    df_opportunities = df_opportunities[
        (df_opportunities['date_closed'].isna()) |  # optioneel: ook open opportunities zonder sluitdatum
        ((df_opportunities['date_closed'] >= pd.Timestamp(start_date)) & (
                df_opportunities['date_closed'] <= pd.Timestamp(end_date)))
        ]

    lead_ids = df_opportunities['id'].tolist()

    if not lead_ids:
        st.warning("Geen opportunities gevonden in de geselecteerde periode.")
        st.stop()

    # Haal mail.activities op
    df_activities = search_read(
        'mail.activity',
        domain=[('res_model', '=', 'crm.lead'), ('res_id', 'in', lead_ids)],
        fields=['id', 'res_id', 'state', 'user_id', 'date_deadline', 'date_done']
    )

    # Haal mail.messages op
    df_messages = search_read(
        'mail.message',
        domain=[('model', '=', 'crm.lead'), ('res_id', 'in', lead_ids)],
        fields=['id', 'res_id', 'date']
    )

    if df_activities.empty and df_messages.empty:
        st.warning("Niet genoeg data voor opvolganalyse.")
        st.stop()

    # Gemiddeld aantal activiteiten per opportunity
    activity_counts = df_activities.groupby('res_id').size().reset_index(name='Aantal activiteiten')
    opp_activity = df_opportunities[['id', 'name']].merge(activity_counts, how='left', left_on='id',
                                                          right_on='res_id').fillna(0)

    st.header("Opvolganalyse van Opportunities")
    avg_activities = opp_activity['Aantal activiteiten'].mean()
    st.write(f"Gemiddeld aantal activiteiten: **{avg_activities:.2f}**")
    st.dataframe(opp_activity[['name', 'Aantal activiteiten']].sort_values('Aantal activiteiten', ascending=False))

    # Datum kolommen omzetten naar datetime
    df_activities['date_done'] = pd.to_datetime(df_activities['date_done'], errors='coerce')
    df_activities['date_deadline'] = pd.to_datetime(df_activities['date_deadline'], errors='coerce')
    df_messages['date'] = pd.to_datetime(df_messages['date'], errors='coerce')

    # Laatste activiteitdatum per lead (max van date_done en date_deadline)
    last_activity_done = df_activities.groupby('res_id')[['date_done', 'date_deadline']].max()
    last_activity_done['last_activity_date'] = last_activity_done.max(axis=1)

    # Laatste berichtdatum per lead
    last_message_date = df_messages.groupby('res_id')['date'].max().to_frame('last_message_date')

    # Combineren activiteit en bericht
    last_contact = last_activity_done[['last_activity_date']].merge(last_message_date, left_index=True,
                                                                    right_index=True, how='outer')

    # Meest recente contactdatum (activiteit of bericht)
    last_contact['most_recent_contact'] = last_contact.max(axis=1)

    # Samenvoegen met opportunities
    df_opportunities = df_opportunities.set_index('id')
    opp_contact = df_opportunities.join(last_contact[['most_recent_contact']])

    # Detecteer stagnatie (geen contact in 7 dagen)
    stagnation_days = 7
    cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=stagnation_days)
    stagnant_opp = opp_contact[
        (opp_contact['most_recent_contact'].isna()) | (opp_contact['most_recent_contact'] < cutoff_date)]

    st.subheader(f"Opportunities zonder contact in de laatste {stagnation_days} dagen (activiteit of bericht)")
    st.dataframe(
        stagnant_opp.reset_index()[['name', 'most_recent_contact']].rename(
            columns={'name': 'Opportunity', 'most_recent_contact': 'Laatste contactdatum'}
        )
    )

    # Regio & Segment Analyse
    st.header("Regio- & Segmentanalyse van Pipeline")

    df_opportunities_filtered = df_opportunities[df_opportunities['probability'] > 0].copy()

    def extract_country_name(x):
        if isinstance(x, (list, tuple)) and len(x) == 2:
            return x[1]
        elif pd.isna(x):
            return 'Onbekend'
        else:
            return str(x)

    df_opportunities_filtered['country'] = df_opportunities_filtered['country_id'].apply(extract_country_name)

    if df_opportunities_filtered.index.name == 'id':
        df_opportunities_filtered = df_opportunities_filtered.reset_index()

    country_group = df_opportunities_filtered.groupby('country').agg({
        'id': 'count',
        'expected_revenue': 'sum',
        'probability': 'mean'
    }).reset_index().rename(columns={
        'id': 'Aantal kansen',
        'expected_revenue': 'Totaal verwachte waarde',
        'probability': 'Gem. slagingskans'
    })

    fig4 = px.bar(
        country_group,
        x='country',
        y='Totaal verwachte waarde',
        title='Verwachte waarde per land',
        text='Totaal verwachte waarde'
    )

    fig4.update_traces(texttemplate='€ %{text:,.0f}', textposition='outside')
    fig4.update_layout(
        yaxis=dict(
            tickprefix='€ ',
            separatethousands=True,
            showgrid=True,
            range=[0, 6500000]
        )
    )

    st.plotly_chart(fig4, use_container_width=True)