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

from shared.core import get_team_name_by_user,extract_hours,get_calendar_name,search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping,get_label, extract_country_name


def get_employee_workweeks(search_read_func):
    # Haal medewerkers en benodigde velden op
    df_employees = search_read_func('hr.employee',domain = [('active', 'in', [True, False])], fields=['id', 'name', 'resource_calendar_id'])
    if df_employees.empty:
        return pd.DataFrame()

    # Kalendernaam extractie (zoals nu in fte.py)
    def get_calendar_name(val):
        if isinstance(val, (list, tuple)) and len(val) > 1:
            return val[1]
        return ''

    df_employees['calendar_name'] = df_employees['resource_calendar_id'].apply(get_calendar_name)

    # Extract hours
    def extract_hours(name):
        if not isinstance(name, str):
            return 40.0
        import re
        m = re.search(r'(\d+)\s*Hours', name, re.IGNORECASE)
        return float(m.group(1)) if m else 40.0

    df_employees['werkweek_uren'] = df_employees['calendar_name'].apply(extract_hours)
    df_employees['FTE'] = df_employees['werkweek_uren'] / 40.0

    return df_employees[['id', 'name', 'resource_calendar_id', 'calendar_name', 'werkweek_uren', 'FTE']]


def show():
    st.header("FTE Overzicht per Team")

    # 1. Haal gebruikers (res.users) en medewerkers (hr.employee) op
    df_users = search_read('res.users', fields=['id', 'employee_ids'])
    df_employees = search_read('hr.employee', fields=['id', 'name', 'resource_calendar_id'])

    if df_users.empty or df_employees.empty:
        st.info("Geen gebruikers of medewerkers gevonden.")
        st.stop()

    # 2. Maak user_id → employee_id mapping (eerste employee_id als lijst)
    user_employee_map = {}
    for _, row in df_users.iterrows():
        emp_ids = row.get('employee_ids', [])
        if isinstance(emp_ids, list) and len(emp_ids) > 0:
            user_employee_map[row['id']] = emp_ids[0]
        else:
            user_employee_map[row['id']] = None

    # 3. Maak inverse mapping employee_id → user_id
    employee_user_map = {v: k for k, v in user_employee_map.items() if v is not None}

    # 4. Voeg user_id toe aan df_employees via mapping
    df_employees['user_id'] = df_employees['id'].map(employee_user_map)

    # 5. Haal crm teams op met member_ids (user_ids)
    df_teams = search_read('crm.team', fields=['id', 'name', 'member_ids'])
    if df_teams.empty:
        st.info("Geen CRM teams gevonden.")
        st.stop()

    # Maak team map: team_id → {'name': ..., 'users': [...]}
    team_users_map = {}
    for _, row in df_teams.iterrows():
        user_ids = []
        if isinstance(row['member_ids'], list):
            # member_ids kan lijst tuples zijn (id, name) of lijst ints
            if len(row['member_ids']) > 0 and isinstance(row['member_ids'][0], (list, tuple)):
                user_ids = [u[0] for u in row['member_ids']]
            else:
                user_ids = row['member_ids']
        team_users_map[row['id']] = {'name': row['name'], 'users': user_ids}

    # 6. Dropdown met team keuzes, incl. 'Geen Team'
    team_options = ['Geen Team'] + sorted({v['name'] for v in team_users_map.values()})
    selected_team_name = st.selectbox("Selecteer team", options=team_options)

    # 7. Filter medewerkers op geselecteerd team
    if selected_team_name != 'Geen Team':
        # Zoek team_id op naam
        selected_team_id = next((k for k, v in team_users_map.items() if v['name'] == selected_team_name), None)
        if selected_team_id:
            team_user_ids = team_users_map[selected_team_id]['users']  # user_ids
            # Zoek employee_ids behorend bij deze user_ids
            team_employee_ids = [user_employee_map[uid] for uid in team_user_ids if
                                 uid in user_employee_map and user_employee_map[uid] is not None]
            df_filtered = df_employees[df_employees['id'].isin(team_employee_ids)]
        else:
            df_filtered = pd.DataFrame(columns=df_employees.columns)
    else:
        df_filtered = df_employees.copy()

    st.write(f"Aantal medewerkers in selectie: {len(df_filtered)}")
    if df_filtered.empty:
        st.info("Geen medewerkers gevonden voor deze selectie.")
        st.stop()

    # 8. Kalendernaam toevoegen uit resource_calendar_id (meestal (id, naam))
    def get_calendar_name(val):
        if isinstance(val, (list, tuple)) and len(val) > 1:
            return val[1]
        return ''

    df_filtered['Calendar Name'] = df_filtered['resource_calendar_id'].apply(get_calendar_name)

    # 9. Uren uit kalendernaam extraheren (bv. '40 Hours')
    def extract_hours(name):
        if not isinstance(name, str):
            return 40.0
        match = re.search(r'(\d+)\s*Hours', name, re.IGNORECASE)
        if match:
            return float(match.group(1))
        else:
            return 40.0

    df_filtered['Werkweek uren'] = df_filtered['Calendar Name'].apply(extract_hours)
    df_filtered['FTE'] = df_filtered['Werkweek uren'] / 40.0

    # 10. Voeg teamnaam toe aan gefilterde medewerkers (via user_id)
    def get_team_name_by_user(user_id):
        if user_id is None:
            return 'Geen Team'
        for team in team_users_map.values():
            if user_id in team['users']:
                return team['name']
        return 'Geen Team'

    df_filtered['Team'] = df_filtered['user_id'].apply(get_team_name_by_user)

    # 11. Aggregatie per team
    df_agg = df_filtered.groupby('Team').agg(
        Aantal_medewerkers=('id', 'count'),
        Totaal_FTE=('FTE', 'sum'),
        Gemiddeld_FTE=('FTE', 'mean')
    ).reset_index()

    # 12. Tonen in Streamlit
    st.subheader("FTE per Team")
    st.dataframe(df_agg.style.format({
        'Totaal_FTE': '{:.2f}',
        'Gemiddeld_FTE': '{:.2f}'
    }), use_container_width=True)

    st.subheader("Medewerkers Detail")
    st.dataframe(
        df_filtered[['name', 'Team', 'Calendar Name', 'Werkweek uren', 'FTE']].rename(columns={'name': 'Medewerker'}),
        use_container_width=True
    )


