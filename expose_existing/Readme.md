# Exposing existing databases

example:

```
python3 expose_existing.py mysql+pymysql://root:password@localhost/sakila --host 172.16.17.11 --port 5555
```

Exposing existing tables doesn't work yet if there's no column named "id", working on that though :)
