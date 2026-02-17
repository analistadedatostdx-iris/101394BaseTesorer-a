import streamlit as st
from procesos import flujocaja, consolidadobancos, seguimientodiario

st.sidebar.title("📊 Procesos")

opcion = st.sidebar.selectbox(
    "¿Qué proceso quieres usar?",
    ["Consolidado bancos", "Seguimiento Diario", "Flujo de caja"]
)

if opcion == "Flujo de caja":
    flujocaja.run()

elif opcion == "Consolidado bancos":
    consolidadobancos.run()

elif opcion == "Seguimiento Diario":
    seguimientodiario.run()