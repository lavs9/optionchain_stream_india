import pandas as pd

url = "https://public.fyers.in/sym_details/NSE_FO.csv"
# Fyers CSVs usually don't have headers, so we might need to infer or check docs.
# Let's read first few lines without header.
df = pd.read_csv(url, nrows=1, header=None)
for col in df.columns:
    print(f"Column {col}: {df.iloc[0][col]}")
