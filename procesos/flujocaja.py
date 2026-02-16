import streamlit as st
import io
import pandas as pd
import re
import unicodedata

def run():
    st.title("Flujo de caja - Desde Excel consolidado")

    # ---------- Normalizar texto ----------
    def normalize(text):
        text = str(text).lower()
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        return re.sub(r'[^a-z0-9]', '', text)

    # ---------- Limpiar valores monetarios ----------
    def clean_money(series):
        return (
            series.astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.strip()
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    # ---------- Subir Excel consolidado ----------
    uploaded_file = st.file_uploader("Sube el Excel consolidado", type="xlsx")

    if uploaded_file is not None:
        # Leer el Excel
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

        # ---------- Pivot por archivo ----------
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

            st.subheader("Consolidado por archivo")
            st.dataframe(pivot_df)
        else:
            pivot_df = df.copy()
            if "Total" not in pivot_df.columns:
                pivot_df["Total"] = clean_money(pivot_df["Total"] if "Total" in pivot_df.columns else 0)

        # ---------- Resumen por concepto ----------
        def normalize_concept(text):
            text = str(text).lower().strip()
            text = text.split(". ", 1)[-1] if ". " in text else text
            return text

        pivot_df["concepto_normalizado"] = pivot_df["concepto"].apply(normalize_concept)
        total_columns = [col for col in pivot_df.columns if col not in ["categoria", "concepto", "fecha", "concepto_normalizado"]]

        resumen_df = (
            pivot_df.groupby("concepto_normalizado", dropna=False)[total_columns]
            .sum()
            .reset_index()
        )
        resumen_df["concepto"] = resumen_df["concepto_normalizado"]

        st.subheader("Resumen por concepto")
        st.dataframe(resumen_df)

        # ---------- Botones de descarga ----------
        output_consolidado = io.BytesIO()
        pivot_df.to_excel(output_consolidado, index=False)
        output_consolidado.seek(0)

        st.download_button(
            "Descargar Excel consolidado",
            output_consolidado,
            "consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        output_resumen = io.BytesIO()
        resumen_df.to_excel(output_resumen, index=False)
        output_resumen.seek(0)

        st.download_button(
            "Descargar Excel resumen por concepto",
            output_resumen,
            "resumen_por_concepto.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
