// Path to your processed data relative to site/index.html
const CSV_PATH = '../data/processed/final_dashboard_data.csv';

document.addEventListener('DOMContentLoaded', function() {
    loadCSVData();
});

function loadCSVData() {
    Papa.parse(CSV_PATH, {
        download: true,
        header: true,
        dynamicTyping: true,
        complete: function(results) {
            console.log("CSV Loaded Successfully:", results.data);
            initializeTable(results.data);
        },
        error: function(err) {
            console.error("Error loading CSV:", err);
        }
    });
}

function initializeTable(data) {
    const table = new Tabulator("#data-table", {
        data: data, // Load the parsed CSV rows
        layout: "fitColumns",
        pagination: "local",
        paginationSize: 15,
        movableColumns: true,
        responsiveLayout: "collapse",
        
        // Define columns based on your sdoh_cleaned.csv and fhir_burden headers
        columns: [
            {title: "Year", field: "Year", sorter: "number", width: 80},
            {title: "County", field: "Location", headerFilter: "input"},
            {title: "Poverty Rate", field: "Poverty", formatter: "progress", color: "red"},
            {title: "ER Visits", field: "Total_ER_Visits", sorter: "number"},
            {title: "Top Reason", field: "ER_Reason_Code", tooltip: true},
        ],
    });

    // Simple search filter implementation
    document.getElementById("table-search").addEventListener("keyup", function(e) {
        table.setFilter("Location", "like", e.target.value);
    });
}