import streamlit as st
import io
import pandas as pd
import re
import unicodedata


def run():
    st.title("Flujo de caja diario")

    # ---------- Normalizar ----------
    def normalize(text):
        text = str(text).lower()
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        return re.sub(r'[^a-z0-9]', '', text)

    # ---------- Encontrar Columna ----------
    def find_column(columns, keywords):
        normalized_cols = {normalize(col): col for col in columns}
        for key in keywords:
            key_norm = normalize(key)
            for col_norm, original_col in normalized_cols.items():
                if key_norm in col_norm or col_norm in key_norm:
                    return original_col
        return None

    # ---------- Transformar Dinero ----------
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

    # ---------- Mapeo ----------
    COLUMN_MAP = {
        "categoria": ["categoria"],
        "concepto": ["concepto"],
        "valor": ["vlr", "valor", "total"],
        "fecha": ["fecha", "date"],
        "banco": ["archivo_origen", "banco", "cuenta"]
    }

    # ---------- Estandarizar ----------
    def standardize_df(df):
        cols = df.columns.tolist()
        n = len(df)

        categoria_col = find_column(cols, COLUMN_MAP["categoria"])
        concepto_col = find_column(cols, COLUMN_MAP["concepto"])
        valor_col = find_column(cols, COLUMN_MAP["valor"])
        fecha_col = find_column(cols, COLUMN_MAP["fecha"])
        banco_col = find_column(cols, COLUMN_MAP["banco"])

        categoria = df[categoria_col] if categoria_col else pd.Series([None] * n)
        concepto = df[concepto_col] if concepto_col else pd.Series([None] * n)
        banco = df[banco_col] if banco_col else pd.Series(["Banco"] * n)

        total = clean_money(df[valor_col]) if valor_col else pd.Series([0] * n)

        if fecha_col:
            fecha = (
                pd.to_datetime(df[fecha_col], errors="coerce")
                .dt.normalize()
            )
        else:
            fecha = pd.Series([pd.NaT] * n)

        return pd.DataFrame({
            "categoria": categoria,
            "concepto": concepto,
            "banco": banco,
            "fecha": fecha,
            "Total": total
        })

    # ---------- Upload Excel ----------
    file = st.file_uploader("Suba el Excel consolidado", type=["xlsx", "xls"])

    if file is not None:
        try:
            df_raw = pd.read_excel(file)
            df = standardize_df(df_raw)

            df = df.dropna(subset=["fecha"])

            # ---------- RESUMEN DIARIO POR BANCO ----------
            pivot_df = (
                df
                .groupby(["fecha", "banco"])["Total"]
                .sum()
                .unstack(fill_value=0)
                .reset_index()
            )

            # ---------- TOTAL DIARIO ----------
            columnas_bancos = pivot_df.columns.drop("fecha")
            pivot_df["Total diario"] = pivot_df[columnas_bancos].sum(axis=1)

            # ordenar
            pivot_df = pivot_df.sort_values("fecha")

            # ---------- TOTAL ACUMULADO MES ----------
            pivot_df["Total acumulado mes"] = (
                pivot_df
                .groupby(pivot_df["fecha"].dt.to_period("M"))["Total diario"]
                .cumsum()
            )

            st.success("Resumen diario por banco listo")
            st.dataframe(pivot_df)

            # descargar
            output = io.BytesIO()
            pivot_df.to_excel(output, index=False)
            output.seek(0)

            st.download_button(
                "Descargar Excel",
                output,
                "flujo_diario_bancos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Error leyendo el archivo: {e}")
