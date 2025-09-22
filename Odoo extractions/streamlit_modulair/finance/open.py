import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from shared.core import search_read

def show():
    st.title("Openstaande Betalingen (Debiteuren)")

    # Filters
    today = datetime.today().date()
    col1, col2 = st.columns(2)
    with col1:
        klant_filter = st.text_input("Filter op klantnaam (optioneel)")
    with col2:
        vervaldatum_filter = st.date_input("Max. vervaldatum (optioneel)", value=today)

    # Odoo query: openstaande klantfacturen (out_invoice, posted, openstaand bedrag > 0)
    domain = [
        ('move_type', '=', 'out_invoice'),
        ('state', '=', 'posted'),
        ('payment_state', 'not in', ['paid','reversed']),
        ('partner_id', 'not ilike', "CompanyA")
    ]
    if klant_filter:
        domain.append(('partner_id.name', 'ilike', klant_filter))
    if vervaldatum_filter:
        domain.append(('invoice_date_due', '<=', vervaldatum_filter.isoformat()))

    # Velden om op te halen
    fields = [
        'name',  # factuurnummer
        'partner_id',
        'invoice_date_due',
        'amount_total',
        'amount_residual',
        'currency_id',
    ]

    invoices = search_read('account.move', domain, fields)

    if invoices.empty:
        st.info("Geen openstaande facturen gevonden met deze filters.")
        return

    # DataFrame maken
    df = pd.DataFrame(invoices)
    # Partner naam uit dict halen
    df['partner_name'] = df['partner_id'].apply(lambda x: x[1] if x else '')
    df['invoice_date_due'] = pd.to_datetime(df['invoice_date_due']).dt.date
    df['currency'] = df['currency_id'].apply(lambda x: x[1] if x else '')
    df['amount_total'] = df['amount_total'].astype(float)
    df['amount_residual'] = df['amount_residual'].astype(float)

    # Aging bucket toevoegen
    def aging_bucket(due_date):
        days_overdue = (today - due_date).days
        if days_overdue < 0:
            return "Niet vervallen"
        elif days_overdue <= 30:
            return "0-30 dagen"
        elif days_overdue <= 60:
            return "31-60 dagen"
        else:
            return "61+ dagen"

    df['Aging'] = df['invoice_date_due'].apply(aging_bucket)

    # Sorteer op vervaldatum oplopend
    df = df.sort_values(by='invoice_date_due')

    # Toon tabel met relevante kolommen
    st.dataframe(
        df[['name', 'partner_name', 'invoice_date_due', 'amount_total', 'amount_residual', 'currency', 'Aging']],
        use_container_width=True
    )

    # Export naar Excel knop
    def to_excel(df):
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Openstaande facturen')
            writer.save()
        return output.getvalue()

    if st.button("Download Excel"):
        excel_data = to_excel(df[['name', 'partner_name', 'invoice_date_due', 'amount_total', 'amount_residual', 'currency', 'Aging']])
        st.download_button(label="Download Openstaande Facturen Excel", data=excel_data, file_name="openstaande_facturen.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
