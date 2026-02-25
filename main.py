import streamlit as st
from procesos import consolidadobancos, seguimientodiario

st.sidebar.title("📊 Procesos")

opcion = st.sidebar.selectbox(
    "¿Qué proceso quieres usar?",
    ["Consolidado bancos", "Seguimiento Diario"]
)

if opcion == "Consolidado bancos":
    consolidadobancos()

elif opcion == "Seguimiento Diario":
    seguimientodiario.run()