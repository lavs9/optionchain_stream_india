from dhanhq import dhanhq
import inspect

# Check dhanhq class methods containing 'option'
print("dhanhq class methods containing 'option':")
for name in dir(dhanhq):
    if 'option' in name.lower():
        print(f"  - {name}")
        try:
            method = getattr(dhanhq, name)
            if callable(method) and not name.startswith('_'):
                sig = inspect.signature(method)
                print(f"    Signature: {sig}")
        except Exception as e:
            print(f"    Error: {e}")
