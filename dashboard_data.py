import pandas as pd
import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database using
    credentials imported from config.py.
    """
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
        logging.error(f"Database connection failed. Ensure PostgreSQL is running and credentials in config.py are correct. Error: {e}")
        # Return None on failure so calling functions can handle it gracefully
        return None

def fetch_aggregated_data():
    """
    Fetches the aggregated financial and sentiment data from the PostgreSQL database
    and returns it as a pandas DataFrame.
    """
    conn = get_db_connection()
    if conn is None:
        logging.warning("Could not fetch data due to database connection failure.")
        return pd.DataFrame() 

    # SQL Query to join stock prices and calculate a daily average sentiment score
    # NOTE: The entire SQL block and code below must be indented under the function!
    SQL_QUERY = """
    SELECT
        s.date,
        s.open_price,
        s.close_price,
        s.volume,
        -- Calculate the average sentiment score for all news articles on that day
        CASE
            WHEN COUNT(n.sentiment_score) > 0 THEN AVG(n.sentiment_score)
            ELSE 0 
        END AS avg_sentiment_score,
        -- Calculate the 7-day rolling average of the close price for smoothing the trend
        AVG(s.close_price) OVER (ORDER BY s.date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_avg_7d
    FROM
        stock_prices s
    LEFT JOIN
        news_raw nr ON s.date = nr.date_published  -- JOIN 1: Get the date from news_raw
    LEFT JOIN
        news_sentiment n ON nr.id = n.article_id   -- JOIN 2: Link sentiment scores to news_raw
    GROUP BY
        s.date, s.open_price, s.close_price, s.volume
    ORDER BY
        s.date;
    """
    
    data = pd.DataFrame()

    try:
        logging.info("Executing SQL query to fetch dashboard data...")
        data = pd.read_sql(SQL_QUERY, conn)
        logging.info(f"Successfully fetched {len(data)} records.")
        
        # Ensure 'date' is a proper datetime object for plotting
        data['date'] = pd.to_datetime(data['date'])
        
    except Exception as e:
        logging.error(f"Error executing SQL query or processing data: {e}")
    finally:
        # Always close the connection
        if conn:
            conn.close()
            logging.info("Database connection closed.")
            
    return data