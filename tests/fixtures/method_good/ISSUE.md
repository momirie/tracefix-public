# Minor bump keeps the old patch number

Releasing 1.2.3 and bumping the minor version gives the wrong number:

```
>>> Version(1, 2, 3).bump("minor")
Version(major=1, minor=3, patch=3)
```

I expected 1.3.0, not 1.3.3. Bumping the major version looks fine.
