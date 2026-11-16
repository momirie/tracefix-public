# Service crashes at startup when PORT is not set

Service crashes at startup on our staging box:

```
  File ".../svc/config.py", line 34, in parse_port
    port = int(raw.strip())
AttributeError: 'NoneType' object has no attribute 'strip'
```

We don't set PORT there. The README says it should just fall back to 8080.
