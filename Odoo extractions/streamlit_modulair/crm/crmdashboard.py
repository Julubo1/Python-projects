import streamlit as st
import pandas as pd
from shared.core import search_read, get_translated_names

def show():
    st.title("CRM Dashboard")

    # --- Data ophalen ---
    try:
        df_all = search_read(
            'crm.lead',
            domain=[('type', '=', 'opportunity')],
            fields=[
                'id', 'name', 'stage_id',
                'probability',
                'expected_revenue', 'prorated_revenue',
                'create_date', 'write_date',
                'x_studio_result_responsable', 'date_last_stage_update',
                'quotation_count', 'partner_id',
                'day_open',
                'days_to_convert',
                'day_close'
            ],
            context={'lang': 'en_GB'}
        )
    except Exception as e:
        st.error(f"Fout bij ophalen data van crm.lead: {e}")
        return

    if df_all.empty:
        st.info("Geen opportunities gevonden.")
        return

    # --- Datumkolommen naar datetime ---
    date_cols = ['create_date', 'write_date', 'date_last_stage_update']
    for col in date_cols:
        df_all[col] = pd.to_datetime(df_all[col], errors='coerce')

    # --- Jaar en maand filter ---
    available_years = sorted(df_all['create_date'].dt.year.dropna().unique(), reverse=True)
    selected_year = st.selectbox("Selecteer jaar", available_years, index=0)

    months_in_year = df_all[df_all['create_date'].dt.year == selected_year]['create_date'].dt.month.unique()
    month_names = {
        1: "Januari", 2: "Februari", 3: "Maart", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Augustus", 9: "September", 10: "Oktober", 11: "November", 12: "December"
    }
    available_months = sorted(months_in_year)
    selected_month = st.selectbox(
        "Selecteer maand",
        available_months,
        format_func=lambda m: month_names[m]
    )

    # Filter op gekozen jaar en maand
    df = df_all[
        (df_all['create_date'].dt.year == selected_year) &
        (df_all['create_date'].dt.month == selected_month)
    ]

    if df.empty:
        st.warning(f"Geen relevante opportunities gevonden in {month_names[selected_month]} {selected_year}.")
        return

    # --- Hulpfuncties voor veilige extractie ---
    # Functie om ID te pakken
    def get_id(x):
        if isinstance(x, (list, tuple)) and len(x) > 0:
            return x[0]
        return None

    # Functie om naam te pakken
    def get_name(x):
        if isinstance(x, (list, tuple)) and len(x) > 1:
            return x[1]
        elif isinstance(x, str):
            return x
        else:
            return 'Onbekend'

    # Stage ID's extraheren
    df['stage_id_raw'] = df['stage_id'].apply(get_id)

    # Dictionary ophalen met de ID's
    stage_dict = get_translated_names('crm.stage', df['stage_id_raw'].dropna().unique().tolist())

    # Maak een functie die eerst dictionary lookup probeert, anders fallback naar naam uit data
    def get_stage_name(row):
        id_ = row['stage_id_raw']
        dict_name = stage_dict.get(id_, None)
        if dict_name:
            return dict_name
        # fallback naar naam uit originele stage_id veld
        return get_name(row['stage_id'])

    df['Stage'] = df.apply(get_stage_name, axis=1)

    def clean_odoo_field(val):
        if isinstance(val, list):
            return val[1] if len(val) > 1 else val[0]
        return val

    for col in ['stage_id', 'team_id', 'partner_id']:
        if col in df.columns:
            df[col] = df[col].apply(clean_odoo_field).astype(str)

    def safe_id(val):
        if isinstance(val, (list, tuple)) and len(val) >= 1:
            return val[0]
        return None

    def safe_name(val):
        if isinstance(val, (list, tuple)) and len(val) == 2:
            return val[1]
        if isinstance(val, str):
            return val
        return 'Onbekend'

    # --- IDs extraheren ---

    df['result_responsable_raw'] = df['x_studio_result_responsable'].apply(safe_id)

    # --- Dictionaries ophalen ---
    stage_dict = get_translated_names(
        'crm.stage',
        df['stage_id_raw'].dropna().unique().tolist()
    )
    user_dict = get_translated_names(
        'res.users',
        df['result_responsable_raw'].dropna().unique().tolist()
    )

    # --- Nieuwe leesbare kolommen ---
    df['Stage'] = df['stage_id_raw'].map(stage_dict).fillna('Onbekend')
    df['Result Responsible'] = df['result_responsable_raw'].map(user_dict).fillna('Onbekend')
    df['Customer'] = df['partner_id'].apply(safe_name)

    # --- Overbodige kolommen verwijderen ---
    df.drop(columns=['stage_id', 'x_studio_result_responsable'], inplace=True)

    # --- Days in current stage berekenen ---
    today = pd.Timestamp.today().normalize()
    df['days_in_stage'] = (
        today - pd.to_datetime(df['date_last_stage_update'], errors='coerce').fillna(today)
    ).dt.days

    # --- Kolomnamen aanpassen ---
    df.rename(columns={
        'day_open': 'days_to_assign',
        'day_close': 'days_to_close'
    }, inplace=True)

    # --- KPI sectie ---
    st.subheader(f"KPI's ({month_names[selected_month]} {selected_year})")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Gem. Days to Assign", round(df['days_to_assign'].mean(), 2))
    kpi2.metric("Gem. Days to Opportunity", round(df['days_to_convert'].mean(), 2))
    kpi3.metric("Gem. Days to Close", round(df['days_to_close'].mean(), 2))
    kpi4.metric("Totale Expected Revenue (€)", round(df['expected_revenue'].sum(), 2))
    kpi5.metric("Totale Prorated Revenue (€)", round(df['prorated_revenue'].sum(), 2))

    # --- Tabel & grafiek ---
    with st.expander("📊 Data tabel"):
        st.dataframe(df)

    st.subheader("Opportunities per Stage")
    stage_counts = df['Stage'].value_counts().reset_index()
    stage_counts.columns = ['Stage', 'Aantal']
    st.bar_chart(stage_counts.set_index('Stage'))
