import streamlit as st
import pandas as pd
from datetime import date, timedelta
from shared.core import search_read
from .fte import get_employee_workweeks

def show():
    st.header("Uitgebreide Verzuimanalyse met FTE-correctie")

    # --- Periode filter ---
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Startdatum", date.today() - timedelta(days=90))
    with col2:
        end_date = st.date_input("Einddatum", date.today())

    if start_date > end_date:
        st.warning("Startdatum kan niet na einddatum liggen.")
        st.stop()

    # --- Verloftypes ophalen ---
    df_leave_types = search_read('hr.leave.type', fields=['id', 'name'])
    if df_leave_types is None or df_leave_types.empty:
        st.error("Kan verloftypes niet ophalen.")
        st.stop()
    leave_type_dict = dict(zip(df_leave_types['id'], df_leave_types['name']))

    # Default selectie verloftypes (ziek)
    default_verzuim = [id for id, name in leave_type_dict.items() if 'Sick' in name or 'Ziek' in name]

    selected_verzuim_types = st.multiselect(
        "Selecteer verloftypes die als verzuim gelden",
        options=df_leave_types['id'],
        format_func=lambda x: leave_type_dict.get(x, str(x)),
        default=default_verzuim
    )
    if not selected_verzuim_types:
        st.info("Selecteer minimaal één verloftype als verzuim.")
        st.stop()

    # --- Verzuimregistraties ophalen ---
    domain = [
        ('holiday_status_id', 'in', selected_verzuim_types),
        ('state', 'in', ['validate', 'confirm']),
        ('request_date_from', '<=', end_date.strftime('%Y-%m-%d')),
        ('request_date_to', '>=', start_date.strftime('%Y-%m-%d')),
    ]

    df_verzuim = search_read(
        'hr.leave',
        domain=domain,
        fields=[
            'employee_id', 'holiday_status_id', 'request_date_from', 'request_date_to',
            'number_of_days', 'state', 'name'
        ]
    )
    if df_verzuim is None or df_verzuim.empty:
        st.info("Geen verzuimregistraties gevonden in de geselecteerde periode.")
        st.stop()

    # --- Data transformeren ---
    df_verzuim['Employee'] = df_verzuim['employee_id'].apply(lambda x: x[1] if isinstance(x, list) else str(x))
    df_verzuim['employee_id_only'] = df_verzuim['employee_id'].apply(lambda x: x[0] if isinstance(x, list) else x)
    df_verzuim['Leave Type'] = df_verzuim['holiday_status_id'].apply(
        lambda x: leave_type_dict.get(x[0] if isinstance(x, list) else x, 'Onbekend'))
    df_verzuim['From'] = pd.to_datetime(df_verzuim['request_date_from'], errors='coerce')
    df_verzuim['To'] = pd.to_datetime(df_verzuim['request_date_to'], errors='coerce')
    df_verzuim['Days'] = df_verzuim['number_of_days']
    df_verzuim['Status'] = df_verzuim['state'].map({'confirm': 'Te bevestigen', 'validate': 'Goedgekeurd'}).fillna(df_verzuim['state'])

    # Status filter interactief
    all_statuses = df_verzuim['Status'].unique().tolist()
    selected_statuses = st.multiselect("Filter op status (optioneel)", options=all_statuses, default=all_statuses)

    # Filter toepassen
    df_filtered = df_verzuim[
        (df_verzuim['Status'].isin(selected_statuses))
    ]

    # --- Medewerkers en FTE ophalen ---
    df_employees = get_employee_workweeks(search_read)
    if df_employees.empty:
        st.warning("Geen medewerkers met werkweekuren gevonden.")
        st.stop()

    # Filter medewerkers die voorkomen in verzuimdata
    df_employees = df_employees[df_employees['id'].isin(df_filtered['employee_id_only'].unique())]

    # Aantal kalenderweken in periode
    total_weeks = ((end_date - start_date).days + 1) / 7

    # Beschikbare werkdagen per medewerker = werkweken * werkdagen per week * FTE (werkweek_uren/40)
    # Werkdagen per week = 5, FTE is werkweek_uren / 40
    df_employees['Beschikbare werkdagen'] = total_weeks * 5 * df_employees['FTE']

    # --- Verzuim per medewerker ---
    verzuim_per_medewerker = df_filtered.groupby('employee_id_only')['Days'].sum().reset_index()
    verzuim_per_medewerker = verzuim_per_medewerker.rename(columns={'employee_id_only': 'id'})

    # Merge met medewerkersdata voor naam en beschikbare werkdagen
    verzuim_per_medewerker = verzuim_per_medewerker.merge(
        df_employees[['id', 'name', 'Beschikbare werkdagen']],
        on='id', how='left'
    )
    verzuim_per_medewerker.rename(columns={'name': 'Employee'}, inplace=True)

    # Verzuimpercentage per medewerker
    verzuim_per_medewerker['Verzuimpercentage'] = (verzuim_per_medewerker['Days'] / verzuim_per_medewerker['Beschikbare werkdagen']) * 100

    # Verzuimfrequentie (aantal meldingen)
    freq = df_filtered.groupby('employee_id_only').size().reset_index(name='Aantal meldingen').rename(columns={'employee_id_only': 'id'})
    verzuim_per_medewerker = verzuim_per_medewerker.merge(freq, on='id', how='left')

    # Sorteren
    verzuim_per_medewerker = verzuim_per_medewerker.sort_values(by='Verzuimpercentage', ascending=False)

    # --- Verzuim per verloftype ---
    verzuim_per_type = df_filtered.groupby('Leave Type')['Days'].sum().reset_index().sort_values(by='Days', ascending=False)

    # --- Verzuimtrend per week ---
    df_filtered['Week'] = df_filtered['From'].dt.to_period('W').apply(lambda r: r.start_time)
    verzuim_per_week = df_filtered.groupby('Week')['Days'].sum().reset_index()

    # --- Resultaten tonen ---
    st.subheader("Totaal verzuimregistraties")
    st.dataframe(df_filtered[['Employee', 'Leave Type', 'From', 'To', 'Days', 'Status']].sort_values(by='From').reset_index(drop=True))

    st.subheader("Verzuim per medewerker")
    st.dataframe(verzuim_per_medewerker[['Employee', 'Days', 'Verzuimpercentage', 'Aantal meldingen']])
    # --- Waarschuwingen tonen ---
    hoge_verzuim = verzuim_per_medewerker[verzuim_per_medewerker['Verzuimpercentage'] > 6]
    if not hoge_verzuim.empty:
        st.warning(f"Er zijn {len(hoge_verzuim)} medewerkers met een verzuimpercentage > 6% in deze periode.")

    st.subheader("Verzuimpercentage per medewerker")
    st.bar_chart(verzuim_per_medewerker.set_index('Employee')['Verzuimpercentage'])

    st.subheader("Aantal verzuimmeldingen per medewerker")
    st.bar_chart(verzuim_per_medewerker.set_index('Employee')['Aantal meldingen'])

    st.subheader("Verzuimtrend per week")
    st.line_chart(verzuim_per_week.set_index('Week')['Days'])



if __name__ == "__main__":
    show()