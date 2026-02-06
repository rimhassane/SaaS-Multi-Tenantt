import streamlit as st
import requests

st.set_page_config(page_title="RAG Multi-Client", layout="wide")
st.title("SaaS Multi-Client RAG")

col1, col2 = st.columns([2, 1])

with col1:
    client = st.selectbox("Choisissez le client", ["Client A", "Client B"])
    question = st.text_input("Votre question", placeholder="Posez votre question...")

with col2:
    st.metric("API Status", "Connecté")

if st.button(" Envoyer", type="primary"):
    if not question.strip():
        st.warning("Veuillez entrer une question")
    else:
        api_key = "tenantA_key" if client == "Client A" else "tenantB_key"
        
        with st.spinner("Recherche des documents et génération de la réponse..."):
            try:
                response = requests.post(
                    "http://127.0.0.1:8000/ask",
                    params={"question": question},
                    headers={"X-API-KEY": api_key},
                    timeout=120
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Afficher la réponse
                    st.success("✅ Réponse générée")
                    st.markdown("### Réponse")
                    st.info(data.get("answer", "Pas de réponse"))
                    
                    # Afficher les sources et confiance
                    col1, col2 = st.columns(2)
                    with col1:
                        sources = data.get("sources", [])
                        if sources:
                            st.markdown("**📄 Sources:**")
                            for source in sources:
                                st.write(f"• {source}")
                        else:
                            st.write("Aucune source")
                    
                    with col2:
                        confidence = data.get("confidence", 0)
                        st.metric("Confiance", f"{confidence:.0%}")
                else:
                    st.error(f"Erreur API: {response.status_code}")
                    st.write(response.text)
            except requests.exceptions.ConnectionError:
                st.error("❌ Impossible de se connecter au serveur. Assurez-vous que le backend est lancé sur http://127.0.0.1:8000")
            except Exception as e:
                st.error(f"Erreur: {str(e)}")
