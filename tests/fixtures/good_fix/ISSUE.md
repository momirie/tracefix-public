# Orders list is missing the last order

We have 10 orders and show 3 per page. The pager shows pages 1–3, and order #10 never
appears anywhere. Asking for page 4 directly gives `PageOutOfRange`:

```
pager.pagination.PageOutOfRange: page 4 is outside 1..3
```

With 9 orders everything looks fine.
