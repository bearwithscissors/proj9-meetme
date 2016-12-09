"""
Just to test database functions,
outside of Flask.

We want to open our MongoDB database,
insert some memos, and read them back
"""

import pymongo
from pymongo import MongoClient
import arrow
import sys

import secrets.admin_secrets
import secrets.client_secrets

MONGO_CLIENT_URL = "mongodb://{}:{}@{}:{}/{}".format(
    secrets.client_secrets.db_user,
    secrets.client_secrets.db_user_pw,
    secrets.admin_secrets.host,
    secrets.admin_secrets.port,
    secrets.client_secrets.db)

try:
    dbclient = MongoClient(MONGO_CLIENT_URL)
    db = getattr(dbclient, secrets.client_secrets.db)
    print("Got database")
    collection = db.dated
    print("Using sample collection")
except Exception as err:
    print("Failed")
    print(err)
    sys.exit(1)


#
# Insertions:  I commented these out after the first
# run successfuly inserted them
#

record = { "type": "dated_memo",
           "date":  arrow.utcnow().naive,
           "text": "This is a sample memo"
          }
collection.insert(record)

record = { "type": "dated_memo",
           "date":  arrow.utcnow().replace(days=+1).naive,
           "text": "Sample one day later"
          }
collection.insert(record)

#
# Read database --- May be useful to see what is in there,
# even after you have a working 'insert' operation in the flask app,
# but they aren't very readable.  If you have more than a couple records,
# you'll want a loop for printing them in a nicer format.
#

records = [ ]
for record in collection.find( { "type": "dated_memo" } ):
   records.append(
        { "type": record['type'],
          "date": arrow.get(record['date']).to('local').isoformat(),
           "text": record['text']
    })

print(records)
