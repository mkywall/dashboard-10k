# 10k Perovskites Live Dashboard

A beautiful, modern Flask-based dashboard for visualizing and tracking the 10k Perovskites project data from BigQuery.


## Cloud Deployment
- Required environment variables are defined in the cloudbuild.yaml
- Pushes to github trigger google cloud build of docker image and deployment to cloud run
- Image stored in google cloud artifact registry

## Features

- **Real-time Data**: Auto-refreshes every 30 seconds
- **ORCID OAuth**: Secure authentication (optional for development)
- **Interactive Visualizations**: Powered by Plotly
- **Responsive Design**: Modern UI with Tailwind CSS
- **Key Metrics**:
  - Total thin films generated
  - UV-Vis spectra acquired
  - Sample type distribution
  - Dataset type breakdown
  - Time series of sample creation
  - Thin film-precursor relationships

## Setup

### 1. Navigate to Project Directory

```bash
cd ~/dashboard-10k
```

### 2. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 3. Install Dependencies (if not already installed)

```bash
pip install -r requirements.txt
```

### 4. Configure BigQuery Credentials

Specify a local path to your cloud credentials json file. 

This is already configured in the code.

### 5. (Optional) Configure ORCID OAuth

If you want to enable ORCID authentication, set these environment variables:

```bash
export ORCID_CLIENT_ID="your_client_id"
export ORCID_CLIENT_SECRET="your_client_secret"
```

For development, authentication is currently disabled in the code. To enable it, uncomment the login check in `dashboard_app.py`.

## Running the Dashboard

```bash
cd ~/dashboard-10k
source venv/bin/activate
python dashboard_app.py
```

Then open your browser to:
```
http://localhost:5000
```

## Dashboard Components

### KPI Cards
- **Thin Films**: Total number of thin film samples
- **UV-Vis Spectra**: Number of spectroscopic measurements
- **Total Datasets**: All datasets in the project
- **Sample Types**: Number of different sample categories

### Visualizations
1. **Sample Types Distribution**: Pie chart showing breakdown of sample types
2. **Top Dataset Types**: Bar chart of most common dataset measurements
3. **Samples Over Time**: Line chart showing sample creation timeline
4. **Thin Film-Precursor Relationships**: Treemap visualization of precursor solutions

## API Endpoint

The dashboard exposes a REST API for data access:

```
GET /api/data
```

Returns JSON with all dashboard metrics.

## Auto-Refresh

The dashboard automatically refreshes data every 30 seconds. You can also manually refresh by clicking the "Refresh" button in the header.

## Development

To modify the dashboard:

- **Backend logic**: Edit `dashboard_app.py`
- **Frontend UI**: Edit `templates/dashboard.html`
- **Styling**: Modify the Tailwind CSS classes in the HTML
- **Charts**: Update the Plotly chart configurations in the JavaScript section

## Project Structure

```
10k-stats/
├── dashboard_app.py              # Flask application
├── templates/
│   └── dashboard.html            # Dashboard UI template
├── requirements.txt              # Python dependencies
├── venv/                         # Virtual environment
└── README.md                     # This file
```

## Troubleshooting

### Port already in use
If port 5000 is already in use, modify the port in `dashboard_app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

### Missing dependencies
Reinstall from requirements:
```bash
pip install -r requirements.txt --force-reinstall
```
