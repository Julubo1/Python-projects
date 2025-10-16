import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import json

# -----------------------------
# INSTELLINGEN
# -----------------------------
HF_MODEL = "bigscience/bloomz-560m"  # Publiek, geen token nodig
HF_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
headers = {"Content-Type": "application/json"}


def analyseer_met_ai(samenvatting: str) -> str:
    """Gebruik Hugging Face publiek model voor tekstuele analyse."""
    prompt = f"""Vat deze dataset-analyse samen in een korte, feitelijke opsomming:
    {samenvatting}
    Schrijf in het Nederlands, maximaal 5 punten.
    """
    try:
        payload = json.dumps({"inputs": prompt})
        response = requests.post(HF_URL, headers=headers, data=payload, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and "generated_text" in data[0]:
                return data[0]["generated_text"]
            elif isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"]
            else:
                return str(data)
        else:
            return f"API-fout: {response.status_code} - {response.text}"
    except Exception as e:
        return f"AI-analyse mislukt: {e}"


# -----------------------------
# STREAMLIT APP
# -----------------------------
st.set_page_config(page_title="Automatische Data-analyse", layout="wide")
st.title("📊 Automatische Data-analyse + AI-conclusie")

uploaded_file = st.file_uploader("Upload een dataset (CSV, Excel of JSON)", type=["csv", "xlsx", "xls", "json"])

if uploaded_file:
    try:
        # Lees bestand in
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith(".json"):
            df = pd.read_json(uploaded_file)
        else:
            st.error("Bestandsformaat niet ondersteund.")
            st.stop()

        st.subheader("📄 Voorbeeld van data")
        st.dataframe(df.head())

        st.subheader("🔍 Basisanalyse")
        st.write(f"Vorm van de data: {df.shape[0]} rijen × {df.shape[1]} kolommen")
        st.write("Ontbrekende waarden per kolom:")
        st.write(df.isna().sum())

        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        cat_cols = df.select_dtypes(exclude=np.number).columns.tolist()
        summary_text = []

        if numeric_cols:
            st.subheader("📈 Numerieke analyse")
            desc = df[numeric_cols].describe()
            st.write(desc)
            summary_text.append("Numerieke kolommen: " + ", ".join(numeric_cols))
            summary_text.append(str(desc))

            if len(numeric_cols) >= 2:
                st.write("Relaties tussen numerieke kolommen:")
                fig = sns.pairplot(df[numeric_cols])
                st.pyplot(fig)

        if cat_cols:
            st.subheader("🔤 Categorische kolommen")
            for col in cat_cols:
                vc = df[col].value_counts().head(10)
                st.bar_chart(vc)
                summary_text.append(f"Topwaarden voor {col}: {vc.to_dict()}")

        # -----------------------------
        # AI-CONCLUSIE
        # -----------------------------
        st.subheader("🧠 AI-conclusie")
        samenvatting = "\n".join(summary_text)
        if len(samenvatting.strip()) < 50:
            st.warning("Niet genoeg data voor AI-analyse.")
        else:
            with st.spinner("AI analyse wordt uitgevoerd..."):
                conclusie = analyseer_met_ai(samenvatting)
            st.write(conclusie)

    except Exception as e:
        st.error(f"Fout bij verwerken: {e}")

else:
    st.info("Upload een dataset om te starten.")
