import pandas as pd
import os

def build_master_dataset(raw_dir, processed_dir):
    sdoh_path      = os.path.join(processed_dir, "sdoh_cleaned.csv")
    fhir_path      = os.path.join(processed_dir, "fhir_burden_cleaned.csv")
    crosswalk_path = os.path.join(raw_dir,        "HUD_ZIP_COUNTY.csv")

    if not os.path.exists(crosswalk_path):
        print("Make sure HUD_ZIP_COUNTY.csv is in the raw folder.")
        return

    sdoh_df = pd.read_csv(sdoh_path)
    fhir_df = pd.read_csv(fhir_path)
    cw_df   = pd.read_csv(crosswalk_path)

    # Ensure consistent types
    sdoh_df['Year']     = sdoh_df['Year'].astype(str)
    sdoh_df['FIPS Code'] = sdoh_df['FIPS Code'].astype(str).str.zfill(5)
    fhir_df['ZipCode']  = fhir_df['ZipCode'].astype(str).str.zfill(5)

    # Synthea gives exact years; CDC only has even years — bucket to nearest SVI year
    def map_year_to_svi(year):
        try:
            y = int(year)
            if y <= 2015: return '2014'
            elif y <= 2017: return '2016'
            elif y <= 2019: return '2018'
            elif y <= 2021: return '2020'
            else: return '2022'
        except:
            return 'Unknown'

    fhir_df['SVI_Year'] = fhir_df['Year'].apply(map_year_to_svi)

    # HUD ZIP → County crosswalk
    cw_df['ZIP']    = cw_df['ZIP'].astype(str).str.zfill(5)
    cw_df['COUNTY'] = cw_df['COUNTY'].astype(str).str.zfill(5)

    # Keep only the majority county per ZIP (highest residential ratio)
    if 'RES_RATIO' in cw_df.columns:
        cw_df = cw_df.sort_values(by=['ZIP', 'RES_RATIO'], ascending=[True, False])
    cw_df = cw_df.drop_duplicates(subset=['ZIP'])

    real_crosswalk = dict(zip(cw_df['ZIP'], cw_df['COUNTY']))

    # Apply the dictionary to map our hospital ZIPs to Counties, drop any that didn't match
    fhir_df['FIPS Code'] = fhir_df['ZipCode'].map(real_crosswalk)
    fhir_df = fhir_df.dropna(subset=['FIPS Code'])

    # Pivot ER reasons from rows into columns
    fhir_pivoted = fhir_df.pivot_table(
        index=['FIPS Code', 'SVI_Year'],
        columns='ER_Reason_Text',
        values='Total_ER_Visits',
        aggfunc='sum',
        fill_value=0,
    ).reset_index()

    # Rename the new columns so it's clear they are ER visit counts
    new_cols = {
        col: f"ER Visits: {col}"
        for col in fhir_pivoted.columns
        if col not in ('FIPS Code', 'SVI_Year')
    }
    fhir_pivoted = fhir_pivoted.rename(columns=new_cols)

    # Calculate a grand total column for all ER visits in that county
    fhir_pivoted['Total ER Visits'] = fhir_pivoted[list(new_cols.values())].sum(axis=1)
    
    # Finally, merge the CDC vulnerability data with our hospital data
    final_dashboard_df = pd.merge(
        sdoh_df,
        fhir_pivoted,
        left_on=['FIPS Code', 'Year'],
        right_on=['FIPS Code', 'SVI_Year'],
        how='inner',
    ).drop(columns=['SVI_Year'])

    final_dashboard_df.to_csv(os.path.join(processed_dir, "final_dashboard_data.csv"), index=False)

    # Sync a copy to the project root for the frontend
    root_dir = os.path.normpath(os.path.join(processed_dir, '..', '..'))
    final_dashboard_df.to_csv(os.path.join(root_dir, "data.csv"), index=False)


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base = os.path.normpath(os.path.join(script_dir, '..'))
    build_master_dataset(
        os.path.join(base, "data", "raw"),
        os.path.join(base, "data", "processed"),
    )
