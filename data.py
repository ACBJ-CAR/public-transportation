from pathlib import Path

import pandas as pd
import streamlit as st

LOCAL_DATA_FOLDER = Path("./")
DATA_PATH = LOCAL_DATA_FOLDER / "dashboard_data" / "september_2026.parquet"

BASELINE_YEAR = "2019"
GROUP_COLUMNS = ["NTD ID", "Agency", "UZA Name"]

MODES = {
    "AR": "Alaska Railroad",
    "CC": "Cable Car",
    "CR": "Commuter Rail",
    "HR": "Heavy Rail (Subway / Metro)",
    "IP": "Inclined Plane",
    "LR": "Light Rail",
    "MG": "Monorail / Automated Guideway",
    "SR": "Streetcar Rail",
    "YR": "Hybrid Rail",
    "CB": "Commuter Bus",
    "DR": "Demand Response (Paratransit)",
    "FB": "Ferryboat",
    "JT": "Jitney",
    "MB": "Bus (Fixed-route bus)",
    "PB": "Público (common in Puerto Rico)",
    "RB": "Bus Rapid Transit (BRT)",
    "TB": "Trolleybus",
    "TR": "Aerial Tramway",
    "VP": "Vanpool",
}

TYPES_OF_SERVICE = {
    "DO": "Directly Operated",
    "PT": "Purchased Transportation — General",
    "TX": "Purchased Transportation – Taxi",
    "TN": "Purchased Transportation — Transportation Network Company",
}


# ---------- Loading ----------


def load_ridership(path=DATA_PATH):
    df = pd.read_parquet(path)
    df["UZA Name"] = df["UZA Name"].str.replace("--", "-", regex=False)
    return df


# ---------- Date / column helpers ----------


def get_current_year(df):
    return df.columns[-1][-4:]


def get_month_columns(df, year):
    return [column for column in df.columns if column.endswith(f"/{year}")]


def get_latest_month(month_columns):
    # int() so "10" sorts after "9"
    return str(max(int(column.split("/")[0]) for column in month_columns))


def format_month(month, year):
    month_name = pd.to_datetime(month, format="%m").month_name()
    return f"{month_name} {year}"


def get_comparison_columns(month_columns, baseline_year=BASELINE_YEAR):
    return [f"{column.split('/')[0]}/{baseline_year}" for column in month_columns]


def ytd_column_name(year):
    return f"{year} YTD Ridership"


# ---------- Math ----------


def to_numeric(df, columns):
    df = df.copy()
    df[columns] = df[columns].replace(",", "", regex=True).apply(pd.to_numeric)
    return df


def sum_by_group(df, group_columns, value_columns):
    return df.groupby(group_columns)[value_columns].sum(min_count=1).reset_index()


def ytd_total(df, month_columns):
    return df[month_columns].sum(axis=1, min_count=1)


def safe_pct(numerator, denominator):
    """numerator / denominator * 100, NaN where denominator is 0."""
    return numerator.div(denominator).mul(100).where(denominator.ne(0))


def add_ytd_comparison(
    df, current_columns, baseline_columns, current_col, baseline_col
):
    df = df.copy()
    df[current_col] = ytd_total(df, current_columns)
    df[baseline_col] = ytd_total(df, baseline_columns)
    df["YTD Change"] = df[current_col] - df[baseline_col]
    df["YTD Change (%)"] = safe_pct(df["YTD Change"], df[baseline_col])
    df[f"YTD percent of {BASELINE_YEAR}"] = safe_pct(df[current_col], df[baseline_col])
    return df


# ---------- Pipeline ----------


def build_agency_summary(
    df, current_year, month_columns, comparison_columns, modes=None
):
    if modes:
        df = df[df["Mode"].isin(modes)]

    ridership_columns = month_columns + comparison_columns
    current_col = ytd_column_name(current_year)
    baseline_col = ytd_column_name(BASELINE_YEAR)

    agency_df = to_numeric(df[[*GROUP_COLUMNS, *ridership_columns]], ridership_columns)
    by_agency = sum_by_group(agency_df, GROUP_COLUMNS, ridership_columns)
    by_agency = add_ytd_comparison(
        by_agency, month_columns, comparison_columns, current_col, baseline_col
    )

    return (
        by_agency[
            [
                *GROUP_COLUMNS,
                current_col,
                baseline_col,
                f"YTD percent of {BASELINE_YEAR}",
            ]
        ]
        .sort_values(by=current_col, ascending=False)
        .rename(columns={"UZA Name": "Metro Area"})
    )


# ---------- Module-level values ----------

ridership_df = load_ridership()
modes = MODES
types_of_service = TYPES_OF_SERVICE

current_year = get_current_year(ridership_df)
month_columns = get_month_columns(ridership_df, current_year)
latest_month = get_latest_month(month_columns)
latest_month_fmt = format_month(latest_month, current_year)
comparison_month_columns = get_comparison_columns(month_columns)

current_ytd_column = ytd_column_name(current_year)
baseline_ytd_column = ytd_column_name(BASELINE_YEAR)

agency_summary_df = build_agency_summary(
    ridership_df, current_year, month_columns, comparison_month_columns
)


@st.cache_data(scope="global")
def get_agency_summary(selected_modes=()):
    """Agency summary limited to the selected modes (all modes if none selected)."""
    if not selected_modes:
        return agency_summary_df
    return build_agency_summary(
        ridership_df,
        current_year,
        month_columns,
        comparison_month_columns,
        modes=list(selected_modes),
    )


# ---------- Sidebar filters ----------


@st.cache_data(scope="global")
def unique_values(column):
    return agency_summary_df[column].dropna().drop_duplicates().sort_values().tolist()


def sidebar_multiselect(label, column):
    return st.sidebar.multiselect(label, unique_values(column))


def msa_filter():
    return sidebar_multiselect("Metro area", "Metro Area")


def agency_filter():
    return sidebar_multiselect("Agency", "Agency")


@st.cache_data(scope="global")
def available_modes():
    codes = ridership_df["Mode"].dropna().unique().tolist()
    return sorted(codes, key=lambda code: MODES.get(code, code))


def mode_filter():
    return st.sidebar.multiselect(
        "Mode",
        available_modes(),
        format_func=lambda code: MODES.get(code, code),
    )
