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

from shared.core import search_read, strip_html, filter_on_year, format_currency, map_oem, contact_mapping, filter_on_date_range, filter_df_on_search, categorize_activity_state, get_translated_names, get_exchange_rate, industry_to_wikidata_q, build_osm_query,wikidata_country_codes,query_wikidata, industry_osm_mapping,get_label, extract_country_name
def show():
    st.title("Marge Analyse")

    # 1. Haal sale.order.line data op
    df_lines = search_read(
        "sale.order.line",
        fields=[
            "id",
            "product_id",
            "x_studio_net_company_purchase_price_euro",
            "price_unit",
            "x_studio_effective_margin",
            "order_id",
            "product_uom_qty"
        ],
        domain=[("order_id.state", "in", ["sale", "done"])],
        context={'lang': 'en_GB'}
    )
    df_lines = pd.DataFrame(df_lines)

    if df_lines.empty:
        st.warning("Geen orderregels gevonden.")
        st.stop()

    # 2. Extract order_id's
    df_lines["order_id_id"] = df_lines["order_id"].apply(lambda x: x[0] if isinstance(x, list) else None)
    order_ids = df_lines["order_id_id"].dropna().unique().tolist()

    if not order_ids:
        st.warning("Geen geldige order_ids gevonden.")
        st.stop()

    # 3. Haal sale.order records op
    df_orders = search_read(
        "sale.order",
        fields=["id", "date_order", "team_id", "partner_id", "name"],
        domain=[("id", "in", order_ids)],
        context={'lang': 'en_GB'}
    )
    df_orders = pd.DataFrame(df_orders)

    if df_orders.empty or "id" not in df_orders.columns:
        st.error("Fout bij ophalen data van sale.order.")
        st.stop()

    # 4. Haal partner info op
    partner_ids = df_orders["partner_id"].apply(
        lambda x: x[0] if isinstance(x, list) else None).dropna().unique().tolist()
    partners = search_read(
        "res.partner",
        fields=["id", "name", "parent_id"],
        domain=[("id", "in", partner_ids)],
        context={'lang': 'en_GB'}
    )
    df_partners = pd.DataFrame(partners)

    # 5. Toevoegen van parent_bedrijf
    df_partners["parent_bedrijf"] = df_partners["parent_id"].apply(
        lambda x: x[1] if isinstance(x, list) else None
    )

    df_partners["partner_id"] = df_partners["id"]
    df_partners = df_partners[["partner_id", "parent_bedrijf"]]  # enkel wat we nodig hebben

    # 6. Merge partners met orders
    df_orders["partner_id_short"] = df_orders["partner_id"].apply(lambda x: x[0] if isinstance(x, list) else None)
    df_orders = df_orders.merge(df_partners, left_on="partner_id_short", right_on="partner_id", how="left")

    # Enkel klanten met parent_bedrijf meenemen
    df_orders = df_orders[df_orders["parent_bedrijf"].notna()]
    df_orders["customer"] = df_orders["parent_bedrijf"]

    # 7. Verwerk overige ordervelden
    df_orders["order_id_id"] = df_orders["id"]
    df_orders["team"] = df_orders["team_id"].apply(lambda x: x[1] if isinstance(x, list) else None)
    df_orders["date_order"] = pd.to_datetime(df_orders["date_order"])

    # 8. Merge met orderlines
    df = pd.merge(
        df_lines,
        df_orders[["order_id_id", "date_order", "team", "customer", "name"]],
        on="order_id_id",
        how="left"
    )
    df.rename(columns={"name": "order_name"}, inplace=True)

    # Jaar + marges/prijzen
    df["year"] = df["date_order"].dt.year.astype("Int64")
    df["verkoopprijs"] = df["price_unit"]
    df["inkoopprijs"] = df["x_studio_net_company_purchase_price_euro"]
    df["marge_pct"] = df["x_studio_effective_margin"]
    df["product"] = df["product_id"].apply(lambda x: x[1] if isinstance(x, list) else None)

    # Producten uitsluiten
    woorden_uitsluiten = ["transport", "tarief", "kilometer", "service engineer"]
    pattern = "|".join(woorden_uitsluiten)
    df = df[~df["product"].str.contains(pattern, case=False, na=False)]

    # Specifieke klant uitsluiten
    df = df[df["customer"] != "company B.V. (B)"]

    # Onvolledige rijen uitsluiten
    df = df.dropna(subset=["product", "team", "customer", "date_order", "verkoopprijs", "inkoopprijs", "marge_pct"])

    # ---------- FILTERS ----------
    select_jaar = st.selectbox("Jaar", sorted(df["year"].dropna().unique(), reverse=True))
    select_team = st.selectbox("Verkoopteam(s)", ["Alle"] + sorted(df["team"].dropna().unique(), reverse=True))
    select_klant = st.selectbox("Klant(en)", ["Alle"] + sorted(df["customer"].dropna().unique(), reverse=True))
    select_product = st.selectbox("Product", ["Alle"] + sorted(df["product"].dropna().unique(), reverse=True))

    df_jaar = df[df["year"] == select_jaar]

    df_filtered = df_jaar.copy()
    if select_team != "Alle":
        df_filtered = df_filtered[df_filtered["team"] == select_team]
    if select_klant != "Alle":
        df_filtered = df_filtered[df_filtered["customer"] == select_klant]
    if select_product != "Alle":
        df_filtered = df_filtered[df_filtered["product"] == select_product]

    # ---------- TABEL 1: Aggregatie per klant/product/team ----------
    agg1 = df_filtered.groupby(["customer", "product", "team"]).agg(
        laagste_marge=("marge_pct", "min"),
        hoogste_marge=("marge_pct", "max"),
        gemiddelde_marge=("marge_pct", "mean"),
        aantal=("product_uom_qty", "sum"),
    ).reset_index()

    st.subheader("Gemiddelde Marge per Klant / Product / Team")
    st.dataframe(agg1.sort_values("gemiddelde_marge", ascending=False), use_container_width=True)

    # ---------- TABEL 2: Orderregels ----------
    st.subheader(f"Marge-details per orderregel ({select_jaar})")

    kolommen_tonen = [
        "date_order", "order_name", "team", "customer", "product",
        "product_uom_qty", "inkoopprijs", "verkoopprijs", "marge_pct"
    ]

    st.dataframe(
        df_filtered[kolommen_tonen].sort_values("date_order", ascending=False),
        use_container_width=True)
