import streamlit as st
import io
import pandas as pd

def run():
    st.title("Flujo de caja - Desde Excel consolidado")

    # ---------- Subir Excel consolidado ----------
    uploaded_file = st.file_uploader("Sube el Excel consolidado", type="xlsx")

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        st.subheader("Datos originales")
        st.dataframe(df)

        # ---------- Filtrar por mes ----------
        if "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            mes_seleccionado = st.selectbox(
                "Selecciona el mes a analizar",
                list(range(1, 13)),
                format_func=lambda x: pd.to_datetime(f"2024-{x}-01").strftime("%B")
            )
            df = df[df["fecha"].dt.month == mes_seleccionado]

        # ---------- Pivot por archivo (si existe columna archivo_origen) ----------
        if "archivo_origen" in df.columns:
            pivot_df = (
                df
                .groupby(["categoria", "concepto", "fecha", "archivo_origen"], dropna=False)["Total"]
                .sum()
                .reset_index()
                .pivot_table(
                    index=["categoria", "concepto", "fecha"],
                    columns="archivo_origen",
                    values="Total",
                    fill_value=0
                )
                .reset_index()
            )
            pivot_df.columns.name = None
            pivot_df["Total"] = pivot_df.drop(columns=["categoria", "concepto", "fecha"]).sum(axis=1)
        else:
            pivot_df = df.copy()
            if "Total" not in pivot_df.columns:
                pivot_df["Total"] = 0

        st.subheader("Consolidado por archivo")
        st.dataframe(pivot_df)

        # ---------- Resumen por concepto (exacto) ----------
        total_columns = [col for col in pivot_df.columns if col not in ["categoria", "concepto", "fecha"]]

        resumen_df = (
            pivot_df.groupby("concepto", dropna=False)[total_columns]
            .sum()
            .reset_index()
        )

        st.subheader("Resumen por concepto")
        st.dataframe(resumen_df)

        output_resumen = io.BytesIO()
        resumen_df.to_excel(output_resumen, index=False)
        output_resumen.seek(0)

        st.download_button(
            "Descargar Flujo de Caja",
            output_resumen,
            "flujocaja.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )