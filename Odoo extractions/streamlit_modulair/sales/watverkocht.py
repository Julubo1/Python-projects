import streamlit as st
import pandas as pd
from datetime import datetime
from shared.core import search_read


def show():
    st.title("Verkoopoverzicht per Product / Productgroep / Supplier (incl. Repairs)")

    # --- Jaar filter ---
    huidige_jaar = datetime.now().year
    jaar = st.selectbox("Kies jaar", list(range(huidige_jaar, huidige_jaar - 6, -1)), index=0)
    start_datum = pd.to_datetime(f"{jaar}-01-01")
    eind_datum = pd.to_datetime(f"{jaar}-12-31")

    # --- Data ophalen ---
    df_order_lines = pd.DataFrame(search_read(
        'sale.order.line',
        domain=[('order_id.state', 'in', ['sale', 'done']), ('product_id', 'not ilike', 'transport')],
        fields=['order_id', 'product_id', 'product_uom_qty', 'price_total', 'currency_id'],
        context={'lang': 'en_GB'}
    ))

    df_orders = pd.DataFrame(search_read(
        'sale.order',
        domain=[('state', 'in', ['sale', 'done']), ('partner_id', '!=', 'company B.V. (B)')],
        fields=['id', 'team_id', 'date_order', 'partner_id'],
        context={'lang': 'en_GB'}
    ))

    df_repairs = pd.DataFrame(search_read(
        'repair.order',
        domain=[('state', '=', 'done'), ('partner_id', '!=', 'company B.V. (B)')],
        fields=['fees_lines', 'operations', 'x_studio_order_date', 'partner_id'],
        context={'lang': 'en_GB'}
    ))

    # --- Product ID's verzamelen uit sales en repairs ---
    def extract_product_ids(df_lines, field='product_id'):
        ids = []
        for pid in df_lines[field]:
            if isinstance(pid, list):
                ids.append(pid[0])
        return ids

    product_ids_sales = extract_product_ids(df_order_lines)

    fees_ids = [fid for sublist in df_repairs['fees_lines'].dropna() if isinstance(sublist, list) for fid in sublist]
    ops_ids = [oid for sublist in df_repairs['operations'].dropna() if isinstance(sublist, list) for oid in sublist]

    df_fees = pd.DataFrame()
    if fees_ids:
        df_fees = pd.DataFrame(search_read(
            'repair.fee',
            domain=[('id', 'in', fees_ids), ('product_id', 'not ilike', 'transport')],
            fields=['id', 'product_id', 'price_subtotal'],
            context={'lang': 'en_GB'}
        ))
        product_ids_sales += extract_product_ids(df_fees, 'product_id')

    df_ops = pd.DataFrame()
    if ops_ids:
        df_ops = pd.DataFrame(search_read(
            'repair.line',
            domain=[('id', 'in', ops_ids), ('product_id', 'not ilike', 'transport')],
            fields=['id', 'product_id', 'price_total'],
            context={'lang': 'en_GB'}
        ))
        product_ids_sales += extract_product_ids(df_ops, 'product_id')

    product_ids_sales = list(set(product_ids_sales))

    # --- Product & Supplier Mapping ---
    df_products = pd.DataFrame(search_read(
        'product.product',
        domain=[('id', 'in', product_ids_sales)],
        fields=['id', 'product_tmpl_id', 'categ_id'],
        context={'lang': 'en_GB'}
    ))

    tmpl_ids = [p['product_tmpl_id'][0] for p in df_products.to_dict('records') if
                isinstance(p.get('product_tmpl_id'), list)]

    df_tmpls = pd.DataFrame(search_read(
        'product.template',
        domain=[('id', 'in', tmpl_ids)],
        fields=['id', 'seller_ids'],
        context={'lang': 'en_GB'}
    ))

    # --- Supplier info ophalen ---
    seller_ids = [sid for sublist in df_tmpls['seller_ids'].dropna() for sid in sublist]
    df_suppliers = pd.DataFrame(search_read(
        'product.supplierinfo',
        domain=[('id', 'in', seller_ids)],
        fields=['id', 'name'],
        context={'lang': 'en_GB'}
    ))

    supplier_map = {s['id']: s['name'][1] if isinstance(s['name'], list) else str(s['name']) for s in
                    df_suppliers.to_dict('records')}
    tmpl_to_suppliers = {t['id']: t['seller_ids'] for t in df_tmpls.to_dict('records')}

    # --- Sales DataFrame samenstellen ---
    df_orders['date_order'] = pd.to_datetime(df_orders['date_order'], errors='coerce')
    df_orders = df_orders[(df_orders['date_order'] >= start_datum) & (df_orders['date_order'] <= eind_datum)]

    sales_rows = []
    for _, line in df_order_lines.iterrows():
        order = df_orders[
            df_orders['id'] == (line['order_id'][0] if isinstance(line['order_id'], list) else line['order_id'])]
        if not order.empty:
            order = order.iloc[0]
            prod = next((p for p in df_products.to_dict('records') if p['id'] == (
                line['product_id'][0] if isinstance(line['product_id'], list) else line['product_id'])), {})
            tmpl_id = prod.get('product_tmpl_id', [None])[0]
            supplier_names = [supplier_map.get(sid) for sid in tmpl_to_suppliers.get(tmpl_id, []) if
                              sid in supplier_map]
            supplier_name = ", ".join(filter(None, supplier_names)) if supplier_names else None

            sales_rows.append({
                'Product': (line['product_id'][1] if isinstance(line['product_id'], list) else str(line['product_id'])),
                'Supplier': supplier_name,
                'Productgroep': prod.get('categ_id', [None, None])[1],
                'product_uom_qty': line['product_uom_qty'],
                'price_total': line['price_total'],
                'Klant': (order['partner_id'][1] if isinstance(order['partner_id'], list) else str(order['partner_id']))
            })

    # --- Repairs DataFrame samenstellen ---
    df_repairs['x_studio_order_date'] = pd.to_datetime(df_repairs['x_studio_order_date'], errors='coerce')
    df_repairs = df_repairs[
        (df_repairs['x_studio_order_date'] >= start_datum) & (df_repairs['x_studio_order_date'] <= eind_datum)]

    repair_rows = []
    for _, row in df_repairs.iterrows():
        klantnaam = row['partner_id'][1] if isinstance(row['partner_id'], list) else str(row['partner_id'])

        for fid in (row['fees_lines'] or []):
            fee = df_fees[df_fees['id'] == fid]
            if not fee.empty:
                pid = fee.iloc[0]['product_id']
                product_id = pid[0] if isinstance(pid, list) else pid
                product_name = pid[1] if isinstance(pid, list) else str(pid)
                prod_info = next((p for p in df_products.to_dict('records') if p.get('id') == product_id), {})
                tmpl_id = prod_info.get('product_tmpl_id', [None])[0]
                supplier_names = [supplier_map.get(sid) for sid in tmpl_to_suppliers.get(tmpl_id, []) if
                                  sid in supplier_map]
                supplier_name = ", ".join(filter(None, supplier_names)) if supplier_names else None
                repair_rows.append({
                    'Product': product_name,
                    'Supplier': supplier_name,
                    'Productgroep': prod_info.get('categ_id', [None, None])[1],
                    'product_uom_qty': 1,
                    'price_total': fee.iloc[0]['price_subtotal'],
                    'Klant': klantnaam
                })

        for oid in (row['operations'] or []):
            op = df_ops[df_ops['id'] == oid]
            if not op.empty:
                pid = op.iloc[0]['product_id']
                product_id = pid[0] if isinstance(pid, list) else pid
                product_name = pid[1] if isinstance(pid, list) else str(pid)
                prod_info = next((p for p in df_products.to_dict('records') if p.get('id') == product_id), {})
                tmpl_id = prod_info.get('product_tmpl_id', [None])[0]
                supplier_names = [supplier_map.get(sid) for sid in tmpl_to_suppliers.get(tmpl_id, []) if
                                  sid in supplier_map]
                supplier_name = ", ".join(filter(None, supplier_names)) if supplier_names else None
                repair_rows.append({
                    'Product': product_name,
                    'Supplier': supplier_name,
                    'Productgroep': prod_info.get('categ_id', [None, None])[1],
                    'product_uom_qty': 1,
                    'price_total': op.iloc[0]['price_total'],
                    'Klant': klantnaam
                })

    df_result = pd.concat([pd.DataFrame(sales_rows), pd.DataFrame(repair_rows)], ignore_index=True)

    df_all = pd.DataFrame(sales_rows + repair_rows)
    df_all['Supplier'] = df_all['Supplier'].apply(
        lambda x: [s.strip() for s in x.split(",")] if isinstance(x, str) else [])

    # --- Filters ---
    unieke_productgroepen = sorted(df_all['Productgroep'].dropna().unique())
    geselecteerde_productgroep = st.selectbox("Productgroep (optioneel)", ["Alle"] + unieke_productgroepen)

    # Alle unieke suppliers flattenen uit lijst-kolom
    unieke_suppliers = sorted(set(supplier for sublist in df_all['Supplier'] for supplier in sublist if supplier))
    geselecteerde_supplier = st.selectbox("Supplier (optioneel)", ["Alle"] + unieke_suppliers)

    # --- Filter toepassen ---
    df_filtered = df_all.copy()
    if geselecteerde_productgroep != "Alle":
        df_filtered = df_filtered[df_filtered['Productgroep'] == geselecteerde_productgroep]

    if geselecteerde_supplier != "Alle":
        # Filter rijen waar de geselecteerde supplier **in de lijst** voorkomt
        df_filtered = df_filtered[df_filtered['Supplier'].apply(lambda x: geselecteerde_supplier in x)]

    st.dataframe(df_filtered.reset_index(drop=True))

    # --- DataFrame tonen ---
    df_final=df_filtered.reset_index(drop=True)

    # --- Samenvatting onder de tabel ---
    totaal_orders = len(df_final)
    totaal_bedrag = df_final['price_total'].sum()
    unieke_producten = df_final['Product'].nunique()
    unieke_klanten = df_final['Klant'].nunique()

    st.markdown("### Samenvatting")
    st.markdown(f"- **Totaal aantal rijen/orders:** {totaal_orders}")
    st.markdown(f"- **Totaal bedrag:** €{totaal_bedrag:,.2f}")
    st.markdown(f"- **Aantal unieke producten:** {unieke_producten}")
    st.markdown(f"- **Aantal unieke klanten:** {unieke_klanten}")


