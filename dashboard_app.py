import streamlit as st
import pandas as pd
# Import the function to retrieve data from your local PostgreSQL database
from dashboard_data import fetch_aggregated_data 

# --- Configure the Streamlit App ---
st.set_page_config(
    page_title="MSFT Financial Sentiment Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)

def format_sentiment(score):
    """Converts the numerical sentiment score into an actionable label and color."""
    if score > 0.3:
        return "HIGHLY POSITIVE", "green"
    elif score > 0.1:
        return "POSITIVE", "lightgreen"
    elif score < -0.3:
        return "HIGHLY NEGATIVE", "red"
    elif score < -0.1:
        return "NEGATIVE", "orange"
    else:
        return "NEUTRAL", "gray"

def main():
    """Main function to run the Streamlit dashboard."""
    
    st.title("📈 Stock Price & AI Sentiment Tracker")
    st.subheader("Daily Market Mood for MSFT (using Gemini Analysis)")

    # Fetch the aggregated data
    df = fetch_aggregated_data()

    if df.empty:
        st.error(
            """
            **Error:** Failed to load data from the database. 
            Please ensure PostgreSQL is running and the `pipeline.py` script ran successfully.
            """
        )
        # Stop execution if data is empty
        return

    # --- Data Processing for Display ---
    
    # Get the most recent trading day's data
    latest_data = df.iloc[-1]
    latest_score = latest_data['avg_sentiment_score']
    latest_price = latest_data['close_price']
    
    sentiment_label, sentiment_color = format_sentiment(latest_score)
    
    # --- 1. Key Metrics Section ---
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        label="Latest Trading Date",
        value=latest_data['date'].strftime('%Y-%m-%d')
    )
    col2.metric(
        label="Closing Price (USD)",
        value=f"${latest_price:.2f}",
        # Calculate daily price change (optional, requires prev day data)
        delta="N/A", 
        delta_color="off" 
    )
    col3.metric(
        label="Daily Sentiment Score",
        value=f"{latest_score:.4f}",
        delta=" ", # Placeholder for delta to show color
        delta_color="inverse" if latest_score < 0 else "normal"
    )
    col4.markdown(f"""
        <div style="background-color: {sentiment_color}; padding: 10px; border-radius: 5px; color: white; text-align: center;">
            **MARKET MOOD:**<br>
            **{sentiment_label}**
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    # --- 2. Charts Section ---
    
    # Chart 1: Stock Price vs. 7-Day Rolling Average
    st.header("Stock Price Trend")
    st.line_chart(
        df,
        x='date',
        y=['close_price', 'rolling_avg_7d'],
        use_container_width=True
    )
    
    # Chart 2: AI Sentiment Over Time
    st.header("AI Sentiment Trend")
    st.bar_chart(
        df,
        x='date',
        y='avg_sentiment_score',
        color='avg_sentiment_score', # Color bars based on score magnitude
        use_container_width=True
    )
    
    # --- 3. Raw Data Table ---
    st.header("Raw Aggregated Data")
    st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()