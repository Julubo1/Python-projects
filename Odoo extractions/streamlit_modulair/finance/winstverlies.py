import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from shared.core import search_read

def show():
    st.title("Winst & Verlies Overzicht")

    # Data ophalen: account.move voor klantfacturen en kostenfacturen
    domain = [
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']),
        ('payment_state', '=', 'paid'),
        ('partner_id', 'not ilike', 'PEO B.V'),
        ('partner_id', 'not ilike', 'PEO Holding')
    ]

    fields = [
        'date', 'move_type', 'amount_untaxed', 'amount_total', 'partner_id',
        'payment_state', 'team_id', 'ref', 'name', 'company_id'
    ]

    moves = search_read(
        'account.move',
        domain=domain,
        fields=fields,
        context={'lang': 'en_GB'}
    )
    if moves.empty:
        st.info("Geen financiële gegevens gevonden.")
        st.stop()

    df = pd.DataFrame(moves)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # === Nieuw: filter per company ===
    df['company_name'] = df['company_id'].apply(lambda x: x[1] if isinstance(x, list) else None)
    companies = sorted(df['company_name'].dropna().unique())
    company_selected = st.selectbox("Selecteer Company", options=companies)

    if company_selected:
        df = df[df['company_name'] == company_selected]

    # === Filter opties: datum bereik ===
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()
    start_date, end_date = st.date_input(
        "Selecteer periode",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    df = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]

    # === Filter optie: verkoopteam ===
    df['team_name'] = df['team_id'].apply(lambda x: x[1] if isinstance(x, list) else None)
    teams = sorted([t for t in df['team_name'].dropna().unique()])
    teams_selected = st.multiselect("Selecteer Verkoopteam(s)", options=teams, default=teams)

    if teams_selected:
        df = df[df['team_name'].isin(teams_selected)]

    # Categoriseren: omzet en kosten
    def categorize_move(row):
        if row['move_type'] in ['out_invoice', 'out_refund']:
            return 'Omzet'
        elif row['move_type'] in ['in_invoice', 'in_refund']:
            return 'Kosten'
        else:
            return 'Onbekend'

    df['categorie'] = df.apply(categorize_move, axis=1)

    # Omzet positief, kosten negatief maken
    df['bedrag'] = df['amount_total']
    df.loc[df['move_type'].isin(['out_refund', 'in_refund']), 'bedrag'] *= -1
    df.loc[df['categorie'] == 'Kosten', 'bedrag'] *= -1

    # Groeperen per categorie
    overzicht = df.groupby('categorie')['bedrag'].sum().reset_index()

    omzet = overzicht.loc[overzicht['categorie'] == 'Omzet', 'bedrag'].sum()
    kosten = overzicht.loc[overzicht['categorie'] == 'Kosten', 'bedrag'].sum()
    bruto_winst = omzet + kosten

    st.subheader("Samenvatting")
    st.metric("Omzet totaal", f"€ {omzet:,.2f}")
    st.metric("Kosten totaal", f"€ {kosten:,.2f}")
    st.metric("Bruto winst", f"€ {bruto_winst:,.2f}")

    # Visualisatie
    fig = px.bar(
        overzicht,
        x='categorie',
        y='bedrag',
        labels={'categorie': 'Categorie', 'bedrag': 'Bedrag (€)'},
        title=f'Omzet en Kosten Overzicht - {company_selected}',
        text='bedrag'
    )
    fig.update_traces(texttemplate='€ %{text:,.2f}', textposition='outside')
    fig.update_layout(yaxis_tickprefix='€ ', yaxis_tickformat=',.2f', uniformtext_minsize=8)
    st.plotly_chart(fig, use_container_width=True)

    # Detailtabel transacties
    st.subheader("Details per Transactie")
    df_display = df[['date', 'name', 'partner_id', 'categorie', 'bedrag',
                     'team_name', 'payment_state', 'company_name']].copy()
    df_display['date'] = df_display['date'].dt.strftime('%Y-%m-%d')
    df_display['partner'] = df_display['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else None)
    df_display['bedrag'] = df_display['bedrag'].apply(lambda x: f"€ {x:,.2f}")
    df_display = df_display.rename(columns={
        'date': 'Datum',
        'name': 'Factuur',
        'partner': 'Relatie',
        'categorie': 'Categorie',
        'bedrag': 'Bedrag',
        'team_name': 'Team',
        'payment_state': 'Betaalstatus',
        'company_name': 'Company'
    })
    df_display = df_display.drop(columns=['partner_id'])
    st.dataframe(df_display.sort_values('Datum', ascending=False), use_container_width=True)
