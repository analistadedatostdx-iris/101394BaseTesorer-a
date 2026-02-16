import streamlit as st
import zipfile
import io
import pandas as pd
import re
import unicodedata
def run():
    st.title("Flujo de caja")

    # ---------- Normalizar y Encontrar columna  ----------
    def normalize(text):
        text = str(text).lower()
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        return re.sub(r'[^a-z0-9]', '', text)


    def find_column(columns, keywords):
        normalized_cols = {normalize(col): col for col in columns}

        for key in keywords:
            key_norm = normalize(key)
            for col_norm, original_col in normalized_cols.items():
                if key_norm in col_norm or col_norm in key_norm:
                    return original_col

        return None


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

    # ---------- Detectar header  ----------
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

        df = pd.read_excel(file, header=header_row)
        return df


    # ---------- Mapeo ----------
    COLUMN_MAP = {
        "categoria": ["categoria"],
        "concepto": ["concepto"],
        "valor": ["vlr", "valor"],
        "fecha": ["fecha", "date"]
    }




    # ---------- Estandarizar ----------
    def standardize_df(df):
        cols = df.columns.tolist()
        n = len(df)

        categoria_col = find_column(cols, COLUMN_MAP["categoria"])
        concepto_col = find_column(cols, COLUMN_MAP["concepto"])
        valor_col = find_column(cols, COLUMN_MAP["valor"])
        fecha_col = find_column(cols, COLUMN_MAP["fecha"])

        categoria = df[categoria_col] if categoria_col else pd.Series([None]*n)
        concepto = df[concepto_col] if concepto_col else pd.Series([None]*n)

        if valor_col:
            total = clean_money(df[valor_col])
        else:
            total = pd.Series([0]*n)

        if fecha_col:
            fecha = (
            pd.to_datetime(df[fecha_col], errors="coerce", utc=True)
                .dt.tz_localize(None)
            )



        else:
            fecha = pd.Series([pd.NaT]*n)

        return pd.DataFrame({
            "fecha": fecha,
            "categoria": categoria,
            "concepto": concepto,
            "Total": total
        })




    # ---------- Streamlit ----------
    # Seleccionar mes 
    mes_seleccionado = st.selectbox(
    "Selecciona el mes a analizar",
    list(range(1,13)),
    format_func=lambda x: pd.to_datetime(f"2024-{x}-01").strftime("%B")
    )

    #Zip 
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

                        st.write(f"📄 {file}")
                        st.write("Columnas detectadas:", df.columns.tolist())

                        clean_df = standardize_df(df)

                        rows_before = len(df)
                        rows_after = len(clean_df.dropna(how="all"))

                        report.append({
                            "archivo": file,
                            "filas_originales": rows_before,
                            "filas_utiles": rows_after
                        })

                        if rows_after > 0:
                            all_data.append(clean_df)

                    except Exception as e:
                        report.append({
                            "archivo": file,
                            "filas_originales": 0,
                            "filas_utiles": 0,
                            "error": str(e)
                        })

        st.subheader("Reporte de lectura por archivo")
        st.dataframe(pd.DataFrame(report))

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)

            st.success("Consolidado listo")
            st.dataframe(final_df.head())

            output = io.BytesIO()
            final_df.to_excel(output, index=False)
            output.seek(0)

            st.download_button(
                "Descargar Excel consolidado",
                output,
                "consolidado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("Ningún archivo aportó datos útiles.")
