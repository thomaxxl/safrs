# Exposing existing databases

Example:

```
python3 expose_existing.py mysql+pymysql://root:password@localhost/sakila --host 172.16.17.11 --port 5555
```

Installation:

```
mkdir tmpenv
virtualenv tmpenv/
source tmpenv/bin/activate
pip install -r requirements.txt
```


Documentation in the [wiki](https://github.com/thomaxxl/safrs/wiki/Exposing-Existing-Databases)

