# app.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.preprocessing import LabelEncoder
import phik
from phik import resources, report
import os, io, base64

# ---------- CONFIG ----------
st.set_page_config(page_title="Auto-Analyse", layout="wide")
st.title("📊 Automatische Data-analyse + Advies")

# ---------- UPLOAD ----------
uploaded = st.file_uploader("Upload CSV of Excel", type=["csv","xlsx","xls"])

if not uploaded:
    st.stop()

# ---------- READ ----------
@st.cache_data
def read_file(f):
    return pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)

df = read_file(uploaded)
st.subheader("📄 Voorproefje")
st.dataframe(df.head())

# ---------- AUTO-DETECT ----------
def auto_detect_types(df):
    """Retourneert dict met keys numeric, categorical, datetime, constant, id_like"""
    out = {"num":[],"cat":[],"dt":[],"constant":[],"id":[]}
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            if s.nunique() == 1:
                out["constant"].append(col)
            elif s.nunique() > 0.95*len(s) and s.is_monotonic_increasing:
                out["id"].append(col)
            else:
                out["num"].append(col)
        elif pd.api.types.is_datetime64_any_dtype(s):
            out["dt"].append(col)
        else:
            if s.nunique() == 1:
                out["constant"].append(col)
            elif s.nunique()/len(s) > 0.5:
                out["id"].append(col)
            else:
                out["cat"].append(col)
    return out

types = auto_detect_types(df)
st.write("**Gedetecteerde types:**", types)

# ---------- CLEAN ----------
df = df.drop(columns=types["constant"]+types["id"])
types = {k:[c for c in v if c in df.columns] for k,v in types.items()}

# ---------- QUICK EDA ----------
st.subheader("🔍 Snelle profilering")
left, right = st.columns(2)
with left:
    st.metric("Rijen", df.shape[0])
    st.metric("Kolommen", df.shape[1])
with right:
    st.write("Missings (%)", (df.isna().mean()*100).round(1).sort_values(ascending=False))

# ---------- CORRELATIES ----------
corr_method = st.selectbox("Correlatiemethode", ["Pearson","Spearman","Phik (categorical)"])
num_cols = types["num"]
cat_cols = types["cat"]

if corr_method == "Phik (categorical)" and (num_cols or cat_cols):
    # Phik werkt voor zowel cat als num
    phik_matrix = df.phik_matrix()
    fig, ax = plt.subplots(figsize=(6,5))
    sns.heatmap(phik_matrix, annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
    st.pyplot(fig)
    st.caption("Phik = 0 → onafhankelijk, 1 → perfecte relatie")
else:
    if len(num_cols) >= 2:
        corr = df[num_cols].corr(method=corr_method.lower())
        fig, ax = plt.subplots(figsize=(6,5))
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
        st.pyplot(fig)

# ---------- OUTLIERS ----------
if num_cols:
    st.subheader("🎯 Outlier-scan (Z-score > 3)")
    z = np.abs(stats.zscore(df[num_cols].dropna()))
    outliers = (z > 3).any(axis=1)
    st.write(f"Aantal outliers: **{outliers.sum()}** ({outliers.mean()*100:.1f}%)")
    if outliers.sum():
        st.write(df[outliers][num_cols].describe())

# ---------- CAUSALE HINTS ----------
def causale_hints(df, types):
    """Simpele heuristiek: zoek naar hoge correlatie + lage p-waarde."""
    hints = []
    num = types["num"]
    if len(num) < 2: return hints
    corr = df[num].corr()
    for i in range(len(corr.columns)):
        for j in range(i+1, len(corr.columns)):
            c = corr.iloc[i,j]
            if abs(c) > 0.7:
                x, y = corr.columns[i], corr.columns[j]
                # quick lin-reg p-waarde
                mask = df[[x,y]].dropna()
                if len(mask) < 10: continue
                slope, intercept, r, p, se = stats.linregress(mask[x], mask[y])
                if p < 0.01:
                    hints.append(f"· **{x}** ↔ **{y}** (r={c:.2f}, p={p:.2g}) → mogelijk sterk verband.")
    return hints

hints = causale_hints(df, types)
if hints:
    st.subheader("🔗 Mogelijke causale verbanden")
    for h in hints:
        st.write(h)

# ---------- ADVIES ----------
def geef_advies(df, types, hints):
    advies = []
    advies.append("### Samenvatting & Advies\n")
    if types["num"]:
        desc = df[types["num"]].describe()
        hoog = (desc.loc["std"]/desc.loc["mean"]).sort_values(ascending=False)
        advies.append(f"· De variabele **{hoog.index[0]}** toont de grootste spreiding (cv={hoog.iloc[0]:.2f}).")
    if hints:
        advies.append("· Er zijn sterke correlaties gevonden; overweeg verder onderzoek naar causaliteit.")
    if types["cat"]:
        for col in types["cat"][:3]:
            top = df[col].value_counts(normalize=True).iloc[0]
            if top > 0.5:
                advies.append(f"· In **{col}** domineert de categorie '{df[col].value_counts().index[0]}' ({top*100:.0f}%).")
    miss = df.isna().mean()
    if miss.max() > 0.1:
        advies.append(f"· Let op: **{miss.idxmax()}** mist {miss.max()*100:.0f}% van de waarden.")
    return "\n".join(advies)

st.markdown(geef_advies(df, types, hints))

# ---------- OPTIONAL AI NARRATIVE ----------
HF_TOKEN = st.secrets.get("HF_TOKEN") or os.getenv("HF_TOKEN")
if HF_TOKEN and st.checkbox("🧠 Genereer een AI-verhaal (vereist HF-token)"):
    import requests, json
    HF_URL = "https://api-inference.huggingface.co/models/ai21labs/AI21-Jamba-Reasoning-3B"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type":"application/json"}
    prompt = f"""Vat in 4 korte Nederlandse zinnen de belangrijkste inzichten uit deze analyse:
    {geef_advies(df, types, hints)}"""
    payload = json.dumps({"inputs": prompt})
    try:
        resp = requests.post(HF_URL, headers=headers, data=payload, timeout=60)
        if resp.status_code == 200:
            st.write("**AI-verhaal:**", resp.json()[0]["generated_text"])
        else:
            st.write("AI-model nog aan het opstarten...", resp.status_code)
    except Exception as e:
        st.write("AI-fout:", e)
