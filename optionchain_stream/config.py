import os

class Config:
    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))

    # ClickHouse
    CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
    CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', 9000))
    CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
    CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')
    CLICKHOUSE_DB = os.getenv('CLICKHOUSE_DB', 'default')

    # AWS S3
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

    # Zerodha
    ZERODHA_API_KEY = os.getenv('ZERODHA_API_KEY')
    ZERODHA_ACCESS_TOKEN = os.getenv('ZERODHA_ACCESS_TOKEN')

    # Upstox
    UPSTOX_CLIENT_ID = os.getenv('UPSTOX_CLIENT_ID')
    UPSTOX_CLIENT_SECRET = os.getenv('UPSTOX_CLIENT_SECRET')
    UPSTOX_REDIRECT_URI = os.getenv('UPSTOX_REDIRECT_URI')
    UPSTOX_ACCESS_TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN')

    # Dhan
    DHAN_CLIENT_ID = os.getenv('DHAN_CLIENT_ID')
    DHAN_ACCESS_TOKEN = os.getenv('DHAN_ACCESS_TOKEN')

    # Fyers
    FYERS_CLIENT_ID = os.getenv('FYERS_CLIENT_ID')
    FYERS_ACCESS_TOKEN = os.getenv('FYERS_ACCESS_TOKEN')
