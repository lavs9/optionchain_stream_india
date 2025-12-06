"""
Streamlit Demo for Option Chain Streaming

A comprehensive web-based demo application to showcase and test 
real-time option chain streaming with multi-broker support.

Features:
- Multi-broker support (Dhan, Upstox, Fyers)
- Real-time option chain display
- Interactive visualizations (IV smile, volume, OI)
- Live streaming dashboard
- Testing environment with controls

Usage:
    export DHAN_CLIENT_ID="your_client_id"
    export DHAN_ACCESS_TOKEN="your_access_token"
    streamlit run streamlit_demo.py
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime
from queue import Queue, Empty
from typing import Dict, List, Any, Optional

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from optionchain_stream.brokers.dhan_broker import DhanBroker
from optionchain_stream.brokers.upstox_broker import UpstoxBroker
from optionchain_stream.brokers.fyers_broker import FyersBroker
from optionchain_stream.models import Tick

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Option Chain Streaming Demo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .option-chain-header {
        background: linear-gradient(90deg, #1f77b4 0%, #2ca02c 100%);
        color: white;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .status-connected {
        color: #28a745;
        font-weight: bold;
    }
    .status-disconnected {
        color: #dc3545;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)


class StreamingDemo:
    """Handles broker connection and data streaming for Streamlit demo"""
    
    def __init__(self):
        self.broker = None
        self.tick_queue = Queue(maxsize=1000)
        self.option_chain_data = {}
        self.tick_count = 0
        self.last_update = None
        self.streaming_thread = None
        self.is_streaming = False
        self.spot_price = 0.0
        
    def initialize_broker(self, broker_name: str, credentials: Dict[str, str]) -> bool:
        """Initialize the selected broker"""
        try:
            if broker_name == "Dhan":
                self.broker = DhanBroker(
                    client_id=credentials['client_id'],
                    access_token=credentials['access_token']
                )
            elif broker_name == "Upstox":
                self.broker = UpstoxBroker(
                    client_id=credentials['client_id'],
                    client_secret=credentials['client_secret'],
                    redirect_uri=credentials.get('redirect_uri', 'http://localhost'),
                    access_token=credentials['access_token']
                )
            elif broker_name == "Fyers":
                self.broker = FyersBroker(
                    client_id=credentials['client_id'],
                    access_token=credentials['access_token']
                )
            else:
                return False
            
            logger.info(f"Successfully initialized {broker_name} broker")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing broker: {e}")
            st.error(f"Failed to initialize broker: {str(e)}")
            return False
    
    def fetch_option_chain(self, symbol: str, expiry: str) -> Dict[str, Any]:
        """Fetch option chain data"""
        if not self.broker:
            return {}
        
        try:
            data = self.broker.fetch_option_chain(symbol, expiry)
            self.last_update = datetime.now()
            return data
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return {}
    
    def start_streaming(self, tokens: List[str]):
        """Start real-time streaming in background thread"""
        if self.is_streaming:
            return
        
        def stream_worker():
            try:
                self.broker.on_tick(self._on_tick)
                self.broker.subscribe(tokens, mode="full")
                self.broker.connect()
            except Exception as e:
                logger.error(f"Streaming error: {e}")
        
        self.is_streaming = True
        self.streaming_thread = threading.Thread(target=stream_worker, daemon=True)
        self.streaming_thread.start()
        logger.info("Started streaming thread")
    
    def _on_tick(self, ticks: List[Tick]):
        """Callback for incoming ticks"""
        for tick in ticks:
            try:
                self.tick_queue.put_nowait({
                    'token': tick.token,
                    'ltp': tick.last_price,
                    'volume': tick.volume,
                    'oi': tick.oi,
                    'timestamp': tick.timestamp
                })
                self.tick_count += 1
            except:
                pass  # Queue full, skip tick
        
        self.last_update = datetime.now()
    
    def get_available_expiries(self, symbol: str) -> List[str]:
        """Get available expiry dates for symbol"""
        if not self.broker:
            return []
        
        try:
            provider = self.broker.get_instrument_provider()
            instruments = provider.fetch_instruments()
            
            expiries = set()
            for inst in instruments:
                if symbol in inst.symbol and inst.instrument_type in ["CE", "PE", "OPTIDX"] and inst.expiry:
                    expiries.add(inst.expiry.strftime("%Y-%m-%d"))
            
            return sorted(list(expiries))
        except Exception as e:
            logger.error(f"Error fetching expiries: {e}")
            return []


def render_sidebar() -> Dict[str, Any]:
    """Render sidebar configuration panel"""
    st.sidebar.title("⚙️ Configuration")
    
    # Broker selection
    st.sidebar.subheader("Broker Settings")
    broker_name = st.sidebar.selectbox(
        "Select Broker",
        ["Dhan", "Upstox", "Fyers"],
        index=0
    )
    
    # Credential input mode
    st.sidebar.markdown("**Credentials**")
    cred_mode = st.sidebar.radio(
        "Input Method",
        ["Enter Manually", "Use Environment/Secrets"],
        index=0,
        help="Choose how to provide broker credentials"
    )
    
    credentials = {}
    
    if cred_mode == "Enter Manually":
        # Manual credential input
        st.sidebar.markdown("*Enter your credentials below:*")
        
        if broker_name == "Dhan":
            credentials['client_id'] = st.sidebar.text_input(
                "Client ID",
                value="",
                type="default",
                key="dhan_client_id"
            )
            credentials['access_token'] = st.sidebar.text_input(
                "Access Token",
                value="",
                type="password",
                key="dhan_access_token"
            )
        elif broker_name == "Upstox":
            credentials['client_id'] = st.sidebar.text_input(
                "Client ID",
                value="",
                type="default",
                key="upstox_client_id"
            )
            credentials['client_secret'] = st.sidebar.text_input(
                "Client Secret",
                value="",
                type="password",
                key="upstox_client_secret"
            )
            credentials['access_token'] = st.sidebar.text_input(
                "Access Token",
                value="",
                type="password",
                key="upstox_access_token"
            )
        elif broker_name == "Fyers":
            credentials['client_id'] = st.sidebar.text_input(
                "Client ID",
                value="",
                type="default",
                key="fyers_client_id"
            )
            credentials['access_token'] = st.sidebar.text_input(
                "Access Token",
                value="",
                type="password",
                key="fyers_access_token"
            )
    else:
        # Use environment variables or Streamlit secrets
        def get_credential(key: str, secret_path: List[str]) -> str:
            """Get credential from environment variable or Streamlit secrets"""
            # Try environment variable first
            env_value = os.getenv(key, '')
            if env_value:
                return env_value
            
            # Try Streamlit secrets (for cloud deployment)
            try:
                if hasattr(st, 'secrets'):
                    value = st.secrets
                    for path_item in secret_path:
                        value = value.get(path_item, {})
                        if isinstance(value, str):
                            return value
                    return value if isinstance(value, str) else ''
            except:
                pass
            
            return ''
        
        if broker_name == "Dhan":
            credentials['client_id'] = get_credential('DHAN_CLIENT_ID', ['dhan', 'client_id'])
            credentials['access_token'] = get_credential('DHAN_ACCESS_TOKEN', ['dhan', 'access_token'])
        elif broker_name == "Upstox":
            credentials['client_id'] = get_credential('UPSTOX_CLIENT_ID', ['upstox', 'client_id'])
            credentials['client_secret'] = get_credential('UPSTOX_CLIENT_SECRET', ['upstox', 'client_secret'])
            credentials['access_token'] = get_credential('UPSTOX_ACCESS_TOKEN', ['upstox', 'access_token'])
        elif broker_name == "Fyers":
            credentials['client_id'] = get_credential('FYERS_CLIENT_ID', ['fyers', 'client_id'])
            credentials['access_token'] = get_credential('FYERS_ACCESS_TOKEN', ['fyers', 'access_token'])
    
    # Check credentials
    has_credentials = all(credentials.values())
    if not has_credentials and cred_mode == "Use Environment/Secrets":
        st.sidebar.warning(f"⚠️ No credentials found in environment/secrets")
    
    # Symbol selection
    st.sidebar.subheader("Market Settings")
    symbol = st.sidebar.selectbox(
        "Symbol",
        ["NIFTY", "BANKNIFTY"],
        index=0
    )
    
    # Refresh interval
    refresh_interval = st.sidebar.slider(
        "Refresh Interval (seconds)",
        min_value=1,
        max_value=10,
        value=2,
        help="How often to update the display"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📖 Instructions")
    st.sidebar.markdown("""
    1. Enter broker credentials or use env/secrets
    2. Click **Connect** to test connection
    3. Select symbol and expiry
    4. Click **Stream Option Chain** to begin
    """)
    
    return {
        'broker_name': broker_name,
        'credentials': credentials,
        'symbol': symbol,
        'refresh_interval': refresh_interval,
        'has_credentials': has_credentials
    }


def format_option_chain_table(option_chain_data: Dict[str, Any]) -> pd.DataFrame:
    """Convert option chain data to DataFrame for display"""
    if not option_chain_data or 'data' not in option_chain_data:
        return pd.DataFrame()
    
    data = option_chain_data['data']
    if not isinstance(data, list) or len(data) == 0:
        return pd.DataFrame()
    
    # Group by strike price
    strikes = {}
    for item in data:
        strike = item.get('strike_price', 0)
        option_type = item.get('option_type', 'XX')
        
        if strike not in strikes:
            strikes[strike] = {'strike': strike, 'CE': {}, 'PE': {}}
        
        strikes[strike][option_type] = {
            'ltp': item.get('ltp', 0),
            'oi': item.get('oi', 0),
            'volume': item.get('volume', 0),
            'iv': item.get('option_greeks', {}).get('iv', 0) if 'option_greeks' in item else 0,
        }
    
    # Convert to DataFrame
    rows = []
    for strike, data in sorted(strikes.items()):
        ce = data.get('CE', {})
        pe = data.get('PE', {})
        
        rows.append({
            'Strike': strike,
            'CE_LTP': ce.get('ltp', 0),
            'CE_OI': ce.get('oi', 0),
            'CE_Vol': ce.get('volume', 0),
            'CE_IV': ce.get('iv', 0),
            'PE_IV': pe.get('iv', 0),
            'PE_Vol': pe.get('volume', 0),
            'PE_OI': pe.get('oi', 0),
            'PE_LTP': pe.get('ltp', 0),
        })
    
    return pd.DataFrame(rows)


def render_option_chain_table(df: pd.DataFrame, spot_price: float = 0):
    """Render option chain table with styling"""
    if df.empty:
        st.warning("No option chain data available")
        return
    
    # Apply styling
    def highlight_atm(row):
        """Highlight ATM strike"""
        if spot_price == 0:
            return [''] * len(row)
        
        strike = row['Strike']
        if abs(strike - spot_price) < 100:  # Within 100 points of spot
            return ['background-color: #ffffcc'] * len(row)
        return [''] * len(row)
    
    # Format numbers
    formatted_df = df.copy()
    formatted_df['CE_LTP'] = formatted_df['CE_LTP'].apply(lambda x: f"{x:.2f}")
    formatted_df['PE_LTP'] = formatted_df['PE_LTP'].apply(lambda x: f"{x:.2f}")
    formatted_df['CE_IV'] = formatted_df['CE_IV'].apply(lambda x: f"{x:.2f}%" if x > 0 else "-")
    formatted_df['PE_IV'] = formatted_df['PE_IV'].apply(lambda x: f"{x:.2f}%" if x > 0 else "-")
    
    # Display
    st.dataframe(
        formatted_df.style.apply(highlight_atm, axis=1),
        use_container_width=True,
        height=600
    )


def render_visualizations(df: pd.DataFrame):
    """Render interactive visualizations"""
    if df.empty:
        return
    
    # Create subplot with 2 rows, 2 columns
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Premium vs Strike", "Volume Distribution", 
                       "Open Interest", "IV Smile"),
        specs=[[{"type": "scatter"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # 1. Premium vs Strike
    fig.add_trace(
        go.Scatter(x=df['Strike'], y=df['CE_LTP'], 
                  mode='lines+markers', name='Call Premium',
                  line=dict(color='green')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=df['Strike'], y=df['PE_LTP'], 
                  mode='lines+markers', name='Put Premium',
                  line=dict(color='red')),
        row=1, col=1
    )
    
    # 2. Volume Distribution
    fig.add_trace(
        go.Bar(x=df['Strike'], y=df['CE_Vol'], name='Call Volume',
              marker_color='lightgreen'),
        row=1, col=2
    )
    fig.add_trace(
        go.Bar(x=df['Strike'], y=df['PE_Vol'], name='Put Volume',
              marker_color='lightcoral'),
        row=1, col=2
    )
    
    # 3. Open Interest
    fig.add_trace(
        go.Bar(x=df['Strike'], y=df['CE_OI'], name='Call OI',
              marker_color='green'),
        row=2, col=1
    )
    fig.add_trace(
        go.Bar(x=df['Strike'], y=df['PE_OI'], name='Put OI',
              marker_color='red'),
        row=2, col=1
    )
    
    # 4. IV Smile (filter out zeros)
    df_iv = df[df['CE_IV'] != '-'].copy()
    if not df_iv.empty:
        try:
            df_iv['CE_IV_num'] = df_iv['CE_IV'].str.rstrip('%').astype(float)
            df_iv['PE_IV_num'] = df_iv['PE_IV'].str.rstrip('%').astype(float)
            
            fig.add_trace(
                go.Scatter(x=df_iv['Strike'], y=df_iv['CE_IV_num'], 
                          mode='lines+markers', name='Call IV',
                          line=dict(color='blue')),
                row=2, col=2
            )
            fig.add_trace(
                go.Scatter(x=df_iv['Strike'], y=df_iv['PE_IV_num'], 
                          mode='lines+markers', name='Put IV',
                          line=dict(color='orange')),
                row=2, col=2
            )
        except:
            pass
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        title_text="Option Chain Analytics"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def main():
    """Main Streamlit application"""
    
    # Header
    st.markdown('<div class="option-chain-header">📊 Option Chain Streaming Demo</div>', 
                unsafe_allow_html=True)
    
    # Initialize session state
    if 'demo' not in st.session_state:
        st.session_state.demo = StreamingDemo()
        st.session_state.started = False
        st.session_state.expiry = None
    
    # Render sidebar and get config
    config = render_sidebar()
    
    # Initialize session state for connection
    if 'connected' not in st.session_state:
        st.session_state.connected = False
    if 'streaming' not in st.session_state:
        st.session_state.streaming = False
    
    # Main control buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Connect button - always show if not connected
        if not st.session_state.connected:
            if config['has_credentials']:
                if st.button("🔌 Connect", type="primary", use_container_width=True):
                    with st.spinner("Testing connection..."):
                        success = st.session_state.demo.initialize_broker(
                            config['broker_name'],
                            config['credentials']
                        )
                        if success:
                            st.session_state.connected = True
                            st.session_state.started = True
                            st.success("✅ Connection successful!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Connection failed. Check your credentials.")
            else:
                st.button("🔌 Connect", disabled=True, use_container_width=True)
                st.caption("Enter credentials first")
        else:
            # Show disconnect button when connected
            if st.button("🔌 Disconnect", type="secondary", use_container_width=True):
                st.session_state.connected = False
                st.session_state.streaming = False
                st.session_state.started = False
                st.session_state.demo = StreamingDemo()
                st.rerun()
    
    with col2:
        # Stream button - only show when connected
        if st.session_state.connected and not st.session_state.streaming:
            if st.button("📊 Stream Option Chain", type="primary", use_container_width=True):
                st.session_state.streaming = True
                st.rerun()
        elif st.session_state.streaming:
            if st.button("⏸️ Stop Streaming", use_container_width=True):
                st.session_state.streaming = False
                st.rerun()
        else:
            st.button("📊 Stream Option Chain", disabled=True, use_container_width=True)
            if not st.session_state.connected:
                st.caption("Connect first")
    
    with col3:
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=True, 
                                   disabled=not st.session_state.streaming)
    
    # Display connection status
    st.markdown("---")
    status_col1, status_col2, status_col3, status_col4 = st.columns(4)
    
    with status_col1:
        if st.session_state.connected:
            st.metric("Connection", "🟢 Connected")
        else:
            st.metric("Connection", "🔴 Disconnected")
    
    with status_col2:
        if st.session_state.connected:
            st.metric("Broker", config['broker_name'])
        else:
            st.metric("Broker", "-")
    
    with status_col3:
        if st.session_state.streaming:
            st.metric("Streaming", "🔴 Live")
        else:
            st.metric("Streaming", "⚪ Idle")
    
    with status_col4:
        last_update = st.session_state.demo.last_update
        if last_update:
            st.metric("Last Update", last_update.strftime("%H:%M:%S"))
        else:
            st.metric("Last Update", "-")
    
    # Show option chain interface only when connected
    if st.session_state.connected:
        # Get available expiries
        if not st.session_state.expiry:
            with st.spinner("Fetching available expiries..."):
                expiries = st.session_state.demo.get_available_expiries(config['symbol'])
                if expiries:
                    st.session_state.expiry = expiries[0]
        
        # Symbol and Expiry selection
        st.markdown("---")
        select_col1, select_col2 = st.columns(2)
        
        with select_col1:
            st.metric("Selected Symbol", config['symbol'])
        
        with select_col2:
            if st.session_state.expiry:
                expiries = st.session_state.demo.get_available_expiries(config['symbol'])
                selected_expiry = st.selectbox(
                    "📅 Select Expiry Date",
                    expiries,
                    index=0 if st.session_state.expiry in expiries else 0
                )
                st.session_state.expiry = selected_expiry
        
        # Show option chain only when streaming
        if st.session_state.streaming and st.session_state.expiry:
            st.markdown("---")
            
            # Fetch and display option chain
            with st.spinner("Fetching option chain..."):
                option_chain = st.session_state.demo.fetch_option_chain(
                    config['symbol'],
                    st.session_state.expiry
                )
                
                if option_chain:
                    # Display metrics
                    met_col1, met_col2, met_col3, met_col4 = st.columns(4)
                    
                    with met_col1:
                        spot = option_chain.get('spot_price', 0)
                        st.metric("Spot Price", f"₹{spot:.2f}" if spot else "-")
                        st.session_state.demo.spot_price = spot
                    
                    with met_col2:
                        pcr = option_chain.get('pcr', 0)
                        st.metric("PCR", f"{pcr:.2f}" if pcr else "-")
                        
                        with met_col3:
                            data_count = len(option_chain.get('data', []))
                            st.metric("Contracts", data_count)
                        
                        with met_col4:
                            st.metric("Mode", "📊 Polling")
                        
                        # Convert to DataFrame and display
                        df = format_option_chain_table(option_chain)
                        
                        if not df.empty:
                            # Tabs for table and charts
                            tab1, tab2 = st.tabs(["📋 Option Chain", "📈 Analytics"])
                            
                            with tab1:
                                render_option_chain_table(df, st.session_state.demo.spot_price)
                            
                            with tab2:
                                render_visualizations(df)
                        else:
                            st.warning("No option chain data available")
                else:
                    st.error("Failed to fetch option chain data")
        elif st.session_state.connected and not st.session_state.streaming:
            st.info("👆 Click **Stream Option Chain** to start viewing data")
        else:
            st.warning(f"No expiry dates found for {config['symbol']}")
    
    else:
        st.info("👈 Enter credentials in the sidebar and click **Connect** to begin")
    
    # Auto-refresh
    if auto_refresh and st.session_state.started:
        time.sleep(config['refresh_interval'])
        st.rerun()


if __name__ == "__main__":
    main()
