import glob
import json
import os
import sys
import subprocess
from pathlib import Path
import pandas as pd

# Setting up the main folder paths
ROOT = Path(__file__).resolve().parent.parent
TARGET_PATIENTS = 50000
GLOBAL_SEED = 123
SYNTHEA_OUTPUT_DIR = ROOT / "data" / "raw" / "synthea_generated"


def _extract_er_visits(output_dir):
    """Read every FHIR JSON file in output_dir and return a list of ER visit rows."""
    records = []
    # Loop through every single JSON file Synthea just made
    for fpath in glob.glob(os.path.join(output_dir, "**", "*.json"), recursive=True):
        try:
            with open(fpath, encoding='utf-8') as f:
                bundle = json.load(f)
        except json.JSONDecodeError:
            continue

        # Pass 1: grab the patient's location from the Patient resource
        patient_id, city, state_val, zipcode = None, "Unknown", "Unknown", "Unknown"
        for entry in bundle.get('entry', []):
            r = entry.get('resource', {})
            if r.get('resourceType') == 'Patient':
                patient_id = r.get('id')
                addr = r.get('address', [{}])[0]
                city      = addr.get('city',        'Unknown')
                state_val = addr.get('state',       'Unknown')
                zipcode   = addr.get('postalCode',  'Unknown')
                break

        # Pass 2: find only Emergency (EMER) encounters and record why the patient came in
        for entry in bundle.get('entry', []):
            r = entry.get('resource', {})
            if r.get('resourceType') != 'Encounter':
                continue
            if r.get('class', {}).get('code') != 'EMER':
                continue
            # Grab the year of the visit and why they came to the ER
            start = r.get('period', {}).get('start', '')
            first_reason = next(iter(r.get('reasonCode', [])), {})
            coding = next(iter(first_reason.get('coding', [])), {})
            if patient_id:
                records.append({
                    'Patient_ID':     patient_id,
                    'Year':           start[:4] if len(start) >= 4 else 'Unknown',
                    'City':           city,
                    'State':          state_val,
                    'ZipCode':        zipcode,
                    'ER_Reason_Code': coding.get('code',    'No Code'),
                    'ER_Reason_Text': coding.get('display', 'Unknown Reason'),
                })
    return records


def run():
    # Use CDC SVI county populations to figure out how many patients each state should get
    svi_df = pd.read_csv(ROOT / "data" / "raw" / "SVI_DATA" / "SVI_2020_US_county.csv", usecols=["STATE", "E_TOTPOP"])
    state_pops = svi_df.groupby("STATE")["E_TOTPOP"].sum()
    state_pops.index = state_pops.index.str.title()
    state_pops = state_pops.drop("District Of Columbia", errors="ignore")

    total_pop = state_pops.sum()
    patients_per_state = {
        state: round((pop / total_pop) * TARGET_PATIENTS)
        for state, pop in state_pops.items()
    }

    os.makedirs(SYNTHEA_OUTPUT_DIR, exist_ok=True)

    all_records = []

    for i, (state, num_patients) in enumerate(patients_per_state.items(), 1):
        # Give each state a unique seed so results are reproducible but varied per state
        state_seed = GLOBAL_SEED + i

        print(f"[{i}/{len(patients_per_state)}] {state}: generating {num_patients} patients...")
# Run the Synthea  tool from CL
        result = subprocess.run([
            "java", "-Xmx12G",
            "-jar", str(ROOT / "scripts" / "synthea-with-dependencies.jar"),
            "-c", str(ROOT / "scripts" / "synthea.properties"),
            "-p", str(num_patients),
            "-s", str(state_seed),
            str(state)
        ])

        if result.returncode != 0:
            sys.exit(1)

        # Pull out just the ER visit data we need, then delete the raw FHIR files
        # to avoid accumulating hundreds of GB across 50 states
        all_records.extend(_extract_er_visits(SYNTHEA_OUTPUT_DIR))
        for fpath in glob.glob(os.path.join(SYNTHEA_OUTPUT_DIR, "**", "*.json"), recursive=True):
            os.remove(fpath)

    if not all_records:
        return

    
    # Turn the list of dicts into a dataframe so pandas can do the heavy lifting
    df = pd.DataFrame(all_records)
    # Group everything together to count the total ER visits per zip code, per year, per reason
    regional_burden = (
        df.groupby(['Year', 'State', 'City', 'ZipCode', 'ER_Reason_Code', 'ER_Reason_Text'])
          .agg(Total_ER_Visits=('Patient_ID', 'count'))
          .reset_index()
          .sort_values(by=['Year', 'ZipCode', 'Total_ER_Visits'], ascending=[False, True, False])
    )

    #Save
    os.makedirs(ROOT / "data" / "processed", exist_ok=True)
    regional_burden.to_csv(ROOT / "data" / "processed" / "fhir_burden_cleaned.csv", index=False)


if __name__ == "__main__":
    run()
