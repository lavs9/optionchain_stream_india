import websocket
import os
import ssl
import requests
import threading
import time

websocket.enableTrace(True)

def on_message(ws, message):
    print(f"Received message: {message}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"Closed: {close_status_code} {close_msg}")

def on_open(ws):
    print("Opened connection")

if __name__ == "__main__":
    access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
    if not access_token:
        print("UPSTOX_ACCESS_TOKEN not set")
        exit(1)

    # Step 1: Get Redirect URL
    url = "https://api.upstox.com/v3/feed/market-data-feed"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "*/*"
    }
    
    print(f"Requesting {url}...")
    response = requests.get(url, headers=headers, allow_redirects=False)
    
    if response.status_code == 302:
        ws_url = response.headers.get('Location')
        print(f"Redirected to: {ws_url}")
    else:
        print(f"Failed to get redirect. Status: {response.status_code}")
        print(response.text)
        exit(1)

    # Step 2: Connect to WS URL (NO AUTH HEADER)
    print(f"Connecting to {ws_url} without Auth header...")
    
    # Only Accept header? Or no headers?
    ws_headers = {
        "Accept": "*/*"
    }
    
    ws = websocket.WebSocketApp(
        ws_url,
        header=ws_headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
