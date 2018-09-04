# coding: utf-8
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base


########################################################################################################################
# Manually Added for safrs, TODO: improve this crap
#
from safrs import SAFRSBase

Base = db.Model
metadata = Base.metadata

def BIGINT(_):
    return db.SMALLINT

def SMALLINT(_):
    return db.SMALLINT

def INTEGER(_):
    return db.INTEGER

def TIME(**kwargs):
    return db.TIME

TIMESTAMP= db.TIMESTAMP
NullType = db.String

########################################################################################################################



class HashTable(SAFRSBase, Base):
    __tablename__ = 'HashTable'

    id = Column(String, primary_key=True)
    type = Column(String)
    filename = Column(String)
    volumename = Column(String)
    item_id = Column(String)
