import pandas as pd

url = "https://images.dhan.co/api-data/api-scrip-master.csv"
df = pd.read_csv(url)
print(f"Unique Segments: {df['SEM_SEGMENT'].unique()}")
print(df.head())
