# Listener crashes when no port is configured

Our gateway crashes at startup on the staging box, where we don't configure a port:

```
>>> Listener().port(None)
Traceback (most recent call last):
  File ".../gateway/listener.py", line 19, in port
    number = int(raw.strip())
AttributeError: 'NoneType' object has no attribute 'strip'
```

I expected the listener to just use its default port.
