import streamlit as st
import requests

st.title("Mini SaaS Multi-Client")

client = st.selectbox("Choisissez le client", ["Client A", "Client B"])
question = st.text_input("Votre question")

if st.button("Envoyer"):
    api_key = "tenantA_key" if client == "Client A" else "tenantB_key"

    response = requests.post(
        "http://127.0.0.1:8000/ask",
        params={"question": question},
        headers={"X-API-KEY": api_key}
    )

    st.json(response.json())
