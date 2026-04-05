// Global state
let allData = [];
let selectedCountyFIPS = null;
let selectedCountyName = null;

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', async () => {
    try {
        console.log('Loading dashboard data...');
        await loadData();
        populateFilters();
        updateDataInfo();
        renderCharts();
        setupEventListeners();
        console.log('Dashboard initialized successfully');
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showError(`Failed to load dashboard data: ${error.message}`);
    }
});

// Load CSV data
async function loadData() {
    // Try multiple paths for flexibility (local, GitHub Pages, etc.)
    const paths = [
        './data.csv',
        '../data/processed/final_dashboard_data.csv'
    ];
    
    let response;
    let lastError;
    
    for (const path of paths) {
        try {
            response = await fetch(path);
            if (response.ok) break;
        } catch (error) {
            lastError = error;
            continue;
        }
    }
    
    if (!response || !response.ok) {
        throw new Error('Failed to load data from any source: ' + (lastError?.message || response?.statusText));
    }
    
    const csvText = await response.text();
    allData = parseCSV(csvText);
    console.log(`Loaded ${allData.length} records`);
}

// Parse CSV with proper handling
function parseCSV(csvText) {
    const lines = csvText.trim().split('\n');
    const headers = lines[0].split(',');
    const data = [];

    for (let i = 1; i < lines.length; i++) {
        const obj = {};
        const values = lines[i].split(',');
        headers.forEach((header, index) => {
            const value = values[index] ? values[index].trim() : '';
            obj[header] = isNaN(value) ? value : parseFloat(value);
        });
        if (obj['FIPS Code']) {
            data.push(obj);
        }
    }
    return data;
}

// Populate dropdown filters
function populateFilters() {
    const states = [...new Set(allData.map(d => d.State))].sort();
    const years = [...new Set(allData.map(d => d.Year))].sort();

    const stateSelect = document.getElementById('stateSelect');
    states.forEach(state => {
        const option = document.createElement('option');
        option.value = state;
        option.textContent = state;
        stateSelect.appendChild(option);
    });

    const yearSelect = document.getElementById('yearSelect');
    years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
    });
}

// Setup filter event listeners
function setupEventListeners() {
    document.getElementById('stateSelect').addEventListener('change', renderCharts);
    document.getElementById('yearSelect').addEventListener('change', renderCharts);
    document.getElementById('metricSelect').addEventListener('change', renderCharts);
}

// Get filtered data based on user selections
function getFilteredData() {
    const stateFilter = document.getElementById('stateSelect').value;
    const yearFilter = document.getElementById('yearSelect').value;

    return allData.filter(d => {
        if (stateFilter && d.State !== stateFilter) return false;
        if (yearFilter && d.Year != yearFilter) return false;
        return true;
    });
}

// Render all charts
function renderCharts() {
    const filtered = getFilteredData();
    renderChoropleth(filtered);
    if (selectedCountyFIPS) {
        renderTimeSeries(filtered);
    } else {
        renderEmptyTimeSeries();
    }
    renderScatterPlot(filtered);
}

// Render choropleth map
function renderChoropleth(data) {
    const fipsValues = data.map(d => String(d['FIPS Code']).padStart(5, '0'));
    const erVisits = data.map(d => d['Total ER Visits'] || 0);
    const counties = data.map(d => d['County']);
    const states = data.map(d => d['State']);
    const hoverText = data.map((d, i) => 
        `<b>${d.County}, ${d.State}</b><br>` +
        `FIPS: ${fipsValues[i]}<br>` +
        `Total ER Visits: ${d['Total ER Visits']}<br>` +
        `Poverty: ${d['Poverty Percentage']}%<br>` +
        `Unemployment: ${d['Unemployment Percentage']}%<br>` +
        `Year: ${d.Year}`
    );

    const choroplethData = [{
        type: 'choropleth',
        locations: fipsValues,
        z: erVisits,
        text: hoverText,
        customdata: fipsValues,
        hoverinfo: 'text',
        colorscale: [
            [0, '#f7fbff'],
            [0.2, '#deebf7'],
            [0.4, '#9ecae1'],
            [0.6, '#3182bd'],
            [0.8, '#08519c'],
            [1, '#08306b']
        ],
        locationmode: 'geojson-id',
        colorbar: { 
            title: 'ER Visits',
            thickness: 15,
            len: 0.7
        },
        marker: { 
            line: { 
                width: 0.5,
                color: '#999'
            }
        }
    }];

    const layout = {
        title: {
            text: 'Total Emergency Room Visits by County',
            font: { size: 18 }
        },
        geo: {
            scope: 'usa',
            projection: { type: 'albers usa' },
            showland: true,
            landcolor: '#f3f3f3',
            coastcolor: '#999',
            countrycolor: '#999',
            countrywidth: 1,
            coastwidth: 1
        },
        margin: { l: 0, r: 0, t: 60, b: 0 },
        height: 500,
        paper_bgcolor: '#fff',
        plot_bgcolor: '#f9f9f9'
    };

    Plotly.newPlot('choroplethMap', choroplethData, layout, { responsive: true });
    
    // Add click handler for county selection
    const mapElement = document.getElementById('choroplethMap');
    mapElement.on('plotly_click', function(data) {
        if (data.points && data.points[0]) {
            const fipsCode = data.points[0].location;
            const countyData = allData.find(d => String(d['FIPS Code']).padStart(5, '0') === fipsCode);
            if (countyData) {
                selectedCountyFIPS = fipsCode;
                selectedCountyName = `${countyData.County}, ${countyData.State}`;
                console.log(`Selected: ${selectedCountyName}`);
                renderCharts();
            }
        }
    });
}

// Render time series for selected county
function renderTimeSeries(data) {
    if (!selectedCountyFIPS) {
        renderEmptyTimeSeries();
        return;
    }

    const countyData = data.filter(d => {
        const fipsCode = String(d['FIPS Code']).padStart(5, '0');
        return fipsCode === selectedCountyFIPS;
    }).sort((a, b) => a.Year - b.Year);

    if (countyData.length === 0) {
        console.warn(`No data found for FIPS: ${selectedCountyFIPS}`);
        renderEmptyTimeSeries();
        return;
    }

    const years = countyData.map(d => d.Year);
    const erVisits = countyData.map(d => d['Total ER Visits'] || 0);
    const poverty = countyData.map(d => d['Poverty Percentage'] || 0);
    const unemployment = countyData.map(d => d['Unemployment Percentage'] || 0);

    const trace1 = {
        x: years,
        y: erVisits,
        name: 'Total ER Visits',
        type: 'scatter',
        mode: 'lines+markers',
        yaxis: 'y',
        line: { color: '#2563eb', width: 3 },
        marker: { size: 8, symbol: 'circle' }
    };

    const trace2 = {
        x: years,
        y: poverty,
        name: 'Poverty %',
        type: 'scatter',
        mode: 'lines+markers',
        yaxis: 'y2',
        line: { color: '#dc2626', width: 2, dash: 'dot' },
        marker: { size: 6, symbol: 'square' }
    };

    const trace3 = {
        x: years,
        y: unemployment,
        name: 'Unemployment %',
        type: 'scatter',
        mode: 'lines+markers',
        yaxis: 'y3',
        line: { color: '#f59e0b', width: 2, dash: 'dash' },
        marker: { size: 6, symbol: 'diamond' }
    };

    const layout = {
        title: `Time Series: ${selectedCountyName}`,
        xaxis: { title: 'Year' },
        yaxis: { 
            title: 'ER Visits', 
            color: '#2563eb',
            position: 0
        },
        yaxis2: { 
            title: 'Poverty %', 
            color: '#dc2626', 
            overlaying: 'y', 
            side: 'right',
            position: 0.85
        },
        yaxis3: {
            title: 'Unemployment %',
            color: '#f59e0b',
            overlaying: 'y',
            side: 'right',
            position: 0.92
        },
        margin: { l: 60, r: 100, t: 40, b: 40 },
        height: 500,
        hovermode: 'x unified',
        paper_bgcolor: '#fff',
        plot_bgcolor: '#f9f9f9'
    };

    Plotly.newPlot('timeSeriesChart', [trace1, trace2, trace3], layout, { responsive: true });
}

// Render empty time series placeholder
function renderEmptyTimeSeries() {
    const emptyData = [{
        x: [],
        y: [],
        type: 'scatter'
    }];
    
    const layout = {
        title: 'Time Series: Select a County',
        xaxis: { title: 'Year' },
        yaxis: { title: 'Value' },
        annotations: [{
            text: 'Click on a county in the choropleth map to view its time series',
            xref: 'paper',
            yref: 'paper',
            x: 0.5,
            y: 0.5,
            showarrow: false,
            font: { size: 14, color: '#999' }
        }],
        margin: { l: 60, r: 60, t: 40, b: 40 },
        height: 500
    };

    Plotly.newPlot('timeSeriesChart', emptyData, layout, { responsive: true });
    document.getElementById('selectedCountyInfo').textContent = 'Select a county from the map above';
}

// Render scatterplot
function renderScatterPlot(data) {
    const metricKey = document.getElementById('metricSelect').value;
    
    if (data.length === 0) {
        const emptyData = [{
            x: [],
            y: [],
            type: 'scatter'
        }];
        const layout = {
            title: `Healthcare Burden vs. ${metricKey}`,
            xaxis: { title: metricKey },
            yaxis: { title: 'Total ER Visits' },
            annotations: [{
                text: 'No data matches your filter selections',
                xref: 'paper',
                yref: 'paper',
                x: 0.5,
                y: 0.5,
                showarrow: false,
                font: { size: 14, color: '#999' }
            }],
            margin: { l: 60, r: 60, t: 40, b: 40 },
            height: 500
        };
        Plotly.newPlot('scatterPlot', emptyData, layout, { responsive: true });
        return;
    }
    
    const scatterData = [{
        x: data.map(d => d[metricKey]),
        y: data.map(d => d['Total ER Visits'] || 0),
        text: data.map(d => 
            `<b>${d.County}, ${d.State}</b><br>` +
            `${metricKey}: ${d[metricKey].toFixed(2)}%<br>` +
            `ER Visits: ${d['Total ER Visits']}<br>` +
            `Poverty: ${d['Poverty Percentage']}%<br>` +
            `Unemployment: ${d['Unemployment Percentage']}%<br>` +
            `Year: ${d.Year}`
        ),
        hoverinfo: 'text',
        mode: 'markers',
        marker: {
            size: 8,
            color: data.map(d => d.Year),
            colorscale: [
                [0, '#fee8c8'],
                [0.5, '#fdbb84'],
                [1, '#e34a33']
            ],
            showscale: true,
            colorbar: { 
                title: 'Year',
                thickness: 15,
                len: 0.7
            },
            line: { 
                width: 1, 
                color: '#fff'
            },
            opacity: 0.7
        },
        type: 'scatter'
    }];

    const layout = {
        title: {
            text: `Healthcare Burden vs. ${metricKey}`,
            font: { size: 16 }
        },
        xaxis: { 
            title: metricKey,
            gridcolor: '#e5e5e5'
        },
        yaxis: { 
            title: 'Total ER Visits',
            gridcolor: '#e5e5e5'
        },
        margin: { l: 60, r: 80, t: 40, b: 40 },
        height: 500,
        hovermode: 'closest',
        paper_bgcolor: '#fff',
        plot_bgcolor: '#f9f9f9'
    };

    Plotly.newPlot('scatterPlot', scatterData, layout, { responsive: true });
}

// Error handling
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    const main = document.querySelector('main');
    if (main) {
        main.insertBefore(errorDiv, main.firstChild);
    }
}

// Update data info display
function updateDataInfo() {
    const uniqueCounties = new Set(allData.map(d => d['FIPS Code'])).size;
    const years = [...new Set(allData.map(d => d.Year))].sort().join(', ');
    const states = [...new Set(allData.map(d => d.State))].sort().join(', ');
    
    const infoElement = document.querySelector('.bg-blue-50 p');
    if (infoElement) {
        infoElement.textContent = 
            `This dashboard visualizes the relationship between Social Determinants of Health (SDOH)—including poverty, unemployment, and education levels—and healthcare utilization as measured by emergency room visits. ` +
            `Data includes ${uniqueCounties} counties across ${states.split(',').length} states for years: ${years}. ` +
            `Data is sourced from the CDC Social Vulnerability Index and synthetic FHIR patient records.`;
    }
}
