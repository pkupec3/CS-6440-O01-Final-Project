import sys
from pathlib import Path

# Setup folder paths
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

sys.path.insert(0, str(SCRIPT_DIR))
from process_sdoh import process_cdc_svi_data
from process_fhir import process_fhir_data, find_fhir_dir
from merge_data import build_master_dataset


def run():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fhir_dir = find_fhir_dir(str(RAW_DIR))
    fhir_csv = PROCESSED_DIR / "fhir_burden_cleaned.csv"

    print("\nStep 1: CDC SVI")
    process_cdc_svi_data(str(RAW_DIR), str(PROCESSED_DIR))

    print("Step 2: Synthea FHIR")
    if fhir_csv.exists() and fhir_dir is None:
        print("  fhir_burden_cleaned.csv already exists — skipping.")
    elif fhir_dir is None:
        print("  No FHIR JSON files found and no pre-built CSV. Skipping.")
    else:
        process_fhir_data(fhir_dir, str(PROCESSED_DIR))

    print("Step 3: Merging")
    build_master_dataset(str(RAW_DIR), str(PROCESSED_DIR))

    print("\nDone. Outputs in data/processed/ and data.csv")


if __name__ == "__main__":
    run()
