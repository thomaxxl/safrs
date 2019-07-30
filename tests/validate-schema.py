from jsonschema import validate
import json, requests

schema = json.load(open("jsonapi-schema.json"))

r = requests.get("http://127.0.0.1:5000/Users/")
print(r.json)
