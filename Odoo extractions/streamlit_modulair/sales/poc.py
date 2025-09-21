import streamlit as st
import xmlrpc.client
import pandas as pd
from datetime import datetime, date, timedelta
import re
import io
import numpy as np
from dateutil import parser
import plotly.express as px
from streamlit_plotly_events import plotly_events
import requests
from rapidfuzz import fuzz, process

from shared.core import search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping,get_label, extract_country_name
def show():
    st.header("PO-C Received Overview")

    df_sales = search_read(
        'sale.order',
        domain=[('state', 'in', ['sale', 'done']),('client_order_ref', 'not ilike', 'call')],
        fields=[
            'name', 'x_studio_rd_poc', 'client_order_ref', 'team_id',
            'amount_untaxed', 'state', 'x_studio_datetime_field_FyIZ2', 'commitment_date', 'partner_id',
            'invoice_status', 'opportunity_id'
        ],
        context={'lang': 'en_GB'})

    df_repair = search_read(
        'repair.order',
        domain=[],
        fields=[
            'id',
            'name',
            'schedule_date',
            'company_id',
            'state',
            'amount_untaxed',
            'currency_id',
            'activity_ids',
            'create_date',
            'x_studio_order_date',
            'x_studio_customer_reference',
            'x_studio_many2one_field_maTCd',
            'partner_id'
        ],
        context={'lang': 'en_GB'})

    df_purchase = search_read(
        'purchase.order',
        domain=[],
        fields=[
            'id', 'name', 'state', 'origin'
        ],
        context={'lang': 'en_GB'})

    # ----------- SALES DATA -----------
    # ----------- SALES DATA -----------
    if not df_sales.empty:
        def extract_team_name(x):
            if isinstance(x, dict) and 'name' in x:
                return x['name']
            elif isinstance(x, list) and len(x) > 1:
                return x[1]
            elif isinstance(x, str):
                return x
            return None

        # Nieuwe kolom met teamnaam
        df_sales['Team'] = df_sales['team_id'].apply(extract_team_name)

        # Voor veilige visualisatie: zet team_id om naar string

        df_sales['team_id'] = df_sales['team_id'].astype(str)

        # Voor verwerking
        df_sales_copy = df_sales.copy()
        df_sales_copy['Module'] = 'Sales'
        df_sales_copy['POC Date'] = pd.to_datetime(df_sales_copy['x_studio_rd_poc'], errors='coerce')
        df_sales_copy['POC Reference'] = df_sales_copy['client_order_ref']
        df_sales_copy['Amount'] = df_sales_copy['amount_untaxed']
        df_sales_copy['Name'] = df_sales_copy['name']
        df_sales_copy['Opportunity'] = df_sales_copy['opportunity_id']
        df_sales_copy['Customer'] = df_sales_copy['partner_id']

        sales_df = df_sales_copy[
            ['Name', 'Customer', 'Opportunity', 'POC Date', 'POC Reference', 'Team', 'Amount', 'Module']]
    else:
        sales_df = pd.DataFrame(
            columns=['Name', 'Customer', 'Opportunity', 'POC Date', 'POC Reference', 'Team', 'Amount', 'Module'])

    # ----------- REPAIR DATA -----------
    if not df_repair.empty:
        df_repair_copy = df_repair.copy()
        df_repair_copy['Module'] = 'Repair'
        df_repair_copy['POC Date'] = pd.to_datetime(df_repair_copy['x_studio_order_date'], errors='coerce')
        df_repair_copy['POC Reference'] = df_repair_copy['x_studio_customer_reference']
        df_repair_copy['Team'] = df_repair_copy['x_studio_many2one_field_maTCd'].apply(extract_team_name)
        df_repair_copy['Amount'] = df_repair_copy[
            'amount_untaxed'] if 'amount_untaxed' in df_repair_copy.columns else None
        df_repair_copy['Name'] = df_repair_copy['name']
        df_repair_copy['Customer'] = df_repair_copy['partner_id']
        repair_df = df_repair_copy[['Name', 'Customer', 'POC Date', 'POC Reference', 'Team', 'Amount', 'Module']]
    else:
        repair_df = pd.DataFrame(columns=['Name', 'Customer', 'POC Date', 'POC Reference', 'Team', 'Amount', 'Module'])

    # ----------- COMBINEER -----------
    combined_df = pd.concat([sales_df, repair_df], ignore_index=True)

    # Filter alleen records met POC Date
    combined_df = combined_df[pd.notnull(combined_df['POC Date'])]

    # ----------- KOPPEL PURCHASE ORDER INFO -----------
    def normalize_order_name(name):
        if not isinstance(name, str) or not name.strip():
            return ''
        # Verwijder prefix letters aan het begin (bv SO1-, Q1-)
        name = re.sub(r'^[A-Za-z]+', '', name).strip()

        # Split op slash en pak het eerste deel, check of het bestaat
        parts = name.split('/')
        first_part = parts[0] if parts else ''

        # Split op spatie en pak het eerste deel, check of het bestaat
        subparts = first_part.split()
        first_subpart = subparts[0] if subparts else ''

        # Return uppercase en gestript
        return first_subpart.strip().upper()

    if not df_purchase.empty:
        df_purchase_copy = df_purchase.copy()
        df_purchase_copy['origin'] = df_purchase_copy['origin'].astype(str)
        df_purchase_copy['state'] = df_purchase_copy['state'].astype(str)

        # Maak genormaliseerde kolommen voor de merge
        combined_df['norm_Name'] = combined_df['Name'].apply(normalize_order_name)
        df_purchase_copy['norm_origin'] = df_purchase_copy['origin'].apply(normalize_order_name)

        # Neem slechts de eerste relevante PO state per origin
        df_purchase_copy = df_purchase_copy.sort_values(
            'state')  # optioneel: prioriteer 'done' boven 'purchase' boven 'draft'
        df_purchase_copy = df_purchase_copy.drop_duplicates(subset='norm_origin', keep='first')

        # Merge op de genormaliseerde kolommen
        combined_df = combined_df.merge(
            df_purchase_copy[['norm_origin', 'state']],
            how='left',
            left_on='norm_Name',
            right_on='norm_origin'
        )

        # Voeg kolom toe: PO ontbreekt of niet verzonden (state niet 'purchase' of 'done')
        combined_df['PO Missing or Not Sent'] = combined_df.apply(
            lambda row: (
                    pd.isnull(row['state']) or
                    (row['state'] not in ['purchase', 'done'])
            ),
            axis=1
        )

        # Helper kolommen opruimen
        combined_df.drop(columns=['norm_Name', 'norm_origin'], inplace=True)

    else:
        combined_df['PO Missing or Not Sent'] = True

    if combined_df.empty:
        st.info("Geen data met ingevulde POC Date beschikbaar.")
    else:
        # -------------------- Jaar & Maand afleiden --------------------
        combined_df['year'] = combined_df['POC Date'].dt.year
        combined_df['Month'] = combined_df['POC Date'].dt.month_name()
        combined_df['Month'] = pd.Categorical(combined_df['Month'], categories=[
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ], ordered=True)

        # -------------------- Filters --------------------
        teams = combined_df['Team'].dropna().unique().tolist()
        maanden = combined_df['Month'].dropna().unique().tolist()

        selected_teams = st.multiselect("Filter op Business Line", teams, default=teams)
        selected_months = st.multiselect("Filter op maand (POC Received)", options=maanden, default=maanden)

        # -------------------- Filter toepassen --------------------
        filtered = combined_df.copy()

        # Filter op jaar via eigen functie
        # Jaarfilter via jaarkiezer
        jaren = [2022, 2023, 2024, 2025, 2026]
        jaarkiezer = st.selectbox("Selecteer jaar:", options=jaren, index=len(jaren) - 1 if jaren else 0)

        filtered = filter_on_year(filtered, ['POC Date'], jaarkiezer)

        # Filter op team en maand
        filtered = filtered[filtered['Team'].isin(selected_teams)]
        filtered = filtered[filtered['Month'].isin(selected_months)]

        # -------------------- Tabel met regels --------------------
        display_df = filtered[
            ['Name', 'Opportunity', 'Customer', 'POC Date', 'POC Reference', 'Team', 'Amount', 'Module',
             'PO Missing or Not Sent']
        ].sort_values('POC Date', ascending=False)

        display_df['Customer'] = display_df['Customer'].apply(
            lambda x: ', '.join(map(str, x)) if isinstance(x, (list, tuple)) else str(x))
        display_df['Opportunity'] = display_df['Opportunity'].apply(
            lambda x: ', '.join(map(str, x)) if isinstance(x, (list, tuple)) else str(x))
        display_df['Amount'] = display_df['Amount'].apply(lambda x: format_currency(x) if pd.notnull(x) else '-')

        st.dataframe(display_df)

        # -------------------- Totalen --------------------
        total_sales = filtered[(pd.notnull(filtered['Amount']))
        ]['Amount'].sum()
        st.success(f"Total Untaxed Amount (Sales): € {total_sales:,.2f}")

        # -------------------- Excel Download --------------------
        st.subheader("Download als Excel-bestand")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            display_df.to_excel(writer, index=False, sheet_name='POC Overview')

        # Zet pointer naar het begin van de buffer
        output.seek(0)
        processed_data = output.getvalue()

        st.download_button(
            label="Download Excel",
            data=processed_data,
            file_name='poc_overview.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )



        # -------------------- Maandelijkse Som per Team --------------------
        pivot_df = filtered.pivot_table(
            index='Team',
            columns='Month',
            values='Amount',
            aggfunc='sum',
            fill_value=0
        )
        st.subheader(f"Maandelijkse Opbrengst per Team ({jaarkiezer})")
        st.dataframe(pivot_df.style.format("€ {:,.0f}"))

