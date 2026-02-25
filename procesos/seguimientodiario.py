import streamlit as st
import zipfile
import io
import pandas as pd
import re
import unicodedata




def run():
    st.title("Seguimiento Diario")



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


        return pd.read_excel(file, header=header_row), header_row



    # ---------- Mapeo ----------
    COLUMN_MAP = {
        "categoria": ["categoria"],
        "concepto": ["concepto"],
        "valor": [
            "vlr flujo",
            "valor dc",
            "valor d/c",
            "vlr",
            "valor",
            "valor de la compra",
        ],
        "fecha": ["fecha", "date", "fecha movimiento", "fecha valor", "fecha transaccion"],
    }



    # ---------- Estandarizar ----------
    def standardize_df(df, filename):
        cols = df.columns.tolist()
        n = len(df)


        categoria_col = find_column(cols, COLUMN_MAP["categoria"])
        concepto_col  = find_column(cols, COLUMN_MAP["concepto"])
        valor_col     = find_column(cols, COLUMN_MAP["valor"])
        fecha_col     = find_column(cols, COLUMN_MAP["fecha"])


        categoria = df[categoria_col] if categoria_col else pd.Series([None] * n)
        concepto  = df[concepto_col]  if concepto_col  else pd.Series([None] * n)
        total     = clean_money(df[valor_col]) if valor_col else pd.Series([0] * n)


        if fecha_col:
            parsed = pd.to_datetime(df[fecha_col], errors="coerce", utc=True)
            fecha  = parsed.dt.tz_convert(None).dt.normalize()
        else:
            fecha = pd.Series([pd.NaT] * n)


        return pd.DataFrame({
            "categoria":      categoria.values,
            "concepto":       concepto.values,
            "banco":          filename,
            "fecha":          fecha.values,
            "Total":          total.values,
        })



    # ---------- ZIP ----------
    zip_file = st.file_uploader("Suba el ZIP con los Excel", type="zip")


    if zip_file is not None:
        all_data = []
        report   = []


        with zipfile.ZipFile(io.BytesIO(zip_file.read())) as z:
            excel_files = [f for f in z.namelist() if f.endswith(".xlsx")]
            st.write("Archivos encontrados:", excel_files)


            for file in excel_files:
                with z.open(file) as f:
                    try:
                        df, header_row = read_real_excel(f)
                        clean_df = standardize_df(df, file)


                        report.append({
                            "archivo":          file,
                            "filas_originales": len(df),
                            "filas_utiles":     len(clean_df),
                        })


                        all_data.append(clean_df)


                    except Exception as e:
                        report.append({"archivo": file, "error": str(e)})
                        st.exception(e)


        st.subheader("Reporte de lectura por archivo")
        st.dataframe(pd.DataFrame(report))


        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)


            # ---------- ELIMINAR FILAS SIN FECHA ----------
            final_df = final_df.dropna(subset=["fecha"])


            if final_df.empty:
                st.warning("No hay datos con fechas válidas. Revisa el debug de fechas arriba.")
            else:
                # ---------- RESUMEN DIARIO POR BANCO ----------
                pivot_df = (
                    final_df
                    .groupby(["fecha", "banco"])["Total"]
                    .sum()
                    .unstack(fill_value=0)
                    .reset_index()
                )


                # ---------- TOTAL DIARIO ----------
                columnas_bancos = pivot_df.columns.drop("fecha")
                pivot_df["Total diario"] = pivot_df[columnas_bancos].sum(axis=1)


                # ---------- ORDENAR ----------
                pivot_df = pivot_df.sort_values("fecha").reset_index(drop=True)


                # ---------- TOTAL ACUMULADO MES ----------
                pivot_df["Total acumulado mes"] = pivot_df["Total diario"].cumsum()


                pivot_df.columns.name = None


                # ---------- FILA DE TOTALES POR COLUMNA ----------
                numeric_cols = pivot_df.select_dtypes(include="number").columns.tolist()
                totals_row = {col: pivot_df[col].sum() for col in numeric_cols}
                totals_row["fecha"] = "TOTAL"
                # "Total acumulado mes" en la fila de totales no tiene sentido
                # como suma de acumulados; se reemplaza con el valor final del periodo
                totals_row["Total acumulado mes"] = pivot_df["Total acumulado mes"].iloc[-1]
                pivot_df_display = pd.concat(
                    [pivot_df, pd.DataFrame([totals_row])],
                    ignore_index=True
                )


                st.success("Resumen diario por banco listo")
                st.dataframe(pivot_df_display)


                # ---------- DESCARGAR (con fila de totales) ----------
                output = io.BytesIO()
                pivot_df_display.to_excel(output, index=False)
                output.seek(0)


                st.download_button(
                    "Descargar Excel",
                    output,
                    "flujo_diario_bancos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.error("Ningún archivo aportó datos útiles.")
