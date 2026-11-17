# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: public-transportation (3.13.12)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Public transportation

# %%
import calendar
import re
from pathlib import Path

import pandas as pd
from IPython.display import HTML, display

# %%
LOCAL_DATA_FOLDER = Path("./data")


# %%
def get_excel_files():
    excel_files = list((LOCAL_DATA_FOLDER / "source").glob("*.xlsx"))
    if len(excel_files) != 1:
        raise ValueError(f"Expected 1 .xlsx file, found {len(excel_files)}")
    return excel_files


excel_files = get_excel_files()

UPT_data = pd.read_excel(excel_files[0], sheet_name="UPT")

# %%
latest_year = UPT_data.columns[-1][-4:]
max_month = UPT_data.columns[-1].split(sep="/")[0]
latest_month_year = UPT_data.columns[-1]
display(
    HTML(
        f"<h1>Check: The latest month available is {calendar.month_name[int(max_month)]}, {latest_year}</h1>"
    )
)


# %%
def get_comparison_months():
    comparison_months = []
    for year in range(2019, int(latest_year) + 1):
        comparison_months.extend(
            [f"{month}/{year}" for month in range(1, int(max_month))]
        )
    return comparison_months


# for year in range(2019, int(latest_year)+1): # This creates variables named months_YEAR for each year in the data
#     globals()[f"months_{year}"] = [f"{month}/{year}" for month in range(1, int(max_month))]

comparison_months = get_comparison_months()

months_2019 = [f"{month}/2019" for month in range(1, int(max_month))]
months_current_year = [f"{month}/{latest_year}" for month in range(1, int(max_month))]

system_rows = UPT_data.loc[
    UPT_data["NTD ID"].notna()
]  # Just get the rows that have a system ID.

# %%
systems = (  # Grouping by ID and name. Each agency has one ID and one name
    system_rows.groupby(["NTD ID", "Agency"])[comparison_months].sum(min_count=1)
)

# %%
# Only get systems with complete data for all comparison months
# complete = systems[comparison_months].notna().all(axis=1)
# systems = systems.loc[complete].copy()

# %%
complete_systems = systems.loc[systems[comparison_months].notna().all(axis=1)]

rides_2019 = complete_systems[months_2019].sum().sum()
rides_2026 = complete_systems[months_current_year].sum().sum()

difference = rides_2026 - rides_2019
change_pct = difference / rides_2019 * 100

print(f"Jan–Aug 2019: {rides_2019:,.0f} rides")
print(f"Jan–Aug 2026: {rides_2026:,.0f} rides")
print(f"Difference:   {difference:+,.0f} rides ({change_pct:+.1f}%)")


# %% [markdown]
# ## What percent of 2019 average are all US transit systems operating at as of the latest month available?


# %%
def get_national_recovery():
    month_columns = []

    for col in system_rows.columns:
        try:
            pd.to_datetime(col, format="%m/%Y")
            month_columns.append(col)
        except ValueError:
            pass

    total_monthly = UPT_data[month_columns].sum()

    ytd_total = total_monthly[total_monthly.index.isin(months_current_year)].sum()
    ytd_average_2019 = total_monthly[total_monthly.index.isin(months_2019)].sum()

    recovery = ytd_total / ytd_average_2019

    return format(recovery * 100, ".2f")

    # rolling_6mo_total = (
    #     total_monthly
    #     .rolling(window=6, min_periods=6)
    #     .mean()
    # )


natl_recovery_pct = get_national_recovery()
print(f"National recovery compared to 2019: {natl_recovery_pct}%")

# %%
GROUP_KEYS = {
    "metro": ["UZA Name"],
    "agency": ["NTD ID", "Agency", "UZA Name"],
}


def ytd_totals(level="metro", rows=None, through_month=None, annual=False):
    """
    Year-to-date ridership by metro or agency.

    level         : "metro" or "agency"
    rows          : DataFrame to aggregate (defaults to system_rows)
    through_month : last month to include in each year (defaults to max_month)
    annual        : False -> running YTD total for every month (e.g. "3/2026" = Jan–Mar 2026)
                    True  -> one column per year with the YTD total through `through_month`
    """
    if level not in GROUP_KEYS:
        raise ValueError(f"level must be one of {list(GROUP_KEYS)}, got {level!r}")

    rows = system_rows if rows is None else rows
    through_month = int(max_month if through_month is None else through_month)

    # All "M/YYYY" columns up to through_month, in chronological order
    month_cols = sorted(
        (
            c
            for c in rows.columns
            if re.fullmatch(r"\d{1,2}/\d{4}", str(c))
            and int(c.split("/")[0]) <= through_month
        ),
        key=lambda c: (int(c.split("/")[1]), int(c.split("/")[0])),
    )

    monthly = rows.groupby(GROUP_KEYS[level])[month_cols].sum(min_count=1)

    # Running total that resets each January
    years = [c.split("/")[1] for c in month_cols]
    ytd = monthly.T.groupby(years).cumsum().T

    if annual:
        last_cols = [f"{through_month}/{y}" for y in dict.fromkeys(years)]
        ytd = ytd[[c for c in last_cols if c in ytd.columns]]
        ytd.columns = [c.split("/")[1] for c in ytd.columns]

    return ytd


# %%
def add_trend_statistics(df, current=None, baseline="2019", as_percent=False):
    """
    Add change and percent-change columns comparing two columns of df.

    df         : DataFrame, e.g. the output of ytd_totals()
    current    : column to compare (defaults to latest_year)
    baseline   : column to compare against (defaults to "2019")
    as_percent : False -> 0.25 means +25%
                 True  -> 25.0 means +25%
    """
    current = str(latest_year) if current is None else str(current)
    baseline = str(baseline)

    missing = [c for c in (current, baseline) if c not in df.columns]
    if missing:
        raise KeyError(f"Column(s) not found: {missing}")

    out = df.copy()
    change = out[current] - out[baseline]
    pct = change / out[baseline].where(out[baseline] != 0)  # 0 baseline -> NaN, not inf
    recovery_pct = out[current] / out[baseline].where(out[baseline] != 0)

    out[f"Change, {current} vs {baseline}"] = change
    out[f"Pct. change, {current} vs {baseline}"] = pct * 100 if as_percent else pct
    out[f"Recovery, {current} vs {baseline}"] = (
        recovery_pct * 100 if as_percent else recovery_pct
    )

    out = out.sort_values(by=f"Pct. change, {current} vs {baseline}", ascending=False)

    out = out[
        [
            baseline,
            current,
            f"Change, {current} vs {baseline}",
            f"Pct. change, {current} vs {baseline}",
            f"Recovery, {current} vs {baseline}",
        ]
    ]

    return out


# %% [markdown]
# ## What are the yearly YTD totals for each metro across all agencies and transit modes?

# %%
metro_ytd_totals = ytd_totals("metro", annual=True).sort_values(
    by="2026", ascending=False
)

metro_ytd_totals.head(5)

# %% [markdown]
# ## What are the yearly YTD totals for each agency across transit modes?

# %%
agency_ytd_totals = ytd_totals("agency", annual=True).sort_values(
    by="2026", ascending=False
)

agency_ytd_totals.head(5)

# %% [markdown]
# ## At what level are agencies operating compared to 2019 on a monthly basis?

# %%
agency_ytd_totals = add_trend_statistics(agency_ytd_totals)
agency_ytd_totals.head(10)

# %% [markdown]
# ## At what level are metros operating at compared to 2019?
# This uses a 6-month rolling average for each month and compares to the 12-month 2019 average

# %%
metro_ytd_totals = add_trend_statistics(metro_ytd_totals)
metro_ytd_totals.head(10)

# %%
