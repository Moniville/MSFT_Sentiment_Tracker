import psycopg2
import pandas as pd
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Database connection failed: {e}")
        return None

def get_daily_sentiment_df():
    """
    Fetches the combined stock price and daily average sentiment from the database
    and returns it as a pandas DataFrame.
    
    CRITICAL FIX: Uses a LEFT JOIN to ensure stock prices are always returned, 
    even if there is no matching sentiment data for that exact day.
    """
    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame() # Return empty DataFrame on failure

    # SQL Query: Uses LEFT JOIN to combine prices and sentiment
    sql = """
    -- Calculate the average sentiment score per day and symbol
    WITH DailySentiment AS (
        SELECT
            CAST(T2.published_at AS DATE) AS ts_date,
            T2.symbol,
            AVG(T1.sentiment_score) AS average_sentiment_score
        FROM news_sentiment_dim T1
        JOIN news_raw T2 ON T1.raw_article_id = T2.article_id
        GROUP BY 1, 2
    ),
    -- Get the last (most recent) close price for each day where we have price data
    DailyClosePrice AS (
        SELECT
            ts_date,
            symbol,
            close_price,
            -- Rank by time to pick the last price recorded for that day
            ROW_NUMBER() OVER (PARTITION BY ts_date, symbol ORDER BY ts_time DESC) as rn
        FROM stock_prices_fact
    )
    -- Join the daily sentiment to the most recent daily close price using a LEFT JOIN
    SELECT
        T1.ts_date,
        T1.symbol,
        T1.close_price,
        -- Use COALESCE to set sentiment to 0.0 if no news was found for that day (NULL result from LEFT JOIN)
        COALESCE(T2.average_sentiment_score, 0.0) AS average_sentiment_score
    FROM DailyClosePrice T1
    LEFT JOIN DailySentiment T2 
        ON T1.ts_date = T2.ts_date AND T1.symbol = T2.symbol
    WHERE T1.rn = 1 -- Select only the most recent price for the day
    ORDER BY T1.ts_date ASC;
    """
    
    try:
        logging.info("Executing SQL query to fetch dashboard data...")
        # Note: pandas warns about using a direct connection object, but it works fine for this purpose.
        df = pd.read_sql_query(sql, conn)
        df['ts_date'] = pd.to_datetime(df['ts_date'])
        logging.info(f"Successfully fetched {len(df)} records for the dashboard.")
        return df
    except Exception as e:
        logging.error(f"Error fetching data for dashboard: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")