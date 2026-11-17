import streamlit as st

st.set_page_config(
    page_title="Public transit dashboard",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="locked",
)

dashboard_page = st.Page(
    "dashboard.py",
    title="Dashboard",
    default=True,
)

agency_detail_page = st.Page(
    "pages/agency.py",
    title="Agency Detail",
)

pg = st.navigation([dashboard_page, agency_detail_page], position="hidden")

pg.run()
