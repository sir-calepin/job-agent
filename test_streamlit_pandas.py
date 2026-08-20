import streamlit as st
import pandas as pd

st.title("Pandas test")
st.write(f"Pandas version: {pd.__version__}")
st.dataframe(pd.DataFrame({
    "role": ["Data Analyst", "BI Analyst"],
    "score": [85, 90],
}))