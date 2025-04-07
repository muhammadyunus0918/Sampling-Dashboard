import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import io
import xlsxwriter
import folium
from streamlit_folium import st_folium
import joblib
from datetime import datetime

# Load data
st.sidebar.title("Upload Data Sampling Baru")
uploaded_file = st.sidebar.file_uploader("Unggah file CSV", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)
else:
    data_path = "D:/Ngoding/Dashboard Sampling/data/dummy_sampling_with_mgo_sio2.csv"
    df = pd.read_csv(data_path)

# Simpan ke SQLite di folder 'outputs' di dalam Documents
output_dir = os.path.expanduser("~/Documents/outputs")
os.makedirs(output_dir, exist_ok=True)

db_path = os.path.join(output_dir, 'classifications.db')
conn = sqlite3.connect(db_path)
df.to_sql('classified_data', conn, if_exists='replace', index=False)
conn.close()

# Load model ML jika ada
model_path = os.path.join(output_dir, 'model_grade.pkl')
model = None
if os.path.exists(model_path):
    model = joblib.load(model_path)

# Title
st.title("Grade Control Dashboard")

# Sidebar filter
with st.sidebar:
    st.header("Filter Data")
    selected_profil = st.multiselect("Pilih Profil:", df['Profil'].unique(), default=df['Profil'].unique())
    selected_material = st.multiselect("Pilih Material:", df['Material'].unique(), default=df['Material'].unique())
    depth_range = st.slider("Rentang Kedalaman:", float(df['Depth'].min()), float(df['Depth'].max()), (float(df['Depth'].min()), float(df['Depth'].max())))

# Filter data
df_filtered = df[
    (df['Profil'].isin(selected_profil)) &
    (df['Material'].isin(selected_material)) &
    (df['Depth'] >= depth_range[0]) &
    (df['Depth'] <= depth_range[1])
]

# Prediksi Ore Grade (jika model tersedia)
if model:
    st.subheader("Prediksi Ore Grade dari Model ML")
    fitur_model = ['Ni (%)', 'Fe (%)', 'SiO2 (%)', 'MgO (%)']
    if all(col in df_filtered.columns for col in fitur_model):
        prediksi = model.predict(df_filtered[fitur_model])
        df_filtered['Ore Class (Prediksi)'] = prediksi
        st.dataframe(df_filtered[['Ni (%)', 'Fe (%)', 'SiO2 (%)', 'MgO (%)', 'Ore Class (Prediksi)']])

# Tampilkan data
st.subheader("Data Sampling")
st.dataframe(df_filtered)

# Visualisasi 2D (User pilih kolom X dan Y)
st.subheader("Visualisasi 2D Dinamis")
x_axis = st.selectbox("Pilih X Axis:", df_filtered.columns, index=df_filtered.columns.get_loc("Ni (%)"))
y_axis = st.selectbox("Pilih Y Axis:", df_filtered.columns, index=df_filtered.columns.get_loc("Fe (%)"))
fig_dynamic = px.scatter(df_filtered, x=x_axis, y=y_axis, color='Material')
st.plotly_chart(fig_dynamic, use_container_width=True)

# Visualisasi Box Plot tetap
tab1, tab2, tab3 = st.tabs(["Box Plot", "Scatter 3D", "Heatmap"])
with tab1:
    fig_box = px.box(df_filtered, x='Material', y='Ni (%)', color='Material')
    st.plotly_chart(fig_box, use_container_width=True)

# Visualisasi 3D
with tab2:
    st.subheader("Visualisasi 3D")
    fig3 = px.scatter_3d(df_filtered, x='X', y='Y', z='Z', color='Material', symbol='Material')
    st.plotly_chart(fig3, use_container_width=True)

# Heatmap
with tab3:
    st.subheader("Sebaran Heatmap (X-Y berdasarkan Ni (%)")
    fig_heatmap = px.density_heatmap(df_filtered, x='X', y='Y', z='Ni (%)', nbinsx=30, nbinsy=30, color_continuous_scale='Viridis')
    st.plotly_chart(fig_heatmap, use_container_width=True)

# Visualisasi Peta Titik Sampling
st.subheader("Peta Sebaran Sampling (X-Y)")
map_center = [df_filtered['Y'].mean(), df_filtered['X'].mean()]
map_sampling = folium.Map(location=map_center, zoom_start=12)
for _, row in df_filtered.iterrows():
    folium.CircleMarker(
        location=[row['Y'], row['X']],
        radius=4,
        popup=f"Material: {row['Material']}\nNi: {row['Ni (%)']}%",
        color='blue',
        fill=True,
        fill_opacity=0.6
    ).add_to(map_sampling)
st_data = st_folium(map_sampling, width=700, height=500)

# Statistik Ringkas
st.subheader("Statistik Ringkas per Material")
stats = df_filtered.groupby('Material')[['Ni (%)', 'Fe (%)', 'SiO2 (%)', 'MgO (%)']].describe().round(2)
st.dataframe(stats)

# Simpan ke DB (histori klasifikasi)
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
conn = sqlite3.connect(db_path)
df_filtered['created_at'] = now_str
df_filtered.to_sql('classified_data_log', conn, if_exists='append', index=False)
conn.close()

# Ekspor ke CSV
st.subheader("Ekspor Data")
export_path = os.path.join(output_dir, 'classified_data.csv')
df_filtered.to_csv(export_path, index=False)
st.download_button("Download CSV", data=df_filtered.to_csv(index=False), file_name="classified_data.csv", mime="text/csv")

# Ekspor ke Excel
st.subheader("Ekspor ke Excel")
excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
    df_filtered.to_excel(writer, index=False, sheet_name='Filtered Data')
    stats.to_excel(writer, sheet_name='Stats per Material')

excel_buffer.seek(0)
st.download_button("Download Excel", data=excel_buffer, file_name="grade_control_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
