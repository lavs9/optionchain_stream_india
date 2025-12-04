import dhanhq
import inspect

print("DhanHQ Dir:")
print(dir(dhanhq))

# Check for main client class
if hasattr(dhanhq, 'dhanhq'):
    print("\ndhanhq class found")
    print(dir(dhanhq.dhanhq))

# Check for WebSocket classes
print("\nChecking for WebSocket classes...")
for name, obj in inspect.getmembers(dhanhq):
    if inspect.isclass(obj):
        print(f"Class: {name}")
        if 'Feed' in name or 'Socket' in name:
            print(f"Potential WebSocket Class: {name}")
            print(dir(obj))
