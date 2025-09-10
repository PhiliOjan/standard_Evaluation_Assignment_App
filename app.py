import pandas as pd
import streamlit as st

st.set_page_config(page_title="SE Contractor Assignment", layout="wide")
st.title("📊 SE Contractor Assignment App")

# ----------------- STEP 0: FILE UPLOAD -----------------
ahs_workplan_file = st.file_uploader("Upload Workplan", type=["xlsx", "csv"])
case_list_file = st.file_uploader("Upload Case List/Raw Dataset", type=["xlsx", "csv"])

if ahs_workplan_file and case_list_file:
    # ----------------- STEP 1: LOAD FILES -----------------
    if ahs_workplan_file.name.endswith("csv"):
        ahs_workplan_df = pd.read_csv(ahs_workplan_file)
    else:
        ahs_workplan_df = pd.read_excel(ahs_workplan_file)

    if case_list_file.name.endswith("csv"):
        case_list_df = pd.read_csv(case_list_file)
    else:
        case_list_df = pd.read_excel(case_list_file)

    # ----------------- STEP 2: CLEAN TEXT -----------------
    for col in ['district', 'cluster', 'village']:
        case_list_df[col] = case_list_df[col].astype(str).str.strip().str.title()

    for col in ['District', 'Cluster', 'Villages']:
        ahs_workplan_df[col] = ahs_workplan_df[col].astype(str).str.strip().str.title()

    # Create unique identifier
    case_list_df['villageidentifier'] = (
        case_list_df['district'] + "_" + case_list_df['cluster'] + "_" + case_list_df['village']
    )
    ahs_workplan_df['villageidentifier'] = (
        ahs_workplan_df['District'] + "_" + ahs_workplan_df['Cluster'] + "_" + ahs_workplan_df['Villages']
    )

    # Merge contractor info
    merged_df = case_list_df.merge(
        ahs_workplan_df[['villageidentifier', 'DAY', 'DATE', 'Contractors Code']],
        on='villageidentifier',
        how='left'
    )

    # Drop duplicate IDs if present
    if 'id' in merged_df.columns:
        merged_df.drop_duplicates(subset='id', keep='first', inplace=True)

    # ----------------- STEP 3: RANDOMIZE DATA -----------------
    randomized_df = merged_df.sample(frac=1, random_state=None).reset_index(drop=True)

    st.subheader("🔀 Randomized Respondents")
    st.dataframe(randomized_df)

    # ----------------- STEP 4: SAMPLING LOGIC -----------------
    final_samples = []

    for village, village_df in randomized_df.groupby('village'):
        men = village_df[village_df['headship'] == 'Men']
        youth = village_df[village_df['headship'] == 'Youth']
        women = village_df[village_df['headship'] == 'Women']

        target_pool, reserve_pool, excess_pool = [], [], []

        # --- Step A: Quotas: 9 Men, 3 Women, 3 Youth ---
        men_target = men.iloc[:min(9, len(men))]
        women_target = women.iloc[:min(3, len(women))]
        youth_target = youth.iloc[:min(3, len(youth))]

        target_pool.extend([men_target, women_target, youth_target])

        # --- Step B: Fill remaining slots up to 15, prioritizing Men > Women > Youth ---
        current_target_count = sum(len(x) for x in target_pool)
        needed = 15 - current_target_count

        if needed > 0:
            extra_men = men.drop(men_target.index)
            take = min(needed, len(extra_men))
            target_pool.append(extra_men.iloc[:take])
            needed -= take

        if needed > 0:
            extra_women = women.drop(women_target.index)
            take = min(needed, len(extra_women))
            target_pool.append(extra_women.iloc[:take])
            needed -= take

        if needed > 0:
            extra_youth = youth.drop(youth_target.index)
            take = min(needed, len(extra_youth))
            target_pool.append(extra_youth.iloc[:take])
            needed -= take

        # --- Step C: Build target group ---
        target = pd.concat(target_pool) if target_pool else pd.DataFrame()
        target['status'] = 'Target'

        # --- Step D: Reserve group (next available) ---
        reserve_candidates = pd.concat([
            men.drop(target.index, errors='ignore'),
            women.drop(target.index, errors='ignore'),
            youth.drop(target.index, errors='ignore')
        ])
        reserve = reserve_candidates.iloc[:15]
        reserve['status'] = 'Reserve'

        # --- Step E: Excess group ---
        excess = reserve_candidates.drop(reserve.index, errors='ignore')
        excess['status'] = 'Excess'

        village_samples = pd.concat([target, reserve, excess])
        final_samples.append(village_samples)

    sampled_df = pd.concat(final_samples, ignore_index=True)

    # ----------------- STEP 5: CONTRACTOR ASSIGNMENT -----------------
    def assign_contractor(group):
        codes = group['Contractors Code'].iloc[0]
        if pd.isna(codes) or not isinstance(codes, str):
            group['assigned_contractor'] = "Not Assigned"
            return group
        clean_codes = [c.strip() for c in codes.split(',') if c.strip()]
        contractor = clean_codes[hash(group['villageidentifier'].iloc[0]) % len(clean_codes)]
        group['assigned_contractor'] = contractor
        return group

    final_df = sampled_df.groupby(['villageidentifier', 'DAY'], group_keys=False).apply(assign_contractor)
    final_df = final_df.drop(columns=['villageidentifier'])

    # ----------------- STEP 6: DISPLAY -----------------
    st.success("✅ Processing Complete!")

    st.subheader("🎯 Target Respondents (per village)")
    target_preview = final_df[final_df['status'] == 'Target']
    st.dataframe(target_preview)

    st.subheader("📋 Final Assigned Cases")
    st.dataframe(final_df)

    # ----------------- STEP 7: MISMATCH CHECK -----------------
    st.subheader("⚠️ Workplan vs Case List Mismatches")

    # Normalize column names
    ahs_workplan_df.columns = ahs_workplan_df.columns.str.strip().str.lower()
    case_list_df.columns = case_list_df.columns.str.strip().str.lower()

    if "villageidentifier" in ahs_workplan_df.columns and "villageidentifier" in case_list_df.columns:
        workplan_villages = set(ahs_workplan_df["villageidentifier"].unique())
        case_villages = set(case_list_df["villageidentifier"].unique())

        missing_in_data = workplan_villages - case_villages
        missing_in_workplan = case_villages - workplan_villages

        mismatch_summary = pd.DataFrame({
            "Mismatch Type": [
                "In Workplan, Not in Case List",
                "In Case List, Not in Workplan"
            ],
            "Villages": [
                ", ".join(sorted(missing_in_data)) if missing_in_data else "None",
                ", ".join(sorted(missing_in_workplan)) if missing_in_workplan else "None"
            ]
        })

        st.dataframe(mismatch_summary, use_container_width=True)

    else:
        st.error("⚠️ Column 'villageidentifier' not found in one or both files. Please check your uploads.")

    # ----------------- STEP 8: DOWNLOADS -----------------
    st.download_button(
        "⬇️ Download Randomized Data (with Status)",
        data=sampled_df.to_csv(index=False),
        file_name="randomized_with_status.csv",
        mime="text/csv"
    )

    st.download_button(
        "⬇️ Download Target Respondents Only",
        data=target_preview.to_csv(index=False),
        file_name="target_respondents.csv",
        mime="text/csv"
    )

    st.download_button(
        "⬇️ Download Final Assigned Data",
        data=final_df.to_csv(index=False),
        file_name="assigned_data.csv",
        mime="text/csv"
    )
