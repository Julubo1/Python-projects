import streamlit as st
import pandas as pd
from datetime import date, timedelta

from shared.core import search_read

def show():
    st.title("Toekomstige Cashflow Forecast")

    # --- Companies ophalen ---
    companies = search_read(
        'res.company',
        domain=[],
        fields=['id', 'name'],
        context={'lang': 'en_GB'}
    )
    df_companies = pd.DataFrame(companies)

    if df_companies.empty:
        st.error("Geen companies gevonden in Odoo.")
        return

    company_map = dict(zip(df_companies['id'], df_companies['name']))

    selected_company_name = st.selectbox("Selecteer Company", df_companies['name'])
    selected_company_id = int(df_companies.loc[df_companies['name'] == selected_company_name, 'id'].values[0])


    # --- Data ophalen met company filter ---
    all_terms = search_read(
        'account.payment.term',
        domain=[],
        fields=['id', 'name', 'line_ids'],
        context={'lang': 'en_GB'}
    )

    pickings = search_read(
        'stock.picking',
        domain=[('picking_type_code', '=', 'outgoing'), ('company_id', '=', selected_company_id)],
        fields=['origin', 'scheduled_date', 'company_id'],
        context={'lang': 'en_GB'}
    )

    receipts = search_read(
        'stock.picking',
        domain=[('picking_type_code', '=', 'incoming'), ('company_id', '=', selected_company_id)],
        fields=['origin', 'scheduled_date', 'company_id'],
        context={'lang': 'en_GB'}
    )

    sales = search_read(
        'sale.order',
        domain=[('state', '=', 'sale'), ('company_id', '=', selected_company_id),('partner_id','!=','PEO B.V. (B)')],
        fields=['name', 'partner_id', 'amount_untaxed', 'currency_id', 'payment_term_id', 'company_id'],
        context={'lang': 'en_GB'}
    )

    purchases = search_read(
        'purchase.order',
        domain=[('state', '=', 'purchase'), ('company_id', '=', selected_company_id),('partner_id','!=','PEO B.V. (B)')],
        fields=['name', 'partner_id', 'origin', 'amount_untaxed', 'currency_id', 'payment_term_id', 'company_id'],
        context={'lang': 'en_GB'}
    )

    # --- Partners ophalen (voor namen) ---
    partners = search_read(
        'res.partner',
        domain=[],
        fields=['id', 'name'],
        context={'lang': 'en_GB'}
    )
    df_partners = pd.DataFrame(partners)
    partner_map = dict(zip(df_partners['id'], df_partners['name']))

    # --- DataFrames maken ---
    df_terms = pd.DataFrame(all_terms)
    df_pickings = pd.DataFrame(pickings)
    df_receipts = pd.DataFrame(receipts)
    df_sales = pd.DataFrame(sales)
    df_purchases = pd.DataFrame(purchases)


    # --- Hulpfunctie voor payment terms ---
    def extract_payment_days(payment_term_id):
        if isinstance(payment_term_id, list) and len(payment_term_id) == 2:
            term_name = payment_term_id[1]
            for part in term_name.split():
                if part.isdigit():
                    return int(part)
        return 30

    # --- Sales orders verwerken (cash-in) ---
    if not df_sales.empty:
        df_sales['partner_id_raw'] = df_sales['partner_id']
        df_sales['partner_id'] = df_sales['partner_id'].apply(lambda x: x[0] if isinstance(x, list) else None)
        df_pickings['scheduled_date'] = pd.to_datetime(df_pickings['scheduled_date'], errors='coerce')
        df_pickings = df_pickings.sort_values('scheduled_date')
        df_pickings_unique = df_pickings.drop_duplicates(subset='origin', keep='first')

        df_sales = df_sales.merge(df_pickings_unique[['origin', 'scheduled_date']], how='left',
                                  left_on='name', right_on='origin')
        df_sales.rename(columns={'scheduled_date': 'commitment_date'}, inplace=True)

        df_sales['expected_invoice_date'] = df_sales['commitment_date'] + timedelta(days=1)
        df_sales['payment_term_days'] = df_sales['payment_term_id'].apply(extract_payment_days)
        df_sales['expected_payment_date'] = df_sales['expected_invoice_date'] + pd.to_timedelta(
            df_sales['payment_term_days'], unit='D')

        df_sales = df_sales[df_sales['expected_payment_date'].notnull()]
        df_sales['cashflow_type'] = 'In'
        df_sales['amount'] = df_sales['amount_untaxed']
        df_sales['order'] = df_sales['name']
        df_sales['partner_name'] = df_sales['partner_id_raw'].apply(lambda x: x[1] if isinstance(x, list) else None)

    else:
        df_sales = pd.DataFrame()

    # --- Purchase orders verwerken (cash-out) ---
    if not df_purchases.empty:
        df_purchases['partner_id_raw'] = df_purchases['partner_id']
        df_purchases['partner_id'] = df_purchases['partner_id'].apply(lambda x: x[0] if isinstance(x, list) else None)
        df_receipts['scheduled_date'] = pd.to_datetime(df_receipts['scheduled_date'], errors='coerce')
        df_receipts = df_receipts.sort_values('scheduled_date')
        df_receipts_unique = df_receipts.drop_duplicates(subset='origin', keep='first')

        df_purchases = df_purchases.merge(df_receipts_unique[['origin', 'scheduled_date']], how='left',
                                          left_on='name', right_on='origin')
        df_purchases.rename(columns={'scheduled_date': 'receipt_date'}, inplace=True)

        df_purchases['expected_invoice_date'] = df_purchases['receipt_date'] + timedelta(days=1)
        df_purchases['payment_term_days'] = df_purchases['payment_term_id'].apply(extract_payment_days)
        df_purchases['expected_payment_date'] = df_purchases['expected_invoice_date'] + pd.to_timedelta(
            df_purchases['payment_term_days'], unit='D')

        df_purchases = df_purchases[df_purchases['expected_payment_date'].notnull()]
        df_purchases['cashflow_type'] = 'Out'
        df_purchases['amount'] = -df_purchases['amount_untaxed']
        df_purchases['order'] = df_purchases['name']
        df_purchases['partner_name'] = df_purchases['partner_id_raw'].apply(lambda x: x[1] if isinstance(x, list) else None)
        df_purchases = df_purchases[~df_purchases['partner_name'].str.contains("PEO B.V.", case=False, na=False)]

    else:
        df_purchases = pd.DataFrame()

    # --- Cashflow combineren ---
    df_cf = pd.concat([
        df_sales[['expected_payment_date', 'cashflow_type', 'amount', 'order','partner_name']],
        df_purchases[['expected_payment_date', 'cashflow_type', 'amount', 'order','partner_name']]
    ])

    df_cf = df_cf[df_cf['expected_payment_date'].notnull()]
    df_cf['month'] = df_cf['expected_payment_date'].dt.to_period('M').astype(str)

    # Alleen toekomstige cashflows tonen
    today = date.today()
    df_cf = df_cf[df_cf['expected_payment_date'].dt.date >= today]

    # --- Streamlit UI ---
    st.header(f"Cashflow Forecast – {selected_company_name}")

    if df_cf.empty:
        st.info("Geen toekomstige cashflows beschikbaar.")
    else:
        min_date = df_cf['expected_payment_date'].min().date()
        max_date = df_cf['expected_payment_date'].max().date()

        start_date, end_date = st.date_input(
            "Selecteer periode",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        filtered_df = df_cf[
            (df_cf['expected_payment_date'].dt.date >= start_date) &
            (df_cf['expected_payment_date'].dt.date <= end_date)
        ]

        # Aggregatie voor grafiek
        agg = filtered_df.groupby(['month', 'cashflow_type'])['amount'].sum().reset_index()
        pivot = agg.pivot(index='month', columns='cashflow_type', values='amount').fillna(0)

        st.bar_chart(pivot)

        # Tabel
        display_df = filtered_df.copy()
        display_df['expected_payment_date'] = display_df['expected_payment_date'].dt.strftime("%Y-%m-%d")
        display_df['amount'] = display_df['amount'].apply(lambda x: f"€ {x:,.2f}")
        display_df = display_df.rename(columns={
            'cashflow_type': 'Type',
            'expected_payment_date': 'Datum',
            'amount': 'Bedrag',
            'order': 'Order',
            'partner_name':'Customer'
        })

        st.subheader("Toekomstige transacties")
        st.dataframe(display_df[['Datum', 'Type', 'Order','Customer', 'Bedrag']].sort_values('Datum'))

        # Totale sommen
        total_in = filtered_df.loc[filtered_df['cashflow_type'] == 'In', 'amount'].sum()
        total_out = filtered_df.loc[filtered_df['cashflow_type'] == 'Out', 'amount'].sum()
        net = total_in + total_out

        st.success(f"Totale forecast cash-in: € {total_in:,.2f}")
        st.error(f"Totale forecast cash-out: € {-total_out:,.2f}")
        st.info(f"Netto cashflow: € {net:,.2f}")
