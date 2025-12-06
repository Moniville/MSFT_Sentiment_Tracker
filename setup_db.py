import psycopg2
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_tables():
    """
    Establishes a connection, drops existing tables to ensure a clean slate, 
    and then creates the necessary database tables.
    """
    conn = None
    try:
        logging.info("Attempting to connect to PostgreSQL for table creation...")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # --- CLEANUP (ENSURE TABLES ARE DROPPED IN CORRECT ORDER) ---
        # news_sentiment depends on news_raw, so drop sentiment first
        cur.execute("DROP TABLE IF EXISTS news_sentiment CASCADE;")
        cur.execute("DROP TABLE IF EXISTS news_raw CASCADE;")
        cur.execute("DROP TABLE IF EXISTS stock_prices CASCADE;")
        
        # --- TABLE CREATION ---

        # 1. Table for Stock Prices (Fact Table)
        cur.execute("""
            CREATE TABLE stock_prices (
                date DATE PRIMARY KEY,
                open_price FLOAT,
                close_price FLOAT,
                high_price FLOAT,
                low_price FLOAT,
                volume BIGINT
            );
        """)

        # 2. Table for Raw News Articles (Parent table for FK)
        cur.execute("""
            CREATE TABLE news_raw (
                id SERIAL PRIMARY KEY,
                title TEXT,
                date_published DATE,
                source TEXT,
                url TEXT UNIQUE
            );
        """)

        # 3. Table for AI Sentiment Analysis (Child table with FK)
        cur.execute("""
            CREATE TABLE news_sentiment (
                article_id INTEGER PRIMARY KEY,
                sentiment_score FLOAT, 
                sentiment_label VARCHAR(20), 
                theme TEXT,
                analysis_time TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES news_raw (id)
            );
        """)

        conn.commit()
        logging.info("✅ Database tables successfully dropped and recreated.")
        cur.close()

    except psycopg2.Error as e:
        logging.error(f"FATAL ERROR during table creation: {e}")
        if conn:
            conn.rollback() 
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed after setup.")


if __name__ == '__main__':
    create_tables()