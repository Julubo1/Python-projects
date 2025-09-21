import streamlit as st
import pandas as pd
from datetime import datetime
from shared.core import search_read

def show():
    st.header("Projecten")



    # Projecten ophalen (geen limiet)
    df_project = search_read(
        'project.project',
        domain=[('active', '=', True)],
        fields=[
            'id', 'name', 'date_start', 'date', 'x_studio_many2one_field_h5V6V', 'x_studio_project_type'
        ],
        context={'lang': 'en_GB'},
        limit=5000
    )

    # Datumkolommen opschonen
    df_project['date_start'] = pd.to_datetime(df_project['date_start'], errors='coerce')
    df_project['date'] = pd.to_datetime(df_project['date'], errors='coerce')



    # Teamnaam fixen
    def fix_team_field(x):
        if isinstance(x, list):
            if len(x) > 1:
                return str(x[1])  # naam van team
            elif len(x) == 1:
                return str(x[0])
            else:
                return 'Geen team'
        elif isinstance(x, tuple):
            return str(x[1]) if len(x) > 1 else str(x[0])
        elif isinstance(x, dict):
            return x.get('name', 'Geen team')
        elif x is None:
            return 'Geen team'
        return str(x)

    df_project['team_str'] = df_project['x_studio_many2one_field_h5V6V'].apply(fix_team_field)
    df_project['team_str'] = df_project['team_str'].replace('', 'Geen team')

    # Projecttype fixen
    def fix_type_field(x):
        if isinstance(x, list) and len(x) > 1:
            return x[1]
        return str(x) if x is not None else ''

    df_project['project_type_str'] = df_project['x_studio_project_type'].apply(fix_type_field)

    # Jaarkiezer op basis van alle unieke startjaren
    all_years = pd.concat([
        df_project['date_start'].dropna().dt.year,
        df_project['date'].dropna().dt.year
    ]).unique()
    year_options = sorted(all_years)
    selected_year = st.selectbox("Selecteer Jaar", options=year_options, index=len(year_options) - 1)

    # Filter op geselecteerd jaar (project start of loopt in dat jaar)
    year_start = pd.Timestamp(f"{selected_year}-01-01")
    year_end = pd.Timestamp(f"{selected_year}-12-31")

    mask = (
            ((df_project['date_start'] >= year_start) & (df_project['date_start'] <= year_end)) |
            ((df_project['date_start'] <= year_end) & (df_project['date'].isna() | (df_project['date'] >= year_start)))
    )
    df_events = df_project[mask].copy()

    # Teamfilter
    teams = sorted(df_events['team_str'].dropna().unique())
    selected_team = st.selectbox("Selecteer Team", options=["Alle"] + teams)
    if selected_team != "Alle":
        df_events = df_events[df_events['team_str'] == selected_team]

    # Projecttype-filter
    project_types = sorted(df_events['project_type_str'].dropna().unique())
    selected_type = st.selectbox("Selecteer Projecttype", options=["Alle"] + project_types)
    if selected_type != "Alle":
        df_events = df_events[df_events['project_type_str'] == selected_type]

    # Project zoekfunctie
    project_search = st.text_input("Zoek op project (min. 2 letters)").strip()
    if len(project_search) >= 2:
        df_events = df_events[df_events["name"].str.contains(project_search, case=False, na=False)]

    st.subheader("Detailoverzicht Projecten")
    display_cols = ['name', 'project_type_str', 'date_start', 'date', 'team_str']
    display_df = df_events[display_cols].sort_values('date_start').rename(columns={
        'name': 'Project Naam',
        'project_type_str': 'Project type',
        'date_start': 'Startdatum',
        'date': 'Einddatum',
        'team_str': 'Business Line'
    })
    st.dataframe(display_df)
