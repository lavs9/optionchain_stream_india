import dhanhq
import inspect

print("Available in dhanhq module:")
for name in dir(dhanhq):
    if not name.startswith('_'):
        print(f"  - {name}")
        obj = getattr(dhanhq, name)
        if inspect.isclass(obj):
            print(f"    (class)")
