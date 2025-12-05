import inspect
from upstox_client.api.options_api import OptionsApi

print("OptionsApi methods:")
for name, method in inspect.getmembers(OptionsApi, predicate=inspect.isfunction):
    if not name.startswith('_'):
        print(f"  - {name}")
        # Try to get signature
        try:
            sig = inspect.signature(method)
            print(f"    Signature: {sig}")
        except:
            pass
