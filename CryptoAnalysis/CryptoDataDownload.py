
import pandas as pd
import numpy as np
import scipy
import sklearn
import requests
import os
from dotenv import load_dotenv

# Load the variables from the .env file into the system environment
load_dotenv()

# Retrieve your specific key safely
API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')

# Safety check to make sure it loaded correctly
if not API_KEY:
    raise ValueError("No API key found. Please check your .env file.")

print("Successfully loaded the API key!")

symbol = 'BITW'

print(f"Requesting weekly data for {symbol} from Alpha Vantage...")

# Set up the API URL for the Weekly Time Series endpoint
url = f'https://www.alphavantage.co/query?function=TIME_SERIES_WEEKLY&symbol={symbol}&apikey={API_KEY}'

# Fetch the data
response = requests.get(url)
data = response.json()

# Extract the weekly data dictionary from the JSON response
weekly_data = data.get('Weekly Time Series', {})

# Safety check: ensure the API didn't return an error (like an invalid key or rate limit)
if not weekly_data:
    print("Error: Could not retrieve data. Check your API key or current rate limits.")
    print("API Response:", data)
else:
    # Convert the raw JSON data into a clean Pandas DataFrame
    df = pd.DataFrame.from_dict(weekly_data, orient='index')
    
    # Convert the dates in the index to actual datetime objects
    df.index = pd.to_datetime(df.index)
    
    # Clean up the column names provided by the API
    df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    
    # Convert all the string values into numbers
    df = df.astype(float)
    
    # Sort chronologically (oldest to newest)
    df = df.sort_index()

    # Filter the data to match your requested date range
    start_date = '2016-02-19'
    end_date = '2026-02-13'
    
    # Create a mask to only keep rows within our date window
    mask = (df.index >= start_date) & (df.index <= end_date)
    filtered_df = df.loc[mask]

    # Print the results to verify
    print("\n--- First 5 Weeks ---")
    print(filtered_df.head())
    print("\n--- Last 5 Weeks ---")
    print(filtered_df.tail())

    # Save the data to a CSV
    filename = f"{symbol}_weekly_data.csv"
    filtered_df.to_csv(filename)
    print(f"\nSuccess! Data saved to '{filename}'.")


