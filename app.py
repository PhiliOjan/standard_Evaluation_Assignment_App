import streamlit as st
import pandas as pd
import numpy as np

# App title
st.set_page_config(page_title="SE", layout="wide")
st.title("SE Sampling & Assignment App")

# File upload
workplan_file = st.file_uploader("Upload Workplan (CSV/Excel)", type=["csv", "xlsx"])
data_file = st.file_uploader("Upload Respondent Data (CSV/Excel)", type=["csv", "xlsx"])

if workplan_file and data_file:
    # Load files
    if workplan_file.name.endswith(".csv"):
        workplan = pd.read_csv(workplan_file)
    else:
        workplan = pd.read_excel(workplan_file)

    if data_file.name.endswith(".csv"):
        df = pd.read_csv(data_file)
    else:
        df = pd.read_excel(data_file)

    st.subheader("Uploaded Data Preview")
    st.write("**Workplan**")
    st.dataframe(workplan.head())
    st.write("**Respondent Data**")
    st.dataframe(df.head())

    # --- Check for mismatches between workplan and dataset ---
    workplan_villages = set(workplan["village"].unique())
    data_villages = set(df["village"].unique())

    missing_in_data = workplan_villages - data_villages
    missing_in_workplan = data_villages - workplan_villages

    mismatch_summary = pd.DataFrame({
        "Mismatch_Type": ["In Workplan, Not in Data", "In Data, Not in Workplan"],
        "Villages": [", ".join(missing_in_data) if missing_in_data else "None",
                     ", ".join(missing_in_workplan) if missing_in_workplan else "None"]
    })

    st.subheader("Village Mismatch Summary")
    st.dataframe(mismatch_summary)

    # --- Sampling Function ---
    def assign_samples(village_df):
        np.random.seed(42)
        village_df = village_df.sample(frac=1).reset_index(drop=True)  # shuffle

        men = village_df[village_df["category"] == "Men"]
        women = village_df[village_df["category"] == "Women"]
        youth = village_df[village_df["category"] == "Youth"]

        target = pd.DataFrame()

        # Try to allocate exact quota
        men_target = men.head(9)
        women_target = women.head(3)
        youth_target = youth.head(3)

        target = pd.concat([men_target, women_target, youth_target])

        # If not enough respondents, prioritize Men -> Women -> Youth
        if len(target) < 15:
            remaining_needed = 15 - len(target)
            remaining_pool = village_df.drop(target.index)

            extra = remaining_pool.head(remaining_needed)
            target = pd.concat([target, extra])

        # Mark status
        village_df["status"] = "Excess"
        village_df.loc[target.index, "status"] = "Target"

        # Select 15 Reserve if possible
        remaining_pool = village_df[village_df["status"] == "Excess"]
        reserve = remaining_pool.head(15 - len(target))
        village_df.loc[reserve.index, "status"] = "Reserve"

        return village_df

    # Apply to each village
    assigned_df = df.groupby("village", group_keys=False).apply(assign_samples)

    # --- Downloads ---
    st.subheader("Download Outputs")
    st.download_button(
        "Download Randomised Data (All Respondents)",
        df.to_csv(index=False).encode("utf-8"),
        "randomised_data.csv",
        "text/csv"
    )

    st.download_button(
        "Download Assigned Data (With Target/Reserve/Excess)",
        assigned_df.to_csv(index=False).encode("utf-8"),
        "assigned_data.csv",
        "text/csv"
    )

    # --- Show Assigned Sample ---
    st.subheader("Assigned Data Preview")
    st.dataframe(assigned_df.head(50))


