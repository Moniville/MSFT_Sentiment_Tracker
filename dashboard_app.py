import streamlit as st
import pandas as pd
import plotly.express as px
from dashboard_data import get_daily_sentiment_df # Imports the function we just corrected!

# --- Configure the Streamlit App ---
st.set_page_config(
    page_title="Financial Sentiment Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Define Helper Functions ---

@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data():
    """Loads and returns the aggregated DataFrame from the database."""
    return get_daily_sentiment_df()

def style_header(text):
    """Returns styled header markdown."""
    return f'<h1 style="color:#007bff; text-align:center;">{text}</h1>'

# --- Main App Execution ---

# 1. Load Data
df = load_data()

if df.empty:
    st.error("No data fetched. Please run 'python pipeline.py' to ingest data and ensure your database connection is active.")
    st.stop()

# Get the latest data points
latest_price = df['close_price'].iloc[-1]
latest_sentiment = df['average_sentiment_score'].iloc[-1]

# --- UI Layout ---

st.markdown(style_header("Stock Price & Sentiment Correlation"), unsafe_allow_html=True)
st.markdown("Analyzing how average daily news sentiment tracks with the closing stock price for Microsoft (MSFT).")

# Metrics for the Latest Run
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Latest Closing Price (MSFT)", 
        value=f"${latest_price:.2f}",
        delta=None # Change calculation is complex without more history
    )

with col2:
    sentiment_delta = f"{latest_sentiment:.2f}"
    sentiment_color = 'off'
    if latest_sentiment > 0.2:
        sentiment_color = 'inverse' # Green color for positive sentiment
    elif latest_sentiment < -0.2:
        sentiment_color = 'normal' # Red color for negative sentiment
        
    st.metric(
        label="Latest Average Sentiment Score", 
        value=sentiment_delta, 
        delta_color=sentiment_color
    )

with col3:
    st.metric(
        label="Data Points Collected", 
        value=f"{len(df)} days of data"
    )

st.markdown("---")

# --- Interactive Plotly Chart ---

# Create a combined chart: Stock Price on primary Y-axis, Sentiment on secondary Y-axis
fig = px.line(df, x='ts_date', y='close_price', title='MSFT Price and Daily Sentiment Trend Over Time')

# Add the sentiment score as a bar chart (or line, but bar better visualizes daily impact)
# Use a custom color scale for sentiment bars (Green for positive, Red for negative)
sentiment_colors = ['#EF553B' if score < 0 else '#636EFB' for score in df['average_sentiment_score']]

fig.add_bar(
    x=df['ts_date'], 
    y=df['average_sentiment_score'], 
    name='Daily Sentiment Score',
    marker_color=sentiment_colors,
    yaxis='y2', # Use the secondary Y-axis
    opacity=0.6
)

# Configure primary Y-axis (Price)
fig.update_layout(
    yaxis=dict(
        title="Stock Price ($)",
        showgrid=True,
        linecolor="#007bff"
    ),
    # Configure secondary Y-axis (Sentiment)
    yaxis2=dict(
        title="Avg. Sentiment Score (-1.0 to 1.0)",
        overlaying='y',
        side='right',
        range=[-1.0, 1.0],
        showgrid=False,
        linecolor="#ff9900"
    ),
    # General layout settings
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    ),
    hovermode="x unified",
    template="plotly_white",
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# --- Display Raw Data for Validation ---
st.subheader("Raw Aggregated Data")
st.dataframe(df, use_container_width=True)