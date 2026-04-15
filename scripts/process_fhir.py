import pandas as pd
import json
import os
import glob
from pathlib import Path


def process_fhir_data(raw_data_dir, output_dir):
    # Grab all the raw patient JSONs
    fhir_files = glob.glob(os.path.join(raw_data_dir, "*.json"))
    if not fhir_files:
        print(f"No FHIR JSON files found in {raw_data_dir}.")
        return

    er_visit_records = []

    for file_path in fhir_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                bundle = json.load(f)
            except json.JSONDecodeError:
                continue

        # Temporary patient demographics
        patient_id = None
        city = "Unknown"
        state = "Unknown"
        zipcode = "Unknown"

        # First pass: find the Patient's demographics
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Patient':
                patient_id = resource.get('id')
                addresses = resource.get('address', [])
                if addresses:
                    city    = addresses[0].get('city',       'Unknown')
                    state   = addresses[0].get('state',      'Unknown')
                    zipcode = addresses[0].get('postalCode', 'Unknown')
                break

        # Second pass: find all ER visits, their reason and year
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') != 'Encounter':
                continue
            if resource.get('class', {}).get('code') != 'EMER':
                continue

            start_date = resource.get('period', {}).get('start', '')
            visit_year = start_date[:4] if len(start_date) >= 4 else 'Unknown'

            first_reason = next(iter(resource.get('reasonCode', [])), {})
            coding       = next(iter(first_reason.get('coding',   [])), {})

            if patient_id:
                er_visit_records.append({
                    'Patient_ID':     patient_id,
                    'Year':           visit_year,
                    'City':           city,
                    'State':          state,
                    'ZipCode':        zipcode,
                    'ER_Reason_Code': coding.get('code',    'No Code'),
                    'ER_Reason_Text': coding.get('display', 'Unknown Reason'),
                })

    df = pd.DataFrame(er_visit_records)
    if df.empty:
        print("No ER visits found in this patient cohort.")
        return
    
    # Count up the total ER visits grouped by location, year, and specific reason
    regional_burden = (
        df.groupby(['Year', 'State', 'City', 'ZipCode', 'ER_Reason_Code', 'ER_Reason_Text'])
          .agg(Total_ER_Visits=('Patient_ID', 'count'))
          .reset_index()
          .sort_values(by=['Year', 'ZipCode', 'Total_ER_Visits'], ascending=[False, True, False])
    )
    # Save the summary
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "fhir_burden_cleaned.csv")
    regional_burden.to_csv(output_path, index=False)


def find_fhir_dir(raw_data_dir):
    """Return the first folder under raw_data_dir that contains JSON files."""
    for path in Path(raw_data_dir).rglob("*.json"):
        return str(path.parent)
    return None


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    raw       = base / "data" / "raw"
    processed = base / "data" / "processed"

    fhir_dir = find_fhir_dir(raw)
    process_fhir_data(fhir_dir, processed)
