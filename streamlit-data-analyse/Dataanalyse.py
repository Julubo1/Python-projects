import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import io

st.title("📊 Automatische Data-analyse")

uploaded_file = st.file_uploader("Upload je dataset (CSV, Excel, of JSON)", type=["csv", "xlsx", "xls", "json"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith(".json"):
            df = pd.read_json(uploaded_file)
        else:
            st.error("Bestandsformaat niet ondersteund.")
            st.stop()

        st.subheader("📄 Overzicht van data")
        st.write(df.head())

        st.subheader("🔍 Automatische gegevensanalyse")

        # Basisinfo
        st.write("**Vorm van de data:**", df.shape)
        st.write("**Kolommen:**", list(df.columns))
        st.write("**Ontbrekende waarden per kolom:**")
        st.write(df.isna().sum())

        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()

        if numeric_cols:
            st.subheader("📈 Numerieke analyse")
            st.write(df[numeric_cols].describe())

            st.pyplot(sns.pairplot(df[numeric_cols]))

        if cat_cols:
            st.subheader("🔤 Categorische analyse")
            for col in cat_cols:
                st.write(f"**{col}** – unieke waarden:", df[col].nunique())
                st.bar_chart(df[col].value_counts().head(10))

        # Simpele automatische conclusie
        st.subheader("💡 Automatische conclusie")
        conclusions = []
        if numeric_cols:
            for col in numeric_cols:
                mean = df[col].mean()
                std = df[col].std()
                if std == 0 or pd.isna(std):
                    continue
                variation = std / mean if mean != 0 else 0
                if variation > 1:
                    conclusions.append(f"{col} varieert sterk (CV > 1).")
                else:
                    conclusions.append(f"{col} is redelijk stabiel (CV ≤ 1).")
        if not conclusions:
            conclusions.append("Geen duidelijke numerieke trends gevonden.")
        st.write("\n".join(conclusions))

    except Exception as e:
        st.error(f"Fout bij verwerken bestand: {e}")
else:
    st.info("Upload een dataset om te starten.")
