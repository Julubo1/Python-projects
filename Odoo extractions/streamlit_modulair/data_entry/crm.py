import streamlit as st
import pandas as pd
from datetime import datetime
from shared.core import search_read, map_oem

def show():
    st.title("Data Entry Fouten Monitor - CRM Module")

    # Leads ophalen
    df_leads = search_read(
        'crm.lead',
        domain=[('stage_id', '!=', 4), ('type', '!=', 'lead')],
        fields=[
            'name', 'partner_id', 'email_from', 'team_id',
            'expected_revenue', 'date_deadline', 'x_studio_expected_delivery', 'x_studio_result_responsable',
            'stage_id', 'x_studio_oem_v2'
        ],
        context={'lang': 'en_GB'}
    )

    # Partner-IDs ophalen
    partner_ids = [p[0] for p in df_leads['partner_id'] if isinstance(p, list)]
    df_partners = pd.DataFrame()
    if partner_ids:
        partners = search_read(
            'res.partner',
            domain=[('id', 'in', partner_ids)],
            fields=['id', 'name', 'is_company']
        )
        df_partners = pd.DataFrame(partners)

    # Data verrijken
    df_leads['team'] = df_leads['team_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_leads['stage'] = df_leads['stage_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_leads['customer'] = df_leads['partner_id'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_leads['partner_id_val'] = df_leads['partner_id'].apply(lambda x: x[0] if isinstance(x, list) else None)
    df_leads['verkoper'] = df_leads['x_studio_result_responsable'].apply(lambda x: x[1] if isinstance(x, list) else '')
    df_leads['oem'] = df_leads['x_studio_oem_v2'].apply(map_oem)

    today = pd.Timestamp.today().normalize()
    fouten = []

    for _, row in df_leads.iterrows():
        issues = []

        if not row['name']:
            issues.append("Naam ontbreekt")
        if not row['oem']:
            issues.append("OEM ontbreekt")
        if not row['team']:
            issues.append("Sales Team ontbreekt")
        if row['team'] in ['Order', 'Office', 'Info', 'Odoo', 'MarCom']:
            issues.append(f"Ongeldig Sales Team: {row['team']}")
        if not row['verkoper']:
            issues.append("Geen result responsible toegewezen")
        if not row['customer']:
            issues.append("Geen klant gekoppeld")

        # Nieuw: controleer of klant een company is (dit mag niet)
        if row['partner_id_val'] and not df_partners.empty:
            match = df_partners[df_partners['id'] == row['partner_id_val']]
            if not match.empty and match.iloc[0]['is_company']:
                issues.append("Klant is een company (moet individual zijn)")

        if not row['date_deadline']:
            issues.append("Expected Order Date ontbreekt")
        else:
            try:
                d = pd.to_datetime(row['date_deadline']).normalize()
                if d < today:
                    issues.append("Expected Order Date is verlopen")
            except Exception:
                issues.append("Expected Order Date is ongeldig formaat")

        if not row['x_studio_expected_delivery']:
            issues.append("Expected Delivery Date ontbreekt")
        else:
            try:
                d = pd.to_datetime(row['x_studio_expected_delivery']).normalize()
                if d < today:
                    issues.append("Expected Delivery Date is verlopen")
            except Exception:
                issues.append("Expected Delivery Date is ongeldig formaat")

        if issues:
            fouten.append({
                "Naam": row['name'],
                "Stage": row['stage_id'],
                "Expected Order": row['date_deadline'],
                "Expected Delivery": row['x_studio_expected_delivery'],
                "Result Responsible": row['verkoper'],
                'OEM': row['oem'],
                "Klant": row['customer'],
                "Sales Team": row['team'],
                "Fouten": "; ".join(issues)
            })

    if not fouten:
        st.success("Geen data entry fouten in CRM gevonden.")
    else:
        fout_df = pd.DataFrame(fouten)
        fout_df['Stage'] = fout_df['Stage'].astype(str)
        unieke_fouten = sorted({f for foutenlijst in fout_df['Fouten'] for f in foutenlijst.split("; ")})

        fout_filter = st.selectbox(
            "Filter op fouttype (CRM)",
            ["Toon alles"] + unieke_fouten,
            key="crm_fout_filter"
        )

        if fout_filter != "Toon alles":
            fout_df = fout_df[fout_df['Fouten'].str.contains(fout_filter, case=False, regex=False)]

        st.warning(f"{len(fout_df)} foutieve CRM-records gevonden.")
        st.dataframe(fout_df)
