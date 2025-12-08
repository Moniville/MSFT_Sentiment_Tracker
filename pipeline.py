import psycopg2
import requests
import time
import json
from datetime import datetime
from google import genai
from google.genai import types
from config import (
    DB_HOST, DB_NAME, DB_USER, DB_PASSWORD,
    ALPHA_VANTAGE_KEY, GNEWS_API_KEY, GEMINI_API_KEY, DB_PORT
)

# Configuration 
STOCK_SYMBOL = "MSFT"
GEMINI_MODEL = "gemini-2.5-flash"
# Wait 13 seconds between AI calls to respect the 5 req/min quota on the free tier (1 request every 12 seconds)
AI_CALL_DELAY = 13 

# Database Insertion Functions (L - Load)

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, 
            password=DB_PASSWORD, port=DB_PORT
        )
        print("Connecting to database...")
        print("Connection successful.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"FATAL ERROR: Database connection failed. {e}")
        return None

def insert_stock_data(conn, data):
    """Inserts a single stock price record into the stock_prices_fact table."""
    sql = """
INSERT INTO stock_prices_fact
(symbol, ts_date, ts_time, open_price, close_price, volume)
VALUES(%s, %s, %s, %s, %s, %s)
ON CONFLICT (symbol, ts_date, ts_time) DO NOTHING;
"""
    try: 
        with conn.cursor() as cur:
            cur.execute(sql, data)
        conn.commit()
        print(f"✅ Fact: Stock price for {data[0]} at {data[2]} inserted.")
    except Exception as e:
        print(f"  ❌ Error inserting stock data: {e}")
        conn.rollback()

# --- FIX: Ensures ON CONFLICT logic matches the SQL schema ---
def insert_raw_news(conn, news_data_list):
    """Inserts multiple raw news records into the news_raw table and returns only unprocessed ones."""
    
    # SQL to insert, skipping if headline already exists
    insert_sql = """
    INSERT INTO news_raw
    (symbol, headline, description, published_at, is_processed)
    VALUES (%s, %s, %s, %s, FALSE)
    ON CONFLICT (headline) DO NOTHING  -- FIX IS HERE: Uses 'headline' which is now UNIQUE
    RETURNING article_id;
    """

    # SQL to fetch unprocessed articles that might have been inserted in a previous run
    fetch_unprocessed_sql = """
    SELECT article_id, headline, description FROM news_raw WHERE is_processed = FALSE;
    """
    
    try:
        with conn.cursor() as cur:
            # 1. Insert new articles 
            for item in news_data_list:
                published_at_dt = datetime.strptime(item[3], '%Y-%m-%d %H:%M:%S')
                cur.execute(insert_sql, (item[0], item[1], item[2], published_at_dt))

            conn.commit()
            print(f"  ✅ Raw: Checked {len(news_data_list)} articles for insertion.")
            
            # 2. Fetch all articles currently flagged as unprocessed
            cur.execute(fetch_unprocessed_sql)
            unprocessed_articles = cur.fetchall()
            
            print(f"  📝 Info: {len(unprocessed_articles)} articles are awaiting AI analysis.")
            return unprocessed_articles 
            
    except Exception as e:
        print(f"  ❌ Error inserting/fetching raw news: {e}")
        conn.rollback()
        return []

def insert_sentiment_data(conn, article_id, sentiment, impact_theme):
    """Inserts the AI-generated sentiment data into the news_sentiment_dim table."""
    
    sentiment_map = {
        "POSITIVE": 1.0,
        "NEGATIVE": -1.0,
        "NEUTRAL": 0.0,
        "UNKNOWN": 0.0, 
        "API_ERROR": 0.0 
    }
    
    sentiment_score = sentiment_map.get(sentiment.upper(), 0.0)

    sql = """
    INSERT INTO news_sentiment_dim
    (raw_article_id, ai_sentiment, ai_impact_theme, sentiment_score)
    VALUES (%s, %s, %s, %s);
    """
    update_raw_sql = "UPDATE news_raw SET is_processed = TRUE WHERE article_id = %s;"
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (article_id, sentiment, impact_theme, sentiment_score))
            
            # Only mark as processed if the sentiment wasn't an API error
            if sentiment != "API_ERROR":
                cur.execute(update_raw_sql, (article_id,))

        conn.commit()
        print(f"    ✅ Dim: Sentiment for Article {article_id} inserted (Score: {sentiment_score}).")
    except Exception as e:
        print(f"    ❌ Error inserting sentiment data for Article {article_id}: {e}")
        conn.rollback()

# --- 2. Data Extraction Functions (E - Extract) ---

def extract_stock_price(symbol):
    """Fetches the latest real-time stock price from Alpha Vantage."""
    print(f"--- 1. Extracting Stock Price for {symbol} ---")
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status() 
        data = response.json()
        quote = data.get('Global Quote', {})

        if not quote:
            print("  ⚠️ Alpha Vantage API Error: Global Quote not found. Check API key or symbol.")
            return None

        open_price = quote.get('02. open')
        close_price = quote.get('05. price')
        volume = quote.get('06. volume')
        
        now = datetime.now()
        ts_date = now.strftime('%Y-%m-%d')
        ts_time = now.strftime('%H:%M:%S')
        
        return (symbol, ts_date, ts_time, open_price, close_price, volume)
    
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error fetching Alpha Vantage data: {e}")
        return None

def extract_latest_news(symbol, limit=10):
    """Fetches the latest news headlines related to the stock symbol from GNews."""
    print(f"--- 2. Extracting Latest News for {symbol} ---")
    
    query = f'"{symbol}" OR "Microsoft" stock' if symbol == "MSFT" else f'"{symbol}" stock'

    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=us&max={limit}&token={GNEWS_API_KEY}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        articles = data.get('articles', [])
        
        news_list = []
        for article in articles:
            published_at_utc = article.get('publishedAt').replace('T', ' ').replace('Z', '')
            
            news_list.append((
                symbol,
                article.get('title'),
                article.get('description'),
                published_at_utc 
            ))
        
        print(f"  ✅ Raw: Fetched {len(articles)} potential new articles.")
        return news_list
    
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error fetching GNews data: {e}")
        return []

# --- 3. AI Transformation (T - Transform) ---

def analyze_sentiment(news_item, client):
    """Uses the Gemini model to analyze sentiment and extract impact theme."""
    article_id, headline, description = news_item
    full_text = f"Headline: {headline}\nDescription: {description}"
    
    print(f"--- 3. Analyzing Sentiment for Article {article_id} ---")

    schema_prompt = """
    Sentiment: [POSITIVE, NEGATIVE, or NEUTRAL]
    Theme: [A single, concise theme of the impact, e.g., 'Product Launch', 'Regulatory Fine', 'Quarterly Earnings']
    """

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
        response = client.models.generate_content(
            model=GEMINI_MODEL, 
            contents=prompt
        )

        lines = response.text.strip().split('\n')
        
        if len(lines) >= 2 and ':' in lines[0] and ':' in lines[1]:
            sentiment = lines[0].split(':')[-1].strip()
            impact_theme = lines[1].split(':')[-1].strip()
            print(f"    AI Result: {sentiment} ({impact_theme})")
            return sentiment, impact_theme
        else:
            print(f"    ⚠️ AI Result: UNKNOWN - Could not parse structured response.")
            return "UNKNOWN", "PARSE_ERROR"


    except Exception as e:
        print(f"    ❌ AI Error for Article {article_id}: {e}")
        return "API_ERROR", "API_ERROR"

# --- Main Pipeline Execution ---

def run_pipeline():
    """Runs the full ETL pipeline."""
    print("==============================================")
    print(f"Starting ETL Pipeline for {STOCK_SYMBOL} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==============================================")
    
    conn = None
    try:
        # 1. Connect to the Database
        conn = get_db_connection()
        if conn is None:
            return

        # 2. Extract and Load Stock Price (E -> L1)
        stock_data = extract_stock_price(STOCK_SYMBOL)
        if stock_data:
            insert_stock_data(conn, stock_data)

        # 3. Extract and Load Raw News (E -> L2)
        news_data_list = extract_latest_news(STOCK_SYMBOL, limit=10)
        unprocessed_articles = insert_raw_news(conn, news_data_list)
        
        # 4. Initialize Gemini Client and Transform (T)
        if unprocessed_articles:
            print(f"\n--- 4. Processing {len(unprocessed_articles)} New/Unprocessed Articles with AI ---")
            
            ai_client = genai.Client(api_key=GEMINI_API_KEY) 

            for i, article in enumerate(unprocessed_articles):
                article_id, _, _ = article 
                
                sentiment, impact_theme = analyze_sentiment(article, ai_client)
                
                # 5. Load Sentiment Data (L3)
                insert_sentiment_data(conn, article_id, sentiment, impact_theme)
                
                # Rate limit safety
                if i < len(unprocessed_articles) - 1:
                    print(f"    ⏳ Waiting {AI_CALL_DELAY} seconds to respect AI quota...")
                    time.sleep(AI_CALL_DELAY) 
                
        print("\n==============================================")
        print("ETL Pipeline Execution Complete.")
        print("==============================================")
        
    except (Exception, psycopg2.Error) as error:
        print(f"\nFATAL ERROR during pipeline execution: {error}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")
            
if __name__ == "__main__":
    run_pipeline()