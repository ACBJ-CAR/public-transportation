import altair as alt
import pandas as pd
import streamlit as st

from data import modes, ridership_df

if st.button("← Back to dashboard"):
    st.switch_page("dashboard.py")

agency_id_value = st.query_params.get("id")
if agency_id_value is None:
    agency_id_value = st.session_state.get("selected_agency")

if agency_id_value is None:
    st.error("No agency selected. Return to the dashboard and choose an agency.")
    st.stop()

try:
    agency_id = int(agency_id_value)
except (TypeError, ValueError):
    st.error("The agency ID in the page URL is invalid.")
    st.stop()

st.query_params["id"] = str(agency_id)

agency_df = ridership_df.loc[ridership_df["NTD ID"] == agency_id].copy()
if agency_df.empty:
    st.error(f"No ridership records were found for agency ID {agency_id}.")
    st.stop()

agency_name = agency_df.iloc[0]["Agency"]
st.title(agency_name)
st.caption(f"National Transit Database agency ID: {agency_id}")

month_columns = [
    column
    for column in agency_df.columns
    if len(column.split("/")) == 2 and all(part.isdigit() for part in column.split("/"))
]
month_columns.sort(key=lambda column: pd.to_datetime(column, format="%m/%Y"))

if not month_columns:
    st.error("No monthly ridership columns are available for this agency.")
    st.stop()

monthly_values = (
    agency_df[month_columns]
    .replace(",", "", regex=True)
    .apply(pd.to_numeric, errors="coerce")
)
monthly_totals = monthly_values.sum(axis=0, min_count=1)
monthly_df = pd.DataFrame(
    {
        "Month": pd.to_datetime(month_columns, format="%m/%Y"),
        "Ridership": monthly_totals.to_numpy(),
    }
).sort_values("Month")

reported_months = monthly_df.dropna(subset=["Ridership"])
if reported_months.empty:
    st.error("No monthly ridership values are available for this agency.")
    st.stop()

latest = reported_months.iloc[-1]
latest_month = latest["Month"]
latest_ridership = latest["Ridership"]
latest_label = latest_month.strftime("%B %Y")

ridership_by_month = monthly_df.set_index("Month")["Ridership"]
same_month_2019 = ridership_by_month.get(
    pd.Timestamp(year=2019, month=latest_month.month, day=1)
)
latest_month_recovery = (
    latest_ridership / same_month_2019
    if pd.notna(same_month_2019) and same_month_2019 != 0
    else float("nan")
)

ytd_dates = pd.date_range(
    start=pd.Timestamp(year=latest_month.year, month=1, day=1),
    end=latest_month,
    freq="MS",
)
current_ytd = ridership_by_month.reindex(ytd_dates)
baseline_dates = pd.DatetimeIndex(
    [pd.Timestamp(year=2019, month=month.month, day=1) for month in ytd_dates]
)
baseline_ytd = ridership_by_month.reindex(baseline_dates)
current_ytd = current_ytd.reset_index(drop=True)
baseline_ytd = baseline_ytd.reset_index(drop=True)
comparable_months = current_ytd.notna() & baseline_ytd.notna()
ytd_ridership = current_ytd.sum(min_count=1)
ytd_current_comparable = current_ytd[comparable_months].sum(min_count=1)
ytd_2019_comparable = baseline_ytd[comparable_months].sum(min_count=1)
ytd_recovery = (
    ytd_current_comparable / ytd_2019_comparable
    if pd.notna(ytd_2019_comparable) and ytd_2019_comparable != 0
    else float("nan")
)

if pd.notna(latest_month_recovery):
    st.markdown(
        f"In **{latest_label}**, {agency_name} reported **{latest_ridership:,.0f}** "
        f"rides — **{latest_month_recovery:.1%}** of its ridership in "
        f"{latest_month.strftime('%B')} 2019."
    )
else:
    st.markdown(
        f"The latest available report for {agency_name} is **{latest_label}**, "
        f"with **{latest_ridership:,.0f}** rides. A same-month 2019 comparison "
        "is unavailable."
    )

st.subheader("Latest month")
st.caption(
    f"One-month totals for {latest_label}, compared with {latest_month.strftime('%B')} 2019."
)
monthly_metric_columns = st.columns(2)
monthly_metric_columns[0].metric(
    f"{latest_label} ridership",
    f"{latest_ridership:,.0f}",
)
monthly_metric_columns[1].metric(
    "Share of same month in 2019",
    f"{latest_month_recovery:.1%}" if pd.notna(latest_month_recovery) else "N/A",
)

st.divider()
st.subheader(f"Year to date through {latest_month.strftime('%B')}")
st.caption(
    f"YTD total rides reported in {latest_month.year} months through "
    f"{latest_month.strftime('%B')}. Recovery compares "
    f"{int(comparable_months.sum())} months reported in both periods."
)
ytd_metric_columns = st.columns(2)
ytd_metric_columns[0].metric(
    f"{latest_month.year} YTD ridership",
    f"{ytd_ridership:,.0f}" if pd.notna(ytd_ridership) else "N/A",
)
ytd_metric_columns[1].metric(
    "Share of comparable 2019 YTD ridership",
    f"{ytd_recovery:.1%}" if pd.notna(ytd_recovery) else "N/A",
)

download_data = agency_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download this agency's full dataset (CSV)",
    data=download_data,
    file_name=f"agency_{agency_id}_ridership.csv",
    mime="text/csv",
)

monthly_chart = (
    alt.Chart(monthly_df, title="Monthly ridership")
    .mark_line()
    .encode(
        x=alt.X("Month:T", title=None),
        y=alt.Y("Ridership:Q", title="Rides", axis=alt.Axis(format=",.0f")),
        tooltip=[
            alt.Tooltip("Month:T", title="Month"),
            alt.Tooltip("Ridership:Q", title="Ridership", format=",.0f"),
        ],
    )
)

recovery_df = monthly_df.loc[monthly_df["Month"].dt.year > 2019].copy()
baseline_2019_df = monthly_df.loc[monthly_df["Month"].dt.year == 2019].copy()
baseline_2019_df["Month number"] = baseline_2019_df["Month"].dt.month
baseline_by_month = baseline_2019_df.set_index("Month number")["Ridership"]
recovery_df["2019 ridership"] = recovery_df["Month"].dt.month.map(baseline_by_month)
recovery_df["Recovery"] = (
    recovery_df["Ridership"]
    .div(recovery_df["2019 ridership"])
    .where(recovery_df["2019 ridership"].ne(0))
)

recovery_chart = (
    alt.Chart(
        recovery_df, title="Monthly ridership compared with the same month in 2019"
    )
    .mark_line()
    .encode(
        x=alt.X("Month:T", title=None),
        y=alt.Y(
            "Recovery:Q",
            title="Share of same-month 2019 ridership",
            axis=alt.Axis(format=".0%"),
        ),
        tooltip=[
            alt.Tooltip("Month:T", title="Month"),
            alt.Tooltip("Recovery:Q", title="Of 2019", format=".1%"),
        ],
    )
)
full_recovery_rule = (
    alt.Chart(pd.DataFrame({"Recovery": [1.0]}))
    .mark_rule(color="#777", strokeDash=[5, 5])
    .encode(y="Recovery:Q")
)

chart_columns = st.columns(2)
with chart_columns[0]:
    st.altair_chart(monthly_chart, width="stretch")
with chart_columns[1]:
    if recovery_df["Recovery"].notna().any():
        st.altair_chart(recovery_chart + full_recovery_rule, width="stretch")
    else:
        st.info(
            "A month-by-month recovery chart is unavailable without 2019 comparisons."
        )

mode_rows = monthly_values.copy()
mode_rows["Mode"] = agency_df["Mode"].map(
    lambda mode: (
        modes.get(mode, f"Unmapped mode ({mode})")
        if pd.notna(mode)
        else "Mode not reported"
    )
)
mode_monthly = mode_rows.groupby("Mode", sort=True)[month_columns].sum(min_count=1)
mode_chart_df = mode_monthly.reset_index().melt(
    id_vars="Mode",
    value_vars=month_columns,
    var_name="Month",
    value_name="Ridership",
)
mode_chart_df["Month"] = pd.to_datetime(mode_chart_df["Month"], format="%m/%Y")
mode_chart_df = mode_chart_df.loc[
    mode_chart_df["Month"] >= pd.Timestamp(year=2019, month=1, day=1)
]
mode_options = sorted(mode_chart_df["Mode"].dropna().unique().tolist())

st.subheader("Ridership by mode")
st.caption("Monthly ridership by reported mode, from 2019 onward.")
selected_modes = st.multiselect(
    "Select modes to compare",
    options=mode_options,
    default=mode_options,
    key=f"agency_modes_{agency_id}",
)

if selected_modes:
    selected_mode_data = mode_chart_df.loc[mode_chart_df["Mode"].isin(selected_modes)]
    mode_chart = (
        alt.Chart(selected_mode_data, title="Monthly ridership by mode")
        .mark_line()
        .encode(
            x=alt.X("Month:T", title=None),
            y=alt.Y("Ridership:Q", title="Rides", axis=alt.Axis(format=",.0f")),
            color=alt.Color("Mode:N", title="Mode"),
            tooltip=[
                alt.Tooltip("Mode:N", title="Mode"),
                alt.Tooltip("Month:T", title="Month"),
                alt.Tooltip("Ridership:Q", title="Ridership", format=",.0f"),
            ],
        )
    )
    st.altair_chart(mode_chart, width="stretch")
else:
    st.info("Select at least one mode to see its ridership trend.")

with st.expander("Definitions"):
    st.markdown(
        """
        - **Mode**: The type of transportation service
        - **Demand response**: Any non-fixed route system of transporting individuals that requires advanced scheduling by the customer.
        – **Heavy rail**: An electric railway with the capacity for a heavy volume of traffic. It is characterized by:
        •   High speed and rapid acceleration passenger rail cars operating singly or in multi-car trains on fixed rails
        •   Separate rights-of-way (ROW) from which all other vehicular and foot traffic are excluded
        •   Sophisticated signaling, and
        •   High platform loading.
        """
    )

with st.expander("View the full agency dataset"):
    st.dataframe(agency_df, hide_index=True)
