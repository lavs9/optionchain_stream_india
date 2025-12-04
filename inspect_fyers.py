import fyers_apiv3
import inspect

print("Fyers API v3 Dir:")
print(dir(fyers_apiv3))

# Check for main client class
if hasattr(fyers_apiv3, 'fyersModel'):
    print("\nfyersModel class found")
    # print(dir(fyers_apiv3.fyersModel)) # Might be too verbose

# Check for WebSocket classes
print("\nChecking for WebSocket classes...")
for name, obj in inspect.getmembers(fyers_apiv3):
    if inspect.isclass(obj):
        print(f"Class: {name}")
        if 'Socket' in name or 'Data' in name:
            print(f"Potential WebSocket Class: {name}")
            print(dir(obj))
