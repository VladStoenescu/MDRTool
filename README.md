# MDRTool

Simple Streamlit dashboard for tracking Migration Dry Run readiness to **21 July 2026**.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   streamlit run app.py
   ```

## Included files

- `app.py` - one-page Streamlit dashboard
- `data/readiness.csv` - sample workstream readiness data
- `data/timeline.csv` - sample timeline activities
- `data/actions.csv` - sample action log

## Features

- Overall readiness status for six workstreams
- Editable readiness and action log tables
- Plotly timeline to the dry run date
- Automatic management summary
- CSV upload to refresh each dataset
- CSV and Excel export