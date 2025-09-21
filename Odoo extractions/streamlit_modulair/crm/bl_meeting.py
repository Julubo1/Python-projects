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
    st.header("Business Line Meeting Overview")

    # ---- DATA OPHALEN ----
    df_leads = search_read(
        'crm.lead',
        domain=[],
        fields=[
            'id', 'name', 'type', 'team_id', 'stage_id', 'partner_id', 'country_id',
            'x_studio_oem_v2', 'x_studio_result_responsable', 'x_studio_rd_po_c',
            'x_studio_sd_quote', 'expected_revenue', 'x_studio_slagingskans',
            'quotation_count', 'x_studio_po_c_reference', 'description',
            'create_date', 'date_deadline'
        ],
        context={'lang': 'en_GB'}
    )
    df_sales = search_read(
        'sale.order',
        domain=[],
        fields=[
            'name', 'x_studio_rd_poc', 'client_order_ref', 'team_id',
            'amount_untaxed', 'state', 'x_studio_datetime_field_FyIZ2', 'commitment_date', 'partner_id',
            'invoice_status', 'opportunity_id'
        ],
        context={'lang': 'en_GB'}
    )

    df_invoices = search_read(
        'account.move',
        domain=[],
        fields=[
            'id', 'name', 'invoice_origin', 'payment_state', 'invoice_date_due',
            'amount_residual', 'invoice_payment_term_id'
        ],
        context={'lang': 'en_GB'}
    )
    df_transfers = search_read(
        'stock.picking',
        domain=[],
        fields=[
            'id', 'name', 'location_id', 'location_dest_id', 'partner_id', 'scheduled_date', 'origin', 'date_done',
            'company_id', 'move_type', 'state'
        ],
        context={'lang': 'en_GB'}
    )
    df_activities = search_read(
        'mail.activity',
        domain=[],
        fields=[
            'id', 'user_id', 'state', 'date_deadline', 'note', 'summary', 'res_model', 'res_id'
        ],
        context={'lang': 'en_GB'}
    )

    df_leads['stage_id_val'] = df_leads['stage_id'].apply(lambda x: x[0] if isinstance(x, list) else None)
    df_leads['Stage'] = df_leads['stage_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')
    df_leads['team_name'] = df_leads['team_id'].apply(lambda x: x[1] if isinstance(x, list) else 'Onbekend')
    df_leads['partner_name'] = df_leads['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_leads['country_name'] = df_leads['country_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_leads["week_created"] = pd.to_datetime(df_leads["create_date"]).dt.isocalendar().week
    df_leads["year_created"] = pd.to_datetime(df_leads["create_date"]).dt.isocalendar().year
    df_leads['Hitrate_num'] = pd.to_numeric(df_leads['x_studio_slagingskans'], errors='coerce')

    if not df_leads.empty:
        # ---- FILTER NIET-WON ----
        filtered = df_leads[df_leads['stage_id_val'] != WON_STAGE_ID].copy()

        teams = filtered['team_name'].dropna().unique().tolist()
        types = filtered['type'].dropna().unique().tolist()
        hitrates = filtered['x_studio_slagingskans'].dropna().unique().tolist()

        selected_team = st.selectbox("Filter op Business Line", options=["Alle"] + teams)
        selected_type = st.selectbox("Filter op Type", options=["Alle"] + types)
        selected_hitrates = st.multiselect("Filter op Hitrate (meerdere mogelijk)", options=hitrates, default=hitrates)

        if selected_team != "Alle":
            filtered = filtered[filtered['team_name'] == selected_team]
        if selected_type != "Alle":
            filtered = filtered[filtered['type'] == selected_type]
        if selected_hitrates:
            # filter op alle geselecteerde hitrates (meerdere)
            filtered = filtered[filtered['x_studio_slagingskans'].isin(selected_hitrates)]

        # Zorg dat 'date_deadline' datetime is (als dat nog niet is gebeurd)
        filtered['date_deadline'] = pd.to_datetime(filtered['date_deadline'], errors='coerce')

        # Maak een kolom met jaar van expected order date
        filtered['year_deadline'] = filtered['date_deadline'].dt.year

        # Optionele jaartallen voor filter (uniek en sorteren)
        years = filtered['year_deadline'].dropna().unique().tolist()
        years = sorted([int(y) for y in years])

        # Voeg optie "Alle jaren" toe
        selected_year = st.selectbox("Filter op Jaar Expected Order Date", options=["Alle jaren"] + years)

        # Filter op jaar als er een specifiek jaar is gekozen
        if selected_year != "Alle jaren":
            filtered = filtered[filtered['year_deadline'] == selected_year]

        # Stage mapping (optioneel, als je custom labels hebt)
        stage_id_to_name = {
            1: "1st snd + <4 C<->PEO!",
            2: "C<->PEO+BMCPPS?+PS!",
            3: "FinalQUO-PEO-->C",
            4: "SD-SO-PEO-->C WON",
            5: "≈ITT-C-->PEO!",
            7: "POcheck+PEO-PO-->OEM",
            9: "BMCPPS?+PS!+QUO!"
        }
        filtered['Stage'] = filtered['stage_id_val'].map(stage_id_to_name)

        table = filtered[[
            'type', 'id', 'name', 'partner_name', 'country_name', 'x_studio_oem_v2',
            'x_studio_result_responsable', 'x_studio_rd_po_c',
            'x_studio_sd_quote', 'expected_revenue', 'Stage', 'x_studio_slagingskans',
            'team_name', 'quotation_count', 'x_studio_po_c_reference', 'description',
            'week_created', 'year_created', 'create_date', 'date_deadline'
        ]].rename(columns={
            'name': 'Opportunity',
            'x_studio_sd_quote': 'SD-QU-PEO-->C',
            'x_studio_rd_po_c': 'RD-PO-C-->PEO',
            'x_studio_po_c_reference': 'POC Reference',
            'x_studio_result_responsable': 'Result Responsible',
            'x_studio_slagingskans': 'Hitrate',
            'team_name': 'Business Line',
            'date_deadline': 'Expected Order Date',
            'quotation_count': 'Number of Quotes',
            'description': 'Internal Note'
        })

        # Data formatteren
        table['Result Responsible'] = table['Result Responsible'].apply(
            lambda x: ', '.join(str(i) for i in x) if isinstance(x, list)
            else (str(x) if pd.notnull(x) else None)
        )
        table['x_studio_oem_v2'] = table['x_studio_oem_v2'].apply(map_oem)
        table['expected_revenue'] = table['expected_revenue'].apply(format_currency)
        table['Internal Note'] = table['Internal Note'].apply(strip_html)

        # ---- ACTIVITEITEN ----
        if not df_activities.empty:
            df_activities['res_id'] = pd.to_numeric(df_activities['res_id'], errors='coerce')
            df_activities['date_deadline'] = pd.to_datetime(df_activities['date_deadline'], errors='coerce')
            today = pd.to_datetime(pd.Timestamp.today().date())
            df_activities['Days Remaining'] = (df_activities['date_deadline'] - today).dt.days
            df_activities['user_name'] = df_activities['user_id'].apply(
                lambda x: x[1] if isinstance(x, list) else 'Onbekend')
            df_activities['Activity CRM'] = df_activities.apply(
                lambda
                    row: f"{row['summary']} (by {row['user_name']}, deadline {row['date_deadline'].date() if pd.notnull(row['date_deadline']) else 'N/A'})",
                axis=1
            )

            activity_grouped = df_activities.groupby('res_id')['Activity CRM'].apply(
                lambda x: '; '.join(x)).reset_index()

            table = table.merge(activity_grouped, how='left', left_on='id', right_on='res_id')
            table.drop(columns=['res_id'], inplace=True, errors='ignore')
        else:
            table['Activity CRM'] = None

        st.subheader("Open Opportunities")
        st.dataframe(table)

        # Totaal expected revenue berekenen (parse van string naar float)
        def parse_currency(x):
            if pd.isna(x):
                return np.nan
            # Verwijder Euro-teken en spaties
            x = x.replace('€', '').strip()
            # Verwijder punten (duizendtallen)
            x = x.replace('.', '')
            # Vervang komma door punt (decimaal scheiding)
            x = x.replace(',', '.')
            try:
                return float(x)
            except ValueError:
                return np.nan

        table['expected_revenue_float'] = table['expected_revenue'].apply(parse_currency)
        total_revenue = table['expected_revenue_float'].sum()

        st.markdown(f"**Totaal geschatte omzet: € {total_revenue:,.2f}**")

        # ==== WON + OPEN SALES ORDERS ANALYSE ====
        st.subheader("WON Opportunities met Open Sales Orders")

        won_opps = df_leads[df_leads['stage_id_val'] == WON_STAGE_ID].copy()

        selected_team = st.selectbox("Filter op Business Line (Team)", options=["Alle"] + teams)
        if selected_team != "Alle":
            won_opps = won_opps[won_opps['team_name'] == selected_team]

        if not won_opps.empty:
            # Voorzie dat df_sales, df_invoices, df_transfers al geladen zijn via search_read eerder
            df_sales['opportunity_id_val'] = df_sales['opportunity_id'].apply(
                lambda x: x[0] if isinstance(x, list) else None)
            df_sales['name'] = df_sales['name'].astype(str)
            df_invoices['invoice_origin'] = df_invoices['invoice_origin'].astype(str)
            df_transfers['origin'] = df_transfers['origin'].astype(str)
            df_transfers['state'] = df_transfers['state'].astype(str)

            merged = won_opps.merge(df_sales, how='left', left_on='id', right_on='opportunity_id_val',
                                    suffixes=('_opp', '_so'))

            if not df_activities.empty:
                sales_activities = df_activities[df_activities['res_model'] == 'sale.order']
                sales_activities['Activity'] = sales_activities.apply(
                    lambda row: f"{row['summary']} (by {row['user_name']}, deadline {row['date_deadline']})", axis=1
                )
                act_grouped = sales_activities.groupby('res_id')['Activity'].apply(lambda x: '; '.join(x)).reset_index()
                merged = merged.merge(act_grouped, how='left', left_on='id_so', right_on='res_id')
            else:
                merged['Activity'] = None

            stock_status = df_transfers.groupby('origin')['state'].apply(lambda x: ', '.join(x.unique())).reset_index()
            stock_status.rename(columns={'state': 'Transfer States'}, inplace=True)
            merged = merged.merge(stock_status, how='left', left_on='name_so', right_on='origin')

            invoice_status = df_invoices.groupby('invoice_origin')['amount_residual'].sum().reset_index()
            merged = merged.merge(invoice_status, how='left', left_on='name_so', right_on='invoice_origin')

            # Needs Action logica
            merged['Transfer States'] = merged['Transfer States'].fillna('')
            merged['amount_residual'] = merged['amount_residual'].fillna(0)

            merged = merged[
                ~merged['Transfer States'].apply(
                    lambda x: all(state.strip() in ['done', 'cancel'] for state in x.split(',') if state.strip())
                )
            ]

            needs_action = merged[
                (merged['Activity'].notnull()) |
                (merged['Transfer States'] != '') |
                (merged['amount_residual'] > 0)
                ].copy()

            display = needs_action[
                ['name_opp', 'partner_name', 'name_so', 'Activity', 'Transfer States', 'amount_residual']].rename(
                columns={
                    'name_opp': 'Opportunity',
                    'name_so': 'Sales Order',
                    'partner_name': 'Customer',
                    'Transfer States': 'Transfer Status',
                    'amount_residual': 'Unpaid Amount'
                })

            display['Unpaid Amount'] = display['Unpaid Amount'].apply(
                lambda x: f"€ {x:,.2f}" if pd.notnull(x) else "€ 0,00")

            st.dataframe(display.sort_values(by=['Opportunity', 'Sales Order']))
            st.success(f"Aantal WON opportunities met open actiepunten: {display['Opportunity'].nunique()}")
        else:
            st.info("Geen WON opportunities gevonden.")