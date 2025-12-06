# --- Imports ---
import psycopg2          # Used for connecting to and interacting with the PostgreSQL database.
import requests          # Used for making HTTP requests to external APIs (Alpha Vantage and GNews).
import time              # Used for pausing execution (time.sleep) to respect API rate limits.
import json              # Not explicitly used but good practice for API handling, retained from original.
from datetime import datetime  # Used for handling date and time stamps for database insertion.
from google import genai       # The official Python SDK for interacting with the Google Gemini API.
from google.genai import types # Used for defining specific types for the Gemini client, retained from original.
# NOTE: The 'config' module must be created separately and contain your API keys and DB credentials.
from config import (
    DB_HOST, DB_NAME, DB_USER, DB_PASSWORD,
    ALPHA_VANTAGE_KEY, GNEWS_API_KEY, GEMINI_API_KEY
)

# --- Configuration Constants ---
STOCK_SYMBOL = "MSFT"                  # The specific stock ticker we are tracking (Microsoft).
GEMINI_MODEL = "gemini-2.5-flash"      # The Gemini model used for sentiment analysis.

# ===============================================================================
# --- 1. Data Loading Functions (L - Load) ---
# These functions handle connecting to PostgreSQL and inserting data into tables.
# ===============================================================================

def insert_stock_data(conn, data):
    """Inserts a single stock price record into the stock_prices table."""
    sql = """
INSERT INTO stock_prices 
(date, open_price, close_price, volume)
VALUES(%s, %s, %s, %s)
ON CONFLICT (date) DO NOTHING;
"""
    # NOTE: The data tuple needs to be simplified to match the 4 columns:
    # (ts_date, open_price, close_price, volume)
    data_simplified = (data[1], data[3], data[4], data[5])
    
    try:
        with conn.cursor() as cur:
            # Execute the SQL command, passing the simplified data tuple
            cur.execute(sql, data_simplified)
        conn.commit() 
        print(f"✅ Fact: Stock price for {data[0]} at {data[2]} inserted.")
    except Exception as e:
        print(f"   ❌ Error inserting stock data: {e}")
        conn.rollback()

def insert_raw_news(conn, news_data_list):
    """Inserts new news articles into the news_raw table."""
    sql = """
    INSERT INTO news_raw
    (title, date_published)
    VALUES (%s, %s)
    RETURNING id; -- CORRECTED: Returning 'id' not 'article_id'
    """
    new_articles = []
    try:
        with conn.cursor() as cur:
            for item in news_data_list:
                published_at_dt = datetime.strptime(item[3], '%Y-%m-%d %H:%M:%S')
                
                # We only insert title and date_published
                # Item tuple is: (symbol, headline, description, published_at_utc)
                cur.execute(sql, (item[1], published_at_dt)) 
                
                # Retrieve the primary key (id) that was just generated
                article_id = cur.fetchone()[0]
                
                # Store the ID along with the article text for AI analysis
                new_articles.append((article_id, item[1], item[2])) 
        conn.commit()
        print(f"   ✅ Raw: Inserted {len(new_articles)} new articles into news_raw.")
        return new_articles
    except Exception as e:
        print(f"   ❌ Error inserting raw news: {e}")
        conn.rollback()
        return []

def insert_sentiment_data(conn, article_id, sentiment, impact_theme):
    """Inserts the AI-generated analysis (sentiment and theme) into the 
    news_sentiment table and marks the raw article as processed."""
    
    # SQL to insert the sentiment and theme
    sql = """
    INSERT INTO news_sentiment
    (article_id, sentiment_score, sentiment_label, theme) 
    VALUES (%s, %s, %s, %s);
    """
    # NOTE: We need to assign a score (e.g., 1.0, -1.0, 0.0) for sentiment_score
    # since we require it for the dashboard SQL AVG() calculation!
    
    sentiment_score_map = {'POSITIVE': 1.0, 'NEGATIVE': -1.0, 'NEUTRAL': 0.0, 'UNKNOWN': 0.0}
    sentiment_score = sentiment_score_map.get(sentiment, 0.0)
    
    # SQL to update the raw table flag is REMOVED because the news_raw table 
    # no longer has the 'is_processed' column (based on our setup_db.py)
    
    try:
        with conn.cursor() as cur:
            # Note: We now insert score and label
            cur.execute(sql, (article_id, sentiment_score, sentiment, impact_theme)) 
        conn.commit()
        print(f"     ✅ Dim: Sentiment for Article {article_id} inserted.")
    except Exception as e:
        print(f"     ❌ Error inserting sentiment data for Article {article_id}: {e}")
        conn.rollback()

# ===============================================================================
# --- 2. Data Extraction Functions (E - Extract) ---
# These functions fetch data from external financial APIs.
# ===============================================================================

def extract_stock_price(symbol):
    """Fetches the latest real-time stock price from the Alpha Vantage API."""
    print(f"--- 1. Extracting Stock Price for {symbol} ---")
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status() # Check for bad HTTP responses (4xx or 5xx)
        data = response.json()
        quote = data.get('Global Quote', {})

        if not quote:
            print("  ⚠️ Alpha Vantage API Error: Global Quote not found. Check API key or symbol.")
            return None

        # Extract specific fields from the API response
        open_price = quote.get('02. open')
        close_price = quote.get('05. price') # Note: This is labeled 'price' but acts as the last trade price
        volume = quote.get('06. volume')
        
        # Capture the current timestamp for when we executed the query
        now = datetime.now()
        ts_date = now.strftime('%Y-%m-%d')
        ts_time = now.strftime('%H:%M:%S')
        
        # Return data as a tuple matching the DB columns
        return (symbol, ts_date, ts_time, open_price, close_price, volume)
    
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error fetching Alpha Vantage data: {e}")
        return None

def extract_latest_news(symbol, limit=10):
    """Fetches the latest news headlines related to the stock symbol from the GNews API."""
    print(f"--- 2. Extracting Latest News for {symbol} ---")
    
    # Construct a search query that includes the ticker and the company name for better results
    query = f'"{symbol}" OR "Microsoft" stock' if symbol == "MSFT" else f'"{symbol}" stock'

    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=us&max={limit}&token={GNEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        articles = data.get('articles', [])
        
        news_list = []
        for article in articles:
            # GNews uses RFC 3339 format (e.g., '2025-12-05T14:00:00Z'). 
            # We clean it up for Python's datetime parser before sending to DB.
            published_at_utc = article.get('publishedAt').replace('T', ' ').replace('Z', '')
            
            news_list.append((
                symbol,
                article.get('title'),
                article.get('description'),
                published_at_utc # The cleaned timestamp string
            ))
        
        print(f"  ✅ Raw: Fetched {len(articles)} potential new articles.")
        return news_list
    
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error fetching GNews data: {e}")
        return []

# ===============================================================================
# --- 3. AI Transformation Function (T - Transform) ---
# This function uses the Gemini model to perform the sentiment analysis.
# ===============================================================================

def analyze_sentiment(news_item, client):
    """
    Uses the Gemini model to analyze the sentiment of a news article
    and extract the financial impact theme in a structured way.
    """
    article_id, headline, description = news_item
    full_text = f"Headline: {headline}\nDescription: {description}"
    
    print(f"--- 3. Analyzing Sentiment for Article {article_id} ---")

    # Define the structure the AI must follow for its response
    schema_prompt = """
    Sentiment: [POSITIVE, NEGATIVE, or NEUTRAL]
    Theme: [A single, concise theme of the impact, e.g., 'Product Launch', 'Regulatory Fine', 'Quarterly Earnings']
    """

    # The main prompt instructs the AI on its role and the format required
    prompt = f"""
    You are an expert financial sentiment analysis agent. Analyze the following news text and determine the overall sentiment 
    towards the stock, and provide a single, concise theme for the news impact. 
    
    Return the output ONLY in the following format:
    {schema_prompt}

    News Text:
    ---
    {full_text}
    ---
    """
    
    try:
        # Call the Gemini API to generate the content based on the prompt
        response = client.models.generate_content(
            model=GEMINI_MODEL, 
            contents=prompt
        )

        # Parse the plain text response into the structured format
        lines = response.text.strip().split('\n')
        
        # Extract sentiment (the part after the colon on the first line)
        sentiment = lines[0].split(':')[-1].strip()
        
        # Extract impact theme (the part after the colon on the second line)
        impact_theme = lines[1].split(':')[-1].strip()
        
        print(f"    AI Result: {sentiment} ({impact_theme})")
        return sentiment, impact_theme

    except Exception as e:
        print(f"    ❌ AI Error for Article {article_id}: {e}")
        # Return fallback values if the API call or parsing fails
        return "UNKNOWN", "API_ERROR"

# ===============================================================================
# --- 4. Main Pipeline Execution ---
# Orchestrates the entire ETL process.
# ===============================================================================

def run_pipeline():
    """Runs the full financial ETL pipeline step-by-step."""
    print("==============================================")
    print(f"Starting ETL Pipeline for {STOCK_SYMBOL} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==============================================")
    
    conn = None
    try:
        # Step 1: Connect to the Database
        print("Connecting to database...")
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
        print("Connection successful.")
        
        # Step 2: Extract Stock Price (E) and Load to Fact Table (L1)
        stock_data = extract_stock_price(STOCK_SYMBOL)
        if stock_data:
            insert_stock_data(conn, stock_data)

        # Step 3: Extract Latest News (E) and Load to Raw Table (L2)
        news_data_list = extract_latest_news(STOCK_SYMBOL, limit=10)
        
        # Only articles that don't already exist in the database will be returned
        new_articles_to_process = insert_raw_news(conn, news_data_list)
        
        # Step 4: Transform (T) and Load Sentiment Data (L3)
        if new_articles_to_process:
            print(f"\n--- 4. Processing {len(new_articles_to_process)} New Articles with AI ---")
            
            # Initialize the Gemini client using the key from your config file
            ai_client = genai.Client(api_key=GEMINI_API_KEY) 

            for article in new_articles_to_process:
                article_id, _, _ = article 
                
                # Analyze sentiment and theme using the AI
                sentiment, impact_theme = analyze_sentiment(article, ai_client)
                
                # Load the AI-generated results into the Dimension Table
                insert_sentiment_data(conn, article_id, sentiment, impact_theme)
                
                # Wait for 1 second to avoid hitting rate limits on the Gemini API
                time.sleep(1) 

        print("\n==============================================")
        print("ETL Pipeline Execution Complete.")
        print("==============================================")
        
    except (Exception, psycopg2.Error) as error:
        # Catch any critical errors during connection or execution
        print(f"\nFATAL ERROR during pipeline execution: {error}")
    finally:
        # Step 5: Close the Database Connection
        if conn is not None:
            conn.close()
            print("Database connection closed.")

# Entry point: Run the main pipeline function when the script is executed
if __name__ == "__main__":
    run_pipeline()