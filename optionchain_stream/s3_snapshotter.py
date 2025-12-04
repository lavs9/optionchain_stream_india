import boto3
import pandas as pd
import io
from datetime import datetime
from typing import List, Dict, Any, Union
from optionchain_stream.models import Tick
from dataclasses import asdict

class S3Snapshotter:
    def __init__(self, bucket_name: str, aws_access_key_id: str, aws_secret_access_key: str, region_name: str):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )

    def snapshot(self, data: List[Union[Tick, Dict[str, Any]]], prefix: str = "option_chain_snapshots"):
        """
        Convert data to parquet and upload to S3.
        Accepts List of Tick objects or Dictionaries.
        """
        if not data:
            return None

        # Convert Ticks to dicts if necessary
        processed_data = []
        for item in data:
            if isinstance(item, Tick):
                processed_data.append(asdict(item))
            else:
                processed_data.append(item)

        df = pd.DataFrame(processed_data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"{prefix}/snapshot_{timestamp}.parquet"
        
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        buffer.seek(0)
        
        self.s3_client.upload_fileobj(buffer, self.bucket_name, file_name)
        return file_name
