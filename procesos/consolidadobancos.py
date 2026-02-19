import streamlit as st
import zipfile
import io
import pandas as pd
import re
import unicodedata


def run():
    st.title("Flujo de caja")

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

    # ---------- Detectar header ----------
    def is_header_row(row):
        text_cells = [
            str(x).strip() for x in row
            if isinstance(x, str) and len(str(x).strip()) > 0
        ]
        short_texts = [t for t in text_cells if len(t) < 30]
        return len(short_texts) >= 4

    def read_real_excel(file):
        df_raw = pd.read_excel(file, header=None)

        header_row = None
        for i, row in df_raw.iterrows():
            if is_header_row(row):
                header_row = i
                break

        if header_row is None:
            header_row = 0

        return pd.read_excel(file, header=header_row)

    # ---------- Mapeo ----------
    COLUMN_MAP = {
        "categoria": ["categoria"],
        "concepto": ["concepto"],
        "valor": ["vlr", "valor"],
        "fecha": ["fecha", "date"]
    }

    # ---------- Estandarizar ----------
    def standardize_df(df, filename):
        cols = df.columns.tolist()
        n = len(df)

        categoria_col = find_column(cols, COLUMN_MAP["categoria"])
        concepto_col = find_column(cols, COLUMN_MAP["concepto"])
        valor_col = find_column(cols, COLUMN_MAP["valor"])
        fecha_col = find_column(cols, COLUMN_MAP["fecha"])

        categoria = df[categoria_col] if categoria_col else pd.Series([None]*n)
        concepto = df[concepto_col] if concepto_col else pd.Series([None]*n)

        total = clean_money(df[valor_col]) if valor_col else pd.Series([0]*n)

        if fecha_col:
            fecha = (
                pd.to_datetime(df[fecha_col], errors="coerce", utc=True)
                .dt.tz_localize(None)
            )
        else:
            fecha = pd.Series([pd.NaT]*n)

        return pd.DataFrame({
            "categoria": categoria,
            "concepto": concepto,
            "archivo_origen": filename,
            "fecha": fecha,
            "Total": total
        })

    # ---------- Selector de mes ----------
    mes_seleccionado = st.selectbox(
        "Selecciona el mes a analizar",
        list(range(1, 13)),
        format_func=lambda x: pd.to_datetime(f"2024-{x}-01").strftime("%B")
    )

    # ---------- ZIP ----------
    zip_file = st.file_uploader("Suba el ZIP con los Excel", type="zip")

    if zip_file is not None:
        all_data = []
        report = []

        with zipfile.ZipFile(io.BytesIO(zip_file.read())) as z:
            excel_files = [f for f in z.namelist() if f.endswith(".xlsx")]
            st.write("Archivos encontrados:", excel_files)

            for file in excel_files:
                with z.open(file) as f:
                    try:
                        df = read_real_excel(f)
                        clean_df = standardize_df(df, file)

                        report.append({
                            "archivo": file,
                            "filas_originales": len(df),
                            "filas_utiles": len(clean_df)
                        })

                        all_data.append(clean_df)

                    except Exception as e:
                        report.append({
                            "archivo": file,
                            "error": str(e)
                        })

        st.subheader("Reporte de lectura por archivo")
        st.dataframe(pd.DataFrame(report))

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)

            # ---------- FILTRAR POR MES ----------
            final_df = final_df[final_df["fecha"].dt.month == mes_seleccionado]

            # ---------- PIVOT ----------
            pivot_df = (
            final_df
            .groupby(
                ["categoria", "concepto", "fecha", "archivo_origen"],
                dropna=False
            )["Total"]
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
            # Total General
            pivot_df["Total"] = pivot_df.drop(columns=["categoria", "concepto", "fecha"]).sum(axis=1)

            st.success("Consolidado listo")
            st.dataframe(pivot_df)

            output = io.BytesIO()
            pivot_df.to_excel(output, index=False)
            output.seek(0)

            st.download_button(
                "Descargar Excel consolidado",
                output,
                "consolidadobancos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("Ningún archivo aportó datos útiles.")
