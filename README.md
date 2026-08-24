# Investors Tracker

A Streamlit application for exploring and analysing investor activity across companies, geographies, sectors, funding stages, and investment types.

The application connects to a PostgreSQL database containing investor and deal data and provides an interactive interface for identifying and comparing investors based on their investment activity.

## Features

* 🔍 Search for specific investors by name
* 🌍 Filter investment activity by company country
* 🏙️ Filter by company city
* 📦 Filter by vertical
* 🏷️ Filter by sector
* 🚀 Filter by company stage
* 🌀 Filter by round type:

  * Equity
  * Debt
  * Grant
* 📅 Filter by deal announcement date
* 📌 Filter investors by headquarters location
* 🏢 Filter by investor type
* ➕ Include or exclude values for each filter
* 📊 View investor activity and deal statistics
* 🔗 Click through to investor websites
* 📥 Download filtered results as a CSV file

## Investor Metrics

For each investor, the application provides:

| Metric                     | Description                                        |
| -------------------------- | -------------------------------------------------- |
| Investor Name              | Name of the investor                               |
| Investor URL               | Investor website                                   |
| Investor HQ                | Investor headquarters location                     |
| Investor Type              | Type of investor                                   |
| Deal Count (Lead)          | Number of deals where the investor was the lead    |
| Deal Count (Participating) | Number of deals where the investor participated    |
| Deal Count (All)           | Total number of matching deals                     |
| Average Deal Size          | Average size of matching deals                     |
| Active Country(s)          | Countries where the investor has been active       |
| Active City(s)             | Cities where the investor has been active          |
| Active Vertical(s)         | Verticals where the investor has been active       |
| Active Stage(s)            | Funding stages where the investor has been active  |
| Active Sector(s)           | Sectors where the investor has been active         |
| Most Active Country        | Country with the highest investment activity       |
| Most Active City           | City with the highest investment activity          |
| Most Active Vertical       | Vertical with the highest investment activity      |
| Most Active Stage          | Funding stage with the highest investment activity |
| Most Active Sector         | Sector with the highest investment activity        |

## Tech Stack

* **Python**
* **Streamlit**
* **Pandas**
* **PostgreSQL**
* **SQLAlchemy**
* **psycopg2**

## Project Structure

```text
investors-tracker/
├── Procfile
├── requirements.txt
├── setup.sh
├── streamlit_investor_tracker.py
└── README.md
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ayenko/investors-tracker.git
cd investors-tracker
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

#### macOS/Linux

```bash
source venv/bin/activate
```

#### Windows

```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Configuration

The application requires access to a PostgreSQL database containing the investor and deal data.

For security, database credentials should be provided through environment variables or Streamlit secrets rather than being hardcoded in the application.

For example, create a `.streamlit/secrets.toml` file:

```toml
[database]
host = "your-database-host"
port = 5432
database = "your-database-name"
username = "your-username"
password = "your-password"
```

Then update the database connection in the application to use these values.

> ⚠️ Never commit database credentials or other secrets to GitHub.

## Running the Application

Start the Streamlit application with:

```bash
streamlit run streamlit_investor_tracker.py
```

The application will typically be available at:

```text
http://localhost:8501
```

## How It Works

The application queries investor and deal data from the database and aggregates investment activity by investor.

Users can apply multiple filters to narrow down results. Each filter can operate in one of two modes:

* **Include** — only show results matching the selected values.
* **Exclude** — remove results matching the selected values.

The application then calculates metrics including:

* Total number of deals
* Lead investments
* Participating investments
* Average deal size
* Active markets
* Active cities
* Active sectors and verticals
* Most active investment markets
* Most active funding stages

Results are displayed in an interactive table and can be downloaded as a CSV file.

## Database Tables

The application currently queries data from the following tables:

* `intelligence.investors`
* `intelligence.companyinvestors`
* `intelligence.deals`

## Deployment

The repository includes a `Procfile` and `setup.sh`, which can be used to support deployment to platforms such as Heroku or similar container-based application platforms.

Ensure that all required environment variables and database credentials are configured in the deployment environment.

## Security

This application connects to a database containing proprietary data.

Before deploying or sharing the repository publicly:

* [ ] Remove hardcoded database credentials
* [ ] Rotate any credentials that have already been exposed
* [ ] Use environment variables or Streamlit secrets
* [ ] Add secret files to `.gitignore`
* [ ] Use a database account with the minimum permissions required
* [ ] Avoid exposing sensitive database information in logs or error messages

## Future Improvements

Potential enhancements include:

* Investor comparison views
* Data visualisations and charts
* Saved searches and filters
* Additional deal metrics
* Pagination for large datasets
* More robust error handling
* Automated tests
* User authentication
* Role-based access controls
* Deployment automation with CI/CD
