#!/usr/bin/env python3
"""
10k Perovskites Live Dashboard
A Flask-based dashboard with ORCID OAuth, Plotly visualizations, and auto-refresh
"""
import os
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, session, jsonify
from authlib.integrations.flask_client import OAuth
from google.cloud import bigquery
import plotly
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
from functools import wraps
import requests
import base64
from dotenv import load_dotenv
from pycrucible import CrucibleClient
from pycrucible.utils import get_tz_isoformat
load_dotenv()
cruc_client = CrucibleClient(
    api_url="https://crucible.lbl.gov/testapi",
    api_key = os.environ.get("crucible_apikey")
)

# Set up credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.expanduser('~/.config/mf-crucible-9009d3780383.json')

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Change this to a fixed secret in production

# ORCID OAuth configuration
oauth = OAuth(app)
orcid = oauth.register(
    'orcid',
    client_id=os.getenv('ORCID_CLIENT_ID', 'YOUR_ORCID_CLIENT_ID'),
    client_secret=os.getenv('ORCID_CLIENT_SECRET', 'YOUR_ORCID_CLIENT_SECRET'),
    authorize_url='https://orcid.org/oauth/authorize',
    authorize_params=None,
    access_token_url='https://orcid.org/oauth/token',
    access_token_params=None,
    client_kwargs={'scope': '/authenticate'},
)

# BigQuery client
bq_client = bigquery.Client(project='mf-crucible')

PROJECT_ID = '10k_perovskites'

def get_thumbnail_image_data(dataset_id):
    """
    Get the actual image data from cloud storage for embedding in HTML
    """
    try:
        download_links = cruc_client.get_dataset_download_links(dataset_id)
        print(f'{download_links=}')

        download_url = [v for k,v in download_links.items() if k.endswith('.jpeg')][0]
        print(f'{download_url=}')

        if not download_url:
            return None
        
        # Download the image
        response = requests.get(download_url)
        print(f'{response.content=}')
        if response.status_code == 200:
            # Convert to base64 for embedding in HTML
            image_data = base64.b64encode(response.content).decode('utf-8')
            
            # Determine content type from file extension or response headers
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            
            return f"data:{content_type};base64,{image_data}"
        else:
            return None
    except Exception as e:
        print(f"Error fetching thumbnail image: {e}")
        return None


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'orcid' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login')
def login():
    """ORCID OAuth login"""
    redirect_uri = url_for('authorize', _external=True)
    return orcid.authorize_redirect(redirect_uri)


@app.route('/authorize')
def authorize():
    """ORCID OAuth callback"""
    token = orcid.authorize_access_token()
    session['orcid'] = token['orcid']
    session['name'] = token.get('name', 'User')
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('login'))


def get_dashboard_data():
    """Fetch all dashboard metrics from BigQuery"""

    # 1. Total thin films
    query_thin_films = f"""
    SELECT COUNT(*) as count
    FROM `mf-crucible.crucible.sample`
    WHERE project_id = '{PROJECT_ID}'
      AND LOWER(sample_type) = 'thin film'
    """
    thin_films_count = bq_client.query(query_thin_films).to_dataframe()['count'][0]

    # 2. Sample types breakdown
    query_sample_types = f"""
    SELECT
        COALESCE(sample_type, 'Unknown') as sample_type,
        COUNT(*) as count
    FROM `mf-crucible.crucible.sample`
    WHERE project_id = '{PROJECT_ID}'
    GROUP BY sample_type
    ORDER BY count DESC
    """
    df_sample_types = bq_client.query(query_sample_types).to_dataframe()

    # 3. Specific dataset counts
    query_spin_runs = f"""
    SELECT COUNT(*) as count
    FROM `mf-crucible.crucible.dataset`
    WHERE project_id = '{PROJECT_ID}'
      AND LOWER(measurement) LIKE '%spin%'
    """
    spin_runs_count = bq_client.query(query_spin_runs).to_dataframe()['count'][0]

    query_sample_well = f"""
    SELECT COUNT(*) as count
    FROM `mf-crucible.crucible.dataset`
    WHERE project_id = '{PROJECT_ID}'
      AND LOWER(measurement) LIKE '%sample well%'
    """
    sample_well_count = bq_client.query(query_sample_well).to_dataframe()['count'][0]

    query_uvvis_datasets = f"""
    SELECT COUNT(*) as count
    FROM `mf-crucible.crucible.dataset`
    WHERE project_id = '{PROJECT_ID}'
      AND LOWER(measurement) LIKE '%oospec%'
    """
    uvvis_datasets_count = bq_client.query(query_uvvis_datasets).to_dataframe()['count'][0]

    # Dataset types breakdown for sample type pie chart
    query_dataset_types = f"""
    SELECT
        COALESCE(measurement, 'Unknown') as measurement,
        COUNT(*) as count
    FROM `mf-crucible.crucible.dataset`
    WHERE project_id = '{PROJECT_ID}'
    GROUP BY measurement
    ORDER BY count DESC
    LIMIT 10
    """
    df_dataset_types = bq_client.query(query_dataset_types).to_dataframe()

    # 4. Spectra count (UV-Vis type data)
    # Calculate as: datasets * samples per dataset * 8
    query_spectra = f"""
    SELECT SUM(sample_count * 8) as total_spectra
    FROM (
        SELECT
            d.id,
            COUNT(DISTINCT dsl.sample_id) as sample_count
        FROM `mf-crucible.crucible.dataset` d
        LEFT JOIN `mf-crucible.crucible.datasetsamplelink` dsl ON d.id = dsl.dataset_id
        WHERE d.project_id = '{PROJECT_ID}'
          AND LOWER(d.measurement) LIKE '%pollux_oospec%'
        GROUP BY d.id
    )
    """
    spectra_result = bq_client.query(query_spectra).to_dataframe()['total_spectra'][0]
    spectra_count = int(spectra_result) if spectra_result is not None else 0

    # 5. Cumulative thin films over time
    query_samples_time = f"""
    WITH daily_counts AS (
        SELECT
            COALESCE(
                SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', date_created),
                SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%S', date_created)
            ) as timestamp,
            DATE(COALESCE(
                SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', date_created),
                SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%S', date_created)
            )) as date
        FROM `mf-crucible.crucible.sample`
        WHERE project_id = '{PROJECT_ID}'
          AND sample_type = 'thin film'
          AND date_created IS NOT NULL
    ),
    daily_totals AS (
        SELECT
            date,
            COUNT(*) as daily_count
        FROM daily_counts
        WHERE date IS NOT NULL
        GROUP BY date
        ORDER BY date
    )
    SELECT
        date,
        daily_count,
        SUM(daily_count) OVER (ORDER BY date) as cumulative_count
    FROM daily_totals
    ORDER BY date
    """
    df_samples_time = bq_client.query(query_samples_time).to_dataframe()

    # 6. Datasets created over time (skip creation_time for now due to invalid format)
    # We'll use a simpler count by dataset type as alternative
    query_dataset_count = f"""
    SELECT COUNT(*) as total_datasets
    FROM `mf-crucible.crucible.dataset`
    WHERE project_id = '{PROJECT_ID}'
    """
    total_datasets = bq_client.query(query_dataset_count).to_dataframe()['total_datasets'][0]

    # 7. Get thin film samples with their parent precursor solutions for UMAP
    query_thin_films_precursors = f"""
    WITH thin_films AS (
        SELECT id, sample_name, description
        FROM `mf-crucible.crucible.sample`
        WHERE project_id = '{PROJECT_ID}'
          AND LOWER(sample_type) = 'thin film'
    ),
    precursor_links AS (
        SELECT
            tf.id as thin_film_id,
            tf.sample_name as thin_film_name,
            ps.sample_name as precursor_name,
            ps.description as precursor_description
        FROM thin_films tf
        LEFT JOIN `mf-crucible.crucible.samplelink` sl ON tf.id = sl.sample_id
        LEFT JOIN `mf-crucible.crucible.sample` ps ON sl.parent_sample_id = ps.id
        WHERE ps.sample_type = 'precursor solution'
    )
    SELECT *
    FROM precursor_links
    LIMIT 500
    """
    df_thin_films_precursors = bq_client.query(query_thin_films_precursors).to_dataframe()

    # 8. Get a random thumbnail - just get any recent sample with an image for now
    query_thumbnail_of_day = f"""
    SELECT
        s.id as sample_id,
        s.sample_name,
        s.description,
        s.date_created,
        s.owner_orcid,
        s.sample_type,
        d.file_to_upload,
        d.dataset_name,
        d.source_folder,
        d.id as dataset_id,
        d.unique_id as unique_id,
        DATE(PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', s.date_created)) as sample_date,
        CASE WHEN DATE(PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', s.date_created)) = CURRENT_DATE()
             THEN true ELSE false END as is_today
    FROM `mf-crucible.crucible.sample` s
    JOIN `mf-crucible.crucible.datasetsamplelink` dsl ON s.id = dsl.sample_id
    JOIN `mf-crucible.crucible.dataset` d ON dsl.dataset_id = d.id
    WHERE s.project_id = '{PROJECT_ID}'
      AND LOWER(d.measurement) LIKE '%sample well%'
      AND d.file_to_upload IS NOT NULL
      AND s.date_created IS NOT NULL
    ORDER BY PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%Ez', s.date_created) DESC
    LIMIT 1
    """
    df_thumbnail_of_day = bq_client.query(query_thumbnail_of_day).to_dataframe()

    thumbnail_of_day_data = None
    if len(df_thumbnail_of_day) > 0:
        thumbnail_of_day_data = df_thumbnail_of_day.iloc[0].to_dict()
        dataset_id = thumbnail_of_day_data['unique_id']
        image_data = get_thumbnail_image_data(dataset_id)
        
        if image_data:
            thumbnail_of_day_data['image_data'] = image_data
        else:
            # Fallback to showing source folder if image can't be retrieved
            thumbnail_of_day_data['image_data'] = None

    return {
        'thin_films_count': int(thin_films_count),
        'spectra_count': int(spectra_count),
        'total_datasets': int(total_datasets),
        'spin_runs_count': int(spin_runs_count),
        'sample_well_count': int(sample_well_count),
        'uvvis_datasets_count': int(uvvis_datasets_count),
        'sample_types': df_sample_types.to_dict('records'),
        'dataset_types': df_dataset_types.to_dict('records'),
        'samples_time': df_samples_time.to_dict('records'),
        'thin_films_precursors': df_thin_films_precursors.to_dict('records'),
        'thumbnail_of_day': thumbnail_of_day_data
    }


@app.route('/')
def index():
    """Main dashboard page - redirect to login if not authenticated"""
    # For development, comment out the login requirement
    # if 'orcid' not in session:
    #     return redirect(url_for('login'))

    return render_template('dashboard.html',
                         user=session.get('name', 'Guest'))


@app.route('/api/data')
def api_data():
    """API endpoint to fetch dashboard data"""
    try:
        data = get_dashboard_data()
        data['timestamp'] = datetime.now().isoformat()
        return jsonify(data)
    except Exception as e:
        import traceback
        print("ERROR in get_dashboard_data:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
