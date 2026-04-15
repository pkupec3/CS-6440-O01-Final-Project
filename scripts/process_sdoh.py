import pandas as pd
import os
import glob
from pathlib import Path

# Normalized state names .
_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'District of Columbia', 'Florida', 'Georgia',
    'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky',
    'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire',
    'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota',
    'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina',
    'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia',
    'Washington', 'West Virginia', 'Wisconsin', 'Wyoming',
}
# key: spaceless lowercase → canonical name
# Handles every CDC variant: ALL CAPS, Title Case, space-stripped 
_STATE_LOOKUP = {s.replace(' ', '').lower(): s for s in _STATES}


def process_cdc_svi_data(raw_data_dir, output_dir):
    
    svi_files = glob.glob(os.path.join(raw_data_dir, "SVI_DATA", "SVI_*_US_county.csv"))
    if not svi_files:
        raise FileNotFoundError("No CDC SVI files found in data/raw/SVI_DATA/")

    all_years_data = []
    # Extract the year directly from the filename
    for file_path in svi_files:
        year = os.path.basename(file_path).split('_')[1]

        df = pd.read_csv(file_path)

        # Normalize column names that changed across years
        if 'EP_POV150' in df.columns:
            df = df.rename(columns={'EP_POV150': 'EP_POV'})
        if 'STCNTY' in df.columns and 'FIPS' not in df.columns:
            df = df.rename(columns={'STCNTY': 'FIPS'})

        keep_columns = ['FIPS', 'STATE', 'COUNTY', 'EP_POV', 'EP_UNEMP', 'EP_NOHSDP']
        df = df[[c for c in keep_columns if c in df.columns]].copy()

        # Rename them for the final dataset
        df = df.rename(columns={
            'FIPS':      'FIPS Code',
            'STATE':     'State',
            'COUNTY':    'County',
            'EP_POV':    'Poverty Percentage',
            'EP_UNEMP':  'Unemployment Percentage',
            'EP_NOHSDP': 'No High School Diploma Percentage',
        })

        # Apply the lookup dictionary to clean up state names
        if 'State' in df.columns:
            key = df['State'].str.strip().str.replace(' ', '', regex=False).str.lower()
            df['State'] = key.map(_STATE_LOOKUP).fillna(df['State'].str.strip().str.title())

        df['Year'] = year
        all_years_data.append(df)
    # Stick all the years together into one giant dataframe
    final_sdoh_df = pd.concat(all_years_data, ignore_index=True)

    # Ensure FIPS codes are zero-padded 5-digit strings
    if 'FIPS Code' in final_sdoh_df.columns:
        final_sdoh_df['FIPS Code'] = (
            final_sdoh_df['FIPS Code']
            .astype(str)
            .str.replace('.0', '', regex=False)
            .str.zfill(5)
        )

    # Save the output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "sdoh_cleaned.csv")
    final_sdoh_df.to_csv(output_path, index=False)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    process_cdc_svi_data(base / "data" / "raw", base / "data" / "processed")
