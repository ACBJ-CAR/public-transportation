import pandas as pd
import streamlit as st

from data import (
    agency_filter,
    agency_summary_df,
    current_year,
    get_agency_summary,
    latest_month,
    latest_month_fmt,
    mode_filter,
    msa_filter,
)

# with ridership_tab:
st.header("Public Transit Data")
# st.subheader(f"Ridership recovery as of {latest_month_fmt}")
st.write(
    "How much has public transportation ridership recovered in your metro? This dashboard compiles Federal Transit Administration (an agency of the Department of Transportation) data for all transit agencies in the U.S. "
    f"The data shown below is ridership through {latest_month_fmt}. The data is updated monthly. \n\n"
    "To update the data shown on this page, select agencies using the boxes on the lefthand side of the table. For more detail on a single agency, click the :material/open_in_new: icon."
)
st.markdown(
    "The ridership figures here are for *unlinked passenger trips*, or UPT, which does not equate to passengers. This is counted each time a rider boards a vehicle. Because of that, transfers count as separate trips. UPT is a measure of system utilization rather than a description of individual passenger journeys. "
    "Individual systems estimate or count the number of passengers they serve using different methods. \n\n"
    "For more information on FTA data, see [this page](https://www.transit.dot.gov/ntd/monthly-ridership)."
)

current_year_ytd_column = f"{current_year} YTD Ridership"
baseline_ytd_column = "2019 YTD Ridership"
metrics_container = st.container()

with st.sidebar:
    st.sidebar.header("Filters")

    min_ridership = st.number_input(
        "Minimum YTD ridership",
        min_value=0,
        value=0,
        step=1_000_000,
    )

    selected_msas = msa_filter()

    selected_agencies = agency_filter()

    selected_modes = mode_filter()

dashboard_df = get_agency_summary(tuple(selected_modes)).copy()

dashboard_df["NTD ID"] = dashboard_df["NTD ID"].astype("Int64").astype(str).str.zfill(5)

dashboard_df = dashboard_df[dashboard_df[current_year_ytd_column] >= min_ridership]

if selected_msas:
    dashboard_df = dashboard_df[dashboard_df["Metro Area"].isin(selected_msas)]

if selected_agencies:
    dashboard_df = dashboard_df[dashboard_df["Agency"].isin(selected_agencies)]

dashboard_df = dashboard_df.reset_index(drop=True)
dashboard_df.index = "agency?id=" + dashboard_df["NTD ID"].astype(str)
dashboard_df.index.name = ""
selection_key = (
    f"agency_selection_{hash((tuple(dashboard_df['NTD ID']), tuple(selected_modes)))}"
)

event = st.dataframe(
    dashboard_df,
    on_select="rerun",
    selection_mode="multi-row",
    key=selection_key,
    hide_index=False,
    column_config={
        "_index": st.column_config.LinkColumn(
            label="Detail",
            display_text=":material/open_in_new:",
            width="x-small",
        ),
        "NTD ID": None,
        current_year_ytd_column: st.column_config.NumberColumn(format="%,d"),
        baseline_ytd_column: st.column_config.NumberColumn(format="%,d"),
        "YTD percent of 2019": st.column_config.NumberColumn(format="%.1f%%"),
        # "Agency detail": st.column_config.LinkColumn(
        #     "Agency detail",
        #     display_text="View agency",
        #     width="small",
        # ),
    },
)

selected_rows = event.selection.rows

if selected_rows:
    metric_df = dashboard_df.iloc[selected_rows]
    metric_scope = f"{len(selected_rows)} selected agenc{'y' if len(selected_rows) == 1 else 'ies'}"
elif selected_msas:
    # Full MSA totals, independent of the min-ridership / agency filters
    metric_df = agency_summary_df[agency_summary_df["Metro Area"].isin(selected_msas)]
    metric_scope = (
        " & ".join(selected_msas)
        if len(selected_msas) <= 2
        else f"{len(selected_msas)} metro areas"
    )
else:
    metric_df = dashboard_df
    metric_scope = "All agencies shown"

current_year_total = metric_df[current_year_ytd_column].sum(min_count=1)
baseline_total = metric_df[baseline_ytd_column].sum(min_count=1)

overall_percent_of_2019 = (
    current_year_total / baseline_total * 100
    if pd.notna(baseline_total) and baseline_total != 0
    else float("nan")
)

months_elapsed = int(latest_month)
monthly_average = (
    current_year_total / months_elapsed
    if pd.notna(current_year_total)
    else float("nan")
)
monthly_average_prior_year = (
    baseline_total / months_elapsed if pd.notna(baseline_total) else float("nan")
)


def fmt_num(value):
    return f"{value:,.0f}" if pd.notna(value) else "N/A"


def sub_caption(text):
    st.markdown(
        f"<div style='font-size:0.8rem; margin-top:-16px;'>{text}</div>",
        unsafe_allow_html=True,
    )


with metrics_container:
    st.caption(f"Showing: **{metric_scope}**")
    col1, col2, col3 = st.columns(3)

    with col1.container(border=True):
        st.metric(
            label=f"{current_year} YTD ridership vs 2019 (same months)",
            value=f"{overall_percent_of_2019:.1f}%"
            if pd.notna(overall_percent_of_2019)
            else "N/A",
        )
        sub_caption("of 2019 levels")

    with col2.container(border=True):
        st.metric(
            label="Average monthly ridership YTD",
            value=fmt_num(monthly_average),
        )
        sub_caption(f"2019 average: {fmt_num(monthly_average_prior_year)}")

    with col3.container(border=True):
        st.metric(
            label="Total ridership YTD",
            value=fmt_num(current_year_total),
        )
        sub_caption(f"2019 total: {fmt_num(baseline_total)}")
