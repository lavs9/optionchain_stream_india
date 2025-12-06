# Streamlit Demo - Option Chain Streaming

A comprehensive web-based demo application to showcase and test real-time option chain streaming with multi-broker support.

## 🎯 Features

- **Multi-Broker Support**: Switch between Dhan, Upstox, and Fyers brokers
- **Real-Time Option Chain Display**: Live updates with color-coded ITM/OTM highlighting
- **Interactive Visualizations**: Premium vs Strike, Volume Distribution, OI buildup, IV Smile
- **Streaming Dashboard**: Connection status, tick counter, spot price, PCR
- **Test Environment**: Easy-to-use controls for testing different configurations

## 🚀 Quick Start

### Prerequisites

1. **Install dependencies**:
   ```bash
   cd /Users/mayanklavania/moonshot_projects/optionchain_stream_india
   pip install -r requirements.txt
   ```

2. **Set environment variables** for your broker:

   **For Dhan**:
   ```bash
   export DHAN_CLIENT_ID="your_client_id"
   export DHAN_ACCESS_TOKEN="your_access_token"
   ```

   **For Upstox**:
   ```bash
   export UPSTOX_CLIENT_ID="your_client_id"
   export UPSTOX_CLIENT_SECRET="your_client_secret"
   export UPSTOX_ACCESS_TOKEN="your_access_token"
   ```

   **For Fyers**:
   ```bash
   export FYERS_CLIENT_ID="your_client_id"
   export FYERS_ACCESS_TOKEN="your_access_token"
   ```

### Running the Demo

```bash
streamlit run streamlit_demo.py
```

The application will open in your default browser at `http://localhost:8501`

## 📖 Usage Guide

### 1. Configure Settings (Sidebar)

**Broker Settings**:
- Select your broker (Dhan, Upstox, or Fyers)
- Credentials are automatically loaded from environment variables

**Market Settings**:
- Choose symbol: NIFTY or BANKNIFTY
- Expiry dates are auto-populated from available contracts

**Streaming Settings**:
- **Option Chain Polling**: Fetches full option chain snapshot (recommended for demo)
- **Real-time Streaming**: WebSocket-based live tick updates (advanced)

**Refresh Interval**:
- Control how often the display updates (1-10 seconds)

### 2. Start Streaming

1. Click **🚀 Start** button
2. Wait for broker connection
3. Select expiry date from dropdown
4. View option chain data in table and charts

### 3. Explore Data

**Option Chain Tab** (`📋 Option Chain`):
- Full option chain with Calls and Puts
- Columns: Strike, CE/PE LTP, OI, Volume, IV
- ATM strikes highlighted in yellow
- Sortable and searchable

**Analytics Tab** (`📈 Analytics`):
- **Premium vs Strike**: Visual representation of option prices
- **Volume Distribution**: Call vs Put volume by strike
- **Open Interest**: OI buildup analysis
- **IV Smile**: Implied volatility curve

### 4. Control Panel

- **🔄 Refresh**: Manually refresh data
- **🛑 Stop**: Disconnect and reset
- **Auto-refresh**: Toggle automatic updates

## 📊 Example Screenshots

### Main Dashboard
The main interface shows:
- Connection status (broker, symbol, last update)
- Spot price and PCR metrics
- Option chain table with color-coded strikes
- Interactive charts

### Option Chain Table
- **Green cells**: In-the-money (ITM)
- **Yellow cells**: At-the-money (ATM)
- **White cells**: Out-of-the-money (OTM)

### Analytics Charts
1. **Premium vs Strike**: See how premiums decay with distance from spot
2. **Volume Distribution**: Identify high-activity strikes
3. **Open Interest**: Detect support/resistance levels
4. **IV Smile**: Analyze volatility skew

## 🔧 Technical Details

### Architecture

```
┌─────────────────────────────────────┐
│     Streamlit Web Interface         │
│  (Auto-refresh every 1-2 seconds)   │
└────────────┬────────────────────────┘
             │
    ┌────────▼────────┐
    │  StreamingDemo  │
    │     Class       │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │   Broker Layer  │
    │ (Dhan/Upstox/   │
    │     Fyers)      │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │  Market Data    │
    │   (REST API /   │
    │   WebSocket)    │
    └─────────────────┘
```

### Data Flow

1. **Initialization**: User selects broker and symbol
2. **Fetch Expiries**: Application queries available expiry dates
3. **Option Chain Polling**: 
   - Calls `broker.fetch_option_chain(symbol, expiry)`
   - Receives full option chain snapshot
   - Formats data into pandas DataFrame
   - Renders table and charts
4. **Auto-Refresh**: Streamlit reruns every N seconds to fetch latest data

### Threading Model

- **Main Thread**: Streamlit UI rendering
- **Background Thread** (streaming mode): WebSocket connection
- **Queue**: Thread-safe communication between broker and UI

## 🐛 Troubleshooting

### Issue: "Missing credentials" error

**Solution**: Make sure you've set the environment variables correctly:
```bash
# Check if variables are set
echo $DHAN_CLIENT_ID
echo $DHAN_ACCESS_TOKEN

# Set them if missing
export DHAN_CLIENT_ID="your_client_id"
export DHAN_ACCESS_TOKEN="your_access_token"
```

### Issue: "No expiry dates found"

**Possible causes**:
1. Broker credentials are invalid
2. Symbol name doesn't match broker's format
3. Network connectivity issues

**Solution**:
- Verify credentials with broker's web portal
- Check network connection
- Try different symbol (NIFTY vs BANKNIFTY)

### Issue: "Failed to fetch option chain data"

**Solutions**:
1. Check if your broker subscription includes option chain API access
2. Verify expiry date is valid (not expired)
3. Check broker API rate limits
4. Review application logs for detailed error messages

### Issue: UI not updating

**Solutions**:
- Enable "Auto-refresh" checkbox
- Manually click "🔄 Refresh" button
- Check browser console for errors
- Restart Streamlit server

## 🎨 Customization

### Change Default Symbol
Edit `streamlit_demo.py`:
```python
symbol = st.sidebar.selectbox(
    "Symbol",
    ["NIFTY", "BANKNIFTY", "FINNIFTY"],  # Add more symbols
    index=0
)
```

### Adjust Refresh Interval
```python
refresh_interval = st.sidebar.slider(
    "Refresh Interval (seconds)",
    min_value=1,
    max_value=30,  # Increase max
    value=5,  # Change default
)
```

### Add More Brokers
Implement broker interface and add to dropdown:
```python
broker_name = st.sidebar.selectbox(
    "Select Broker",
    ["Dhan", "Upstox", "Fyers", "Zerodha"],  # Add new broker
    index=0
)
```

## 📝 Notes

- **Option Chain Polling** is recommended for stable demo experience
- **Real-time Streaming** requires more complex setup (WebSocket handling)
- Data refresh frequency depends on broker API rate limits
- Some brokers may require paid subscriptions for WebSocket access

## 🔗 Related Documentation

- [Multi-Broker Setup Guide](multi_broker_setup.md)
- [Main README](../README.md)
- [Broker Testing Summary](broker_testing.md)


## ☁️ Streamlit Cloud Deployment

Deploy the demo to Streamlit Community Cloud for free!

### Step 1: Prepare Repository

1. **Fork this repository** to your GitHub account

2. **Ensure files are committed**:
   - `streamlit_demo.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `.streamlit/secrets.toml.example` (template only)

3. **Verify `.gitignore`** includes:
   ```
   .streamlit/secrets.toml
   ```

### Step 2: Deploy to Streamlit Cloud

1. **Visit** [share.streamlit.io](https://share.streamlit.io)

2. **Sign in** with your GitHub account

3. **Click "New app"**

4. **Configure deployment**:
   - Repository: `your-username/optionchain_stream_india`
   - Branch: `main` (or your branch name)
   - Main file path: `streamlit_demo.py`
   - App URL: Choose a custom URL (e.g., `your-app-name.streamlit.app`)

5. **Click "Deploy"** (app will start building)

### Step 3: Configure Secrets

1. **Navigate to app settings** (gear icon in Streamlit Cloud dashboard)

2. **Open "Secrets" tab**

3. **Add your credentials** in TOML format:

   ```toml
   # For Dhan broker
   [dhan]
   client_id = "your_actual_dhan_client_id"
   access_token = "your_actual_dhan_access_token"
   
   # For Upstox broker (if using)
   [upstox]
   client_id = "your_actual_upstox_client_id"
   client_secret = "your_actual_upstox_client_secret"
   access_token = "your_actual_upstox_access_token"
   
   # For Fyers broker (if using)
   [fyers]
   client_id = "your_actual_fyers_client_id"
   access_token = "your_actual_fyers_access_token"
   ```

4. **Click "Save"**

5. **App will reboot automatically** with credentials loaded

### Step 4: Test Deployment

1. **Open your app** at `https://your-app-name.streamlit.app`

2. **Select broker** from sidebar (credentials should be loaded automatically)

3. **Click "Start"** to connect

4. **Verify** option chain data displays correctly

### Troubleshooting Deployment

**Issue: App won't start**
- Check deployment logs in Streamlit Cloud dashboard
- Verify `requirements.txt` has all dependencies
- Ensure `streamlit_demo.py` is in repository root

**Issue: "Missing credentials" error**
- Verify secrets are saved in correct TOML format
- Check spelling of secret keys matches expected names
- Ensure no extra spaces or quotes in secret values

**Issue: Import errors**
- Add missing packages to `requirements.txt`
- Redeploy after updating requirements

**Resource Links:**
- [Streamlit Cloud Docs](https://docs.streamlit.io/streamlit-community-cloud)
- [Secrets Management](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management)

## 💡 Tips


1. **For Testing**: Use Option Chain Polling mode with 2-second refresh
2. **For Analysis**: Export data from table view for offline analysis
3. **For Performance**: Reduce refresh interval if experiencing lag
4. **For Multiple Symbols**: Open multiple browser tabs with different symbols

---

**Built with ❤️ for the Indian algo trading community**
