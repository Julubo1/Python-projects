# app.py  (volledige nieuwe versie)
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import phik
import io, os

# ---------- CONFIG ----------
st.set_page_config(page_title="Auto-Analyse + handige keuzes", layout="wide")
st.title("📊 Automatische Data-analyse + eigen kolommen-verkenner")

# ---------- UPLOAD ----------
uploaded = st.file_uploader("Upload CSV of Excel", type=["csv","xlsx","xls"])
if not uploaded:
    st.stop()

# ---------- READ ----------
@st.cache_data
def read_file(f):
    return pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)

df = read_file(uploaded)
st.success(f"Dataset geladen: {df.shape[0]} rijen × {df.shape[1]} kolommen")

# ---------- KEUZEBLOK ----------
st.subheader("🔍 Kies twee kolommen voor maatwerk-analyse")
left, right = st.columns(2)
with left:
    col1 = st.selectbox("Kolom 1", df.columns)
with right:
    col2 = st.selectbox("Kolom 2", df.columns, index=1 if len(df.columns)>1 else 0)

if col1 == col2:
    st.warning("Kies twee verschillende kolommen.")
    st.stop()

s1, s2 = df[col1], df[col2]
cat1, cat2 = s1.dtype == "object", s2.dtype == "object"
num1, num2 = pd.api.types.is_numeric_dtype(s1), pd.api.types.is_numeric_dtype(s2)

st.subheader(f"Analyse: **{col1}** vs **{col2}**")

# 1. Categorisch + Numeriek  →  gemiddelde/som per categorie
if (cat1 and num2) or (cat2 and num1):
    cat_col, num_col = (col1, col2) if cat1 else (col2, col1)
    tmp = df.groupby(cat_col)[num_col].agg(["mean","sum","count"]).sort_values("mean", ascending=False)
    st.write("Gemiddelde (en som) per categorie:")
    st.dataframe(tmp)
    fig, ax = plt.subplots()
    sns.barplot(x=tmp.index, y=tmp["mean"], ax=ax, palette="viridis")
    ax.set_title(f"Gemiddeld {num_col} per {cat_col}")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

# 2. Beide categorisch  →  crosstab + heatmap
elif cat1 and cat2:
    ct = pd.crosstab(df[col1], df[col2], normalize="index")
    st.write("Relatieve verdeling (rij-som = 100%):")
    st.dataframe(ct.round(3))
    fig, ax = plt.subplots()
    sns.heatmap(ct, annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
    ax.set_title(f"Crosstab: {col1} vs {col2}")
    st.pyplot(fig)

# 3. Beide numeriek  →  scatter + correlatie
elif num1 and num2:
    df_clean = df[[col1, col2]].dropna()
    r, p = stats.pearsonr(df_clean[col1], df_clean[col2])
    st.metric("Pearson r", f"{r:.2f}", delta=f"p = {p:.3g}")
    fig, ax = plt.subplots()
    sns.regplot(x=col1, y=col2, data=df_clean, ax=ax, line_kws={"color":"red"})
    ax.set_title(f"Scatter: {col1} vs {col2}")
    st.pyplot(fig)

# 4. Overige combi’s (bijv. datetime + iets) → simpel box/hist
else:
    st.info("Geen standaard-combinatie herkend; hier een boxplot van de numerieke kolom.")
    num_col = col1 if num1 else col2
    cat_col = col1 if cat1 else col2
    fig, ax = plt.subplots()
    sns.boxplot(x=cat_col, y=num_col, data=df, ax=ax)
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

# ---------- EIND KEUZEBLOK ----------

# ---------- REST VAN DE AUTO-ANALYSE (OPTIONEEL) ----------
with st.expander("📈 Algemene dataset-analyse (zoals eerder)"):
    # hier plak je eventueel de gehele vorige automatische analyse
    st.write("Plaats hier de rest van je vorige code …")
