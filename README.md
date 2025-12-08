📈 Financial Sentiment Tracker (MSFT) - A Data Engineering Journey

This project was a "vibe-coded" experiment, born out of curiosity to explore basic ETL (Extract, Transform, Load) and Data Engineering principles. It leverages the Gemini API for sophisticated sentiment analysis to create a real-time, AI-powered Streamlit dashboard.

The core goal was to build a complete, end-to-end pipeline:

Extract: Gather historical stock price data (Alpha Vantage) and current news articles (GNews).

Transform (AI-Powered): Utilize the Gemini API to rapidly analyze news text and generate a standardized numerical sentiment score.

Load: Store all structured data (prices, news, sentiment scores) reliably into a PostgreSQL database.

Visualize: Display the results and trend analysis in a user-friendly Streamlit dashboard.

Below is a screenshot of the PostgreSQL Database
<img width="1366" height="671" alt="Screenshot 2025-12-05 190326" src="https://github.com/user-attachments/assets/1b907195-367b-4a19-8fd7-66ccd26286f5" />


Below is a screenshot of the Extraction and Sentimentization
<img width="1364" height="694" alt="Screenshot 2025-12-05 181415" src="https://github.com/user-attachments/assets/1ef61447-6199-4bd7-99ac-2dcbe3ad545b" />


Below is a screen of the visual created via Streamlit
<img width="1349" height="579" alt="Screenshot 2025-12-05 193429" src="https://github.com/user-attachments/assets/8b430366-a199-4b5a-b711-52b325ba70ff" />




Prerequisites

PostgreSQL: A running PostgreSQL database instance (local or hosted).

Python: Python 3.9+ installed.

API Keys:

Gemini API Key (for sentiment analysis)

Alpha Vantage API Key (for stock prices)

GNews API Key (for news headlines)

Setup Guide

Follow these steps to set up the environment and run the tracker on your local machine.

Clone the Repository:

git clone [Your Repository URL]


Create Virtual Environment & Install Dependencies:
Navigate into the project directory and set up the required Python environment:

python -m venv venv
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\activate   # Windows
pip install -r requirements.txt


Configure Secrets (config.py):
For security, this file is not tracked by Git. You must create a new file named config.py in the root directory and populate it with your personal credentials:

# --- API Keys ---
GEMINI_API_KEY = "YOUR_GEMINI_KEY"

ALPHA_VANTAGE_KEY = "YOUR_ALPHA_VANTAGE_KEY"

GNEWS_API_KEY = "YOUR_GNEWS_KEY"

# --- Database Credentials ---
DB_HOST = "localhost" # or your remote host IP/URL

DB_NAME = "your_db_name"

DB_USER = "your_db_user"

DB_PASSWORD = "your_db_password"

DB_PORT = "5432" 


Initialize Database Tables:
Run the setup script once to create the necessary tables (stock_prices, news_raw, news_sentiment):

python setup_db.py


Run the Data Pipeline (ETL):
Execute the pipeline to fetch initial data, analyze sentiment, and populate the database. Run this command periodically to keep your data fresh:

python pipeline.py


Launch the Dashboard:
Start the Streamlit application to visualize the data:

streamlit run dashboard_app.py
