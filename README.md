# Public Health Dashboard: SDOH & Healthcare Burden

**Course:** CS 6440: Intro to Health Informatics  
**Team:** Peter Kupec, Yiming Chen, Tim Pham, Oluwafisayo Oduyemi, Fernando Diaz

## About This Project
This project is a serverless web dashboard designed to help public health officials visualize the relationship between Social Determinants of Health (SDOH) and healthcare utilization across the United States.

To meet modern healthcare interoperability standards without requiring a live backend server, our data pipeline merges public U.S. Census/CDC data with synthetic patient records formatted in the FHIR (Fast Healthcare Interoperability Resources) standard.

## Repository Structure
To keep our deployment lightweight, raw data is processed offline using Python, and only the finalized, flattened CSVs are pushed to the live website.

* `/data/raw/` - Ignored by Git. Place downloaded FHIR and CDC files here.
* `/data/processed/` - Tracked by Git. Contains the final processed CSVs.
* `/scripts/` - Contains `generate_synthea.py`, `process_sdoh.py`, `process_fhir.py`, `merge_data.py`, and `run_pipeline.py`.
* `index.html` / `main.js` / `styles.css` - Frontend dashboard files at the project root.

-----------------------------------------------------------------------------------------------------------------------------------------------

## Local Setup & Data Instructions

Because our raw datasets are too large for GitHub, you must download them locally to run the Python data pipeline.

### Step 1: Clone the Repo
Clone this repository to your local machine and ensure you have Python and Pandas installed.
`pip install pandas`

### Step 2: Download the CDC SVI Data
1. Go to the [CDC ATSDR Social Vulnerability Index page](https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html).
2. Download the CSV files for the entire United States at the County level for the years 2014, 2016, 2018, 2020, and 2022.
3. Move these CSV files into your local `data/raw/SVI_DATA/` folder.

### Step 3: Generate the Synthetic FHIR Data
Instead of downloading the standard 1K sample (which is heavily biased toward Massachusetts), we generate our own 20,000 patient dataset accurately distributed across all 50 states.

**Prerequisites:**
1. **Java:** You must have **Java 17 or higher** installed.
2. **Synthea Engine:** Ensure `synthea-with-dependencies.jar` and `synthea.properties` are located inside your local `/scripts/` folder.

**Run the Generation:**
Once Java is installed and your CDC SVI data is in place, run from the project root:
```
python scripts/generate_synthea.py
```

### Step 4: Download the HUD-USPS ZIP Crosswalk File
1. Go to the [HUD USPS Crosswalk Downloads Page](https://www.huduser.gov/apps/public/uspscrosswalk/home).
2. Create an account and download the latest ZIP-County crosswalk (4th Quarter).
3. Place the CSV file into your local `data/raw/` folder as `HUD_ZIP_COUNTY.csv`.

-----------------------------------------------------------------------------------------------------------------------------------------------

## Data Processing Logic - SVI (`process_sdoh.py`)

To maintain a fast, serverless architecture for GitHub Pages, all data merging is handled offline via our Python ETL (Extract, Transform, Load) pipeline.

### Core Libraries
* **`pandas`**: Used for high-performance data manipulation, filtering, and standardizing the changing CDC column names across different years.
* **`glob`**: Utilized for dynamic pattern matching (e.g., `SVI_*_US_county.csv`). This prevents hardcoding filenames and allows the pipeline to automatically ingest new years of data if they are added to the `/raw` folder.
* **`os`**: Ensures file pathing works across all team members' operating systems (Windows/Mac/Linux) without breaking.

### The Processing Flow
1. **Dynamic Ingestion:** `glob` scans the `/data/raw/SVI_DATA` directory for the downloaded CDC SVI files and extracts the year directly from the filename.
2. **Normalization:** The CDC alters its column headers periodically (e.g., `EP_POV` vs `EP_POV150`). The script standardizes these headers so they stack cleanly.
3. **Filtering:** We drop over 100 unused data points, keeping only the essential SDOH metrics (Poverty, Unemployment, Education) to keep the final payload lightweight.
4. **FIPS Standardization:** County FIPS codes are forced into a strict 5-digit string format (padding with leading zeros where necessary) to guarantee a 1:1 match with the frontend Plotly choropleth map.
5. **Output:** The script stacks the data into a single, flattened `sdoh_cleaned.csv` ready for frontend consumption.

-----------------------------------------------------------------------------------------------------------------------------------------------

## Healthcare Pipeline - FHIR (`process_fhir.py`)

The standard FHIR format represents a massive, highly nested JSON structure for every individual patient. This script flattens individual synthetic patient histories into a single, lightweight geographic metric for use when real or manually placed FHIR data is available.

### Core Libraries
* **`json`**: Utilized to parse the complex, deeply nested dictionary structures inherent to FHIR Bundles.
* **`pandas`**: Used to aggregate the extracted patient data into regional cohorts using `.groupby()`.
* **`glob`**: Enables dynamic batch processing of all JSON files in the Synthea output directory, preventing hardcoded file paths.
* **`os`**: Ensures file pathing works across all team members' operating systems (Windows/Mac/Linux) without breaking.

### The Processing Flow
1. **Batch Ingestion:** `glob` scans the `data/raw/` directory for patient JSON files and queues every one for processing. Safety checks are included to skip corrupted files (`json.JSONDecodeError`).
2. **Double-Pass Extraction:** Because the order of resources within a FHIR Bundle array is not strictly guaranteed, the script makes two passes:
   * Pass 1 (Demographics): Locates the `Patient` resource to extract the geographic anchor (City, State, ZipCode).
   * Pass 2 (Encounters & Time): Locates `Encounter` resources, strictly filtering for hospital visits classified as Emergency (`class code: 'EMER'`). It dives into the `period.start` object to extract the exact **Year** the ER visit occurred.
3. **Clinical Coding Extraction & Fallbacks:** For every ER visit, the script extracts the SNOMED-CT code and its human-readable `display` text from the `reasonCode` block. If the text is missing, it defaults to `"Unknown Reason"` while retaining the SNOMED code in a separate `ER_Reason_Code` column.
4. **Spatio-Temporal Aggregation:** Instead of outputting a row for every patient, `pandas` aggregates the data by **Year**, **Location**, and **ER Reason**, counting occurrences into a `Total_ER_Visits` metric.
5. **Output:** The script sorts by Year and highest-burden areas, exporting the flattened data as `fhir_burden_cleaned.csv`.

### Architectural Decision: Geographic Aggregation
Instead of plotting individual patient records, our pipeline intentionally aggregates ER visits by Zip Code. This design choice was made to solve three specific engineering challenges:

1. **Data Alignment:** The CDC SVI dataset is measured at the County level. By aggregating patient-level FHIR data into regional cohorts, we align the "grain" of both datasets for a clean 1-to-1 merge.
2. **Frontend Optimization:** Because this is a serverless application hosted on GitHub Pages, the user's browser must render the Plotly charts. Condensing raw JSON files into a single lightweight CSV prevents browser crashes and guarantees fast load times.
3. **Privacy & Compliance:** By aggregating individual medical events into regional summaries, we de-identify the synthetic patients, mirroring the reporting standards used by the CDC and WHO.

-----------------------------------------------------------------------------------------------------------------------------------------------

## The Master Merge (`merge_data.py`)

This is the final script in our backend pipeline. It takes our two completely different datasets (CDC SVI and Synthea FHIR) and joins them into a single, clean CSV file that our Plotly dashboard can read instantly.

### How It Works (Step-by-Step)
1. **The Time Translator:** Synthea patients visit the ER every year (e.g., 2017, 2019), but the CDC only releases data every two years (2014, 2016, 2018...). The script safely "buckets" hospital visits into the closest CDC reporting year so no records are lost during the merge.
2. **The Geographic Translator (HUD Crosswalk):** Synthea data uses Zip Codes, but CDC data uses County FIPS codes. We use the official **HUD ZIP-to-County Crosswalk** to translate every synthetic patient's zip code into its correct 5-digit County code.
3. **The Pivot (Squishing the Data):** The script takes the tall list of different ER visits (Asthma, COVID, Overdose) and pivots them sideways into individual columns.
4. **The Inner Merge:** Now that both datasets share the same key (County FIPS Code + Year), we do a clean `pd.merge()` to fuse them together.

### Architectural Decisions & Edge Cases

#### 1. Handling Overlapping County Borders (`RES_RATIO`)
**The Problem:** Zip codes are drawn by the Post Office, not the government. A single zip code will often bleed across two county lines, which could duplicate patients into the wrong county.
**Our Solution:** We use the `RES_RATIO` (Residential Ratio) column from the HUD crosswalk. Our script sorts by this ratio and drops duplicates, strictly assigning ER visits to whichever county contains the majority of residential addresses for that zip code.

#### 2. Flipping the Data (Long vs. Wide Format)
**The Problem:** Our FHIR data was in a "Long" format (multiple rows for the same county, one per disease). Merging this directly with the CDC data would duplicate the county's poverty statistics, corrupting any averages.
**Our Solution:** We use `pandas.pivot_table()` to convert to "Wide" format — exactly one row per County per Year. This is also crucial for the frontend: Plotly can read each ER reason as a direct column rather than filtering rows at runtime.

#### 3. Rolling Up vs. Splitting Down
**The Problem:** We had to decide whether to map the CDC data down to Zip Codes, or map the patient data up to Counties.
**Our Solution:** In data science, you cannot reliably split statistical data downwards. If a county has a 15% poverty rate, you cannot accurately distribute that across its zip codes (wealth may be concentrated in one neighborhood). Our architecture strictly "rolls up" the individual patient ER visits into the larger County buckets.

-----------------------------------------------------------------------------------------------------------------------------------------------

## Pipeline Orchestrator (`run_pipeline.py`)

`run_pipeline.py` is the single entry point for running the full data pipeline against real or pre-downloaded FHIR data. It calls `process_sdoh.py`, `process_fhir.py`, and `merge_data.py` in sequence, and automatically detects whether `generate_synthea.py` has already produced `fhir_burden_cleaned.csv` to avoid crashing on missing JSON files.

### The Processing Flow
1. **Step 1 — CDC SVI:** Calls `process_sdoh.py` to normalize and stack the CDC SVI files into `sdoh_cleaned.csv`.
2. **Step 2 — FHIR Processing:** Calls `process_fhir.py` to extract ER visit records from raw FHIR JSON bundles and write `fhir_burden_cleaned.csv`.
   * If `fhir_burden_cleaned.csv` already exists and no JSON files are present (i.e., `generate_synthea.py` already ran and deleted them), this step is skipped automatically.
3. **Step 3 — Merge:** Calls `merge_data.py` to join the SDOH and FHIR datasets via the HUD ZIP crosswalk and write the final `data.csv` for the dashboard.

> **Note:** If you generated data with `generate_synthea.py`, you do not need to run `run_pipeline.py` for Step 2 — it will skip it. You can still run `run_pipeline.py` to complete Steps 1 and 3, or run `process_sdoh.py` and `merge_data.py` directly.

-----------------------------------------------------------------------------------------------------------------------------------------------

## Synthetic Patient Generation (`generate_synthea.py`)

By default, the Synthea engine generates a small sample of patients heavily biased toward Massachusetts. This script automates the generation of 20,000 patients spread accurately across all 50 U.S. states, extracts ER visit data inline, and writes the result directly to `fhir_burden_cleaned.csv` — without leaving raw FHIR files on disk.

### Core Libraries
* **`pandas`**: Reads the CDC SVI dataset to calculate population proportions per state and aggregates the extracted ER records into the final CSV.
* **`subprocess`**: Launches the Synthea JVM for each state and checks its exit code to catch failures early.
* **`glob` / `os`**: Scans the Synthea output directory for generated JSON files and removes them after extraction.
* **`pathlib`**: Anchors all file paths to the project root so the script runs correctly from any working directory.

### The Processing Flow
1. **Read the Demographics:** Loads `SVI_2020_US_county.csv` and groups by state to get real-world population totals.
2. **Calculate Proportions:** Each state receives a patient count proportional to its share of the U.S. population, summing to `TARGET_PATIENTS`.
3. **State-by-State Generation:** Loops through all 50 states, invoking Synthea once per state with a unique reproducible seed.
4. **Inline Extraction:** After each state completes, `_extract_er_visits` reads every generated FHIR bundle — extracting patient demographics and Emergency (`EMER`) encounter records.
5. **Immediate Cleanup:** Raw JSON files are deleted after extraction to prevent accumulating hundreds of gigabytes across 50 runs.
6. **Aggregation & Output:** All records are grouped by Year, State, City, ZipCode, and ER Reason and written to `data/processed/fhir_burden_cleaned.csv` — the same schema produced by `process_fhir.py`.

### Architectural Decisions & Edge Cases

#### 1. Inline Extraction Over Batch Processing
* **The Problem:** Storing FHIR JSON for all 50 states simultaneously would require hundreds of gigabytes of disk space.
* **Our Solution:** We extract and delete per state. Each state's files are processed and removed before the next state begins, keeping disk usage bounded to one state's worth of files at a time.

#### 2. Dynamic Population Weighting
* **The Problem:** Hardcoding patient counts per state is brittle and doesn't reflect real demographics.
* **Our Solution:** Patient counts are derived directly from the CDC SVI population data, so the distribution adjusts automatically if the dataset changes.

#### 3. 100% Reproducibility
* **The Problem:** Synthea relies on random number generation, so two runs could produce different patients.
* **Our Solution:** Each state gets a unique seed derived from `GLOBAL_SEED + state_index`, guaranteeing that anyone who runs the script will generate the exact same synthetic patients and ER visits.

-----------------------------------------------------------------------------------------------------------------------------------------------

## Synthea Configuration (`synthea.properties`)

To ensure our synthetic patients are compatible with our dashboard, we use a custom properties file to override Synthea's default settings. This ensures the output is standardized, lightweight, and formatted for modern healthcare interoperability.

### Key Configuration Settings
* **`exporter.fhir.export = true`**: Enables the generation of JSON-based FHIR records.
* **`exporter.fhir.version = R4`**: Sets the FHIR version to R4.
* **`exporter.csv.export = false`**: Disables other formats like CSV to save disk space and speed up generation.
* **`generate.years_of_history = 10`**: Limits patient records to the last 10 years.
* **`exporter.baseDirectory`**: Tells Synthea exactly where to save the files so our Python scripts can find them.

### Architectural Decisions & Edge Cases

#### 1. Disabling Hospital and Practitioner Exports
* **The Problem:** By default, Synthea creates extra files for hospitals and practitioners. For 20,000 patients, this generates a large number of extra files that slow down our Python processing scripts.
* **Our Solution:** Since our dashboard only needs patient-level ER data, we disabled these extra files. This reduces total dataset size without losing any relevant information.

#### 2. Time-Windowing
* **The Problem:** Synthetic patients can have extensive medical history, leading to large JSON files that are slow to parse.
* **Our Solution:** We set `years_of_history` to 10. This ensures patient data aligns with our CDC SVI study years (2014–2022) while keeping file sizes manageable.

-----------------------------------------------------------------------------------------------------------------------------------------------
