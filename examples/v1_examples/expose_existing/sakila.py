# coding: utf-8
##Failed to get col type for address.location
# Failed to get col type for film.special_features
from sqlalchemy import (
    CHAR,
    Column,
    DECIMAL,
    DateTime,
    Enum,
    ForeignKey,
    INTEGER,
    Index,
    LargeBinary,
    SMALLINT,
    String,
    TIMESTAMP,
    Table,
    Text,
    VARCHAR,
    text,
)
from sqlalchemy.sql.sqltypes import NullType
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql.types import MEDIUMINT, TINYINT, YEAR
from sqlalchemy.dialects.mysql.enumerated import SET
from sqlalchemy.ext.declarative import declarative_base
from safrs import SAFRSBase

Base = db.Model
metadata = Base.metadata


def SMALLINT(_):
    return db.SMALLINT


def INTEGER(_):
    return db.INTEGER


NullType = db.String


class Actor(SAFRSBase, Base):
    __tablename__ = "actor"

    actor_id = Column(SMALLINT(5), primary_key=True)
    first_name = Column(String(45), nullable=False)
    last_name = Column(String(45), nullable=False, index=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


t_actor_info = Table(
    "actor_info",
    metadata,
    Column("actor_id", SMALLINT(5), server_default=text("'0'")),
    Column("first_name", String(45)),
    Column("last_name", String(45)),
    Column("film_info", Text),
)


class Addres(SAFRSBase, Base):
    __tablename__ = "address"

    address_id = Column(SMALLINT(5), primary_key=True)
    address = Column(String(50), nullable=False)
    address2 = Column(String(50))
    district = Column(String(20), nullable=False)
    city_id = Column(ForeignKey("city.city_id", onupdate="CASCADE"), nullable=False, index=True)
    postal_code = Column(String(10))
    phone = Column(String(20), nullable=False)
    location = Column(NullType, nullable=False, index=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    city = relationship("City")


class Category(SAFRSBase, Base):
    __tablename__ = "category"

    category_id = Column(TINYINT(3), primary_key=True)
    name = Column(String(25), nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class City(SAFRSBase, Base):
    __tablename__ = "city"

    city_id = Column(SMALLINT(5), primary_key=True)
    city = Column(String(50), nullable=False)
    country_id = Column(ForeignKey("country.country_id", onupdate="CASCADE"), nullable=False, index=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    country = relationship("Country")


class Country(SAFRSBase, Base):
    __tablename__ = "country"

    country_id = Column(SMALLINT(5), primary_key=True)
    country = Column(String(50), nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class Customer(SAFRSBase, Base):
    __tablename__ = "customer"

    customer_id = Column(SMALLINT(5), primary_key=True)
    store_id = Column(ForeignKey("store.store_id", onupdate="CASCADE"), nullable=False, index=True)
    first_name = Column(String(45), nullable=False)
    last_name = Column(String(45), nullable=False, index=True)
    email = Column(String(50))
    address_id = Column(ForeignKey("address.address_id", onupdate="CASCADE"), nullable=False, index=True)
    active = Column(TINYINT(1), nullable=False, server_default=text("'1'"))
    create_date = Column(DateTime, nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    address = relationship("Addres")
    store = relationship("Store")


t_customer_list = Table(
    "customer_list",
    metadata,
    Column("ID", SMALLINT(5), server_default=text("'0'")),
    Column("name", String(91)),
    Column("address", String(50)),
    Column("zip code", String(10)),
    Column("phone", String(20)),
    Column("city", String(50)),
    Column("country", String(50)),
    Column("notes", String(6)),
    Column("SID", TINYINT(3)),
)


class Film(SAFRSBase, Base):
    __tablename__ = "film"

    film_id = Column(SMALLINT(5), primary_key=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    release_year = Column(YEAR(4))
    language_id = Column(ForeignKey("language.language_id", onupdate="CASCADE"), nullable=False, index=True)
    original_language_id = Column(ForeignKey("language.language_id", onupdate="CASCADE"), index=True)
    rental_duration = Column(TINYINT(3), nullable=False, server_default=text("'3'"))
    rental_rate = Column(DECIMAL(4, 2), nullable=False, server_default=text("'4.99'"))
    length = Column(SMALLINT(5))
    replacement_cost = Column(DECIMAL(5, 2), nullable=False, server_default=text("'19.99'"))
    rating = Column(Enum("G", "PG", "PG-13", "R", "NC-17"), server_default=text("'G'"))
    special_features = Column(SET)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    language = relationship("Language", primaryjoin="Film.language_id == Language.language_id")
    original_language = relationship("Language", primaryjoin="Film.original_language_id == Language.language_id")


class FilmActor(SAFRSBase, Base):
    __tablename__ = "film_actor"

    actor_id = Column(ForeignKey("actor.actor_id", onupdate="CASCADE"), primary_key=True, nullable=False)
    film_id = Column(ForeignKey("film.film_id", onupdate="CASCADE"), primary_key=True, nullable=False, index=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    actor = relationship("Actor")
    film = relationship("Film")


class FilmCategory(SAFRSBase, Base):
    __tablename__ = "film_category"

    film_id = Column(ForeignKey("film.film_id", onupdate="CASCADE"), primary_key=True, nullable=False)
    category_id = Column(ForeignKey("category.category_id", onupdate="CASCADE"), primary_key=True, nullable=False, index=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    category = relationship("Category")
    film = relationship("Film")


t_film_list = Table(
    "film_list",
    metadata,
    Column("FID", SMALLINT(5), server_default=text("'0'")),
    Column("title", String(255)),
    Column("description", Text),
    Column("category", String(25)),
    Column("price", DECIMAL(4, 2), server_default=text("'4.99'")),
    Column("length", SMALLINT(5)),
    Column("rating", Enum("G", "PG", "PG-13", "R", "NC-17"), server_default=text("'G'")),
    Column("actors", Text),
)


class FilmText(SAFRSBase, Base):
    __tablename__ = "film_text"
    __table_args__ = (Index("idx_title_description", "title", "description"),)

    film_id = Column(SMALLINT(6), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)


class Inventory(SAFRSBase, Base):
    __tablename__ = "inventory"
    __table_args__ = (Index("idx_store_id_film_id", "store_id", "film_id"),)

    inventory_id = Column(MEDIUMINT(8), primary_key=True)
    film_id = Column(ForeignKey("film.film_id", onupdate="CASCADE"), nullable=False, index=True)
    store_id = Column(ForeignKey("store.store_id", onupdate="CASCADE"), nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    film = relationship("Film")
    store = relationship("Store")


class Language(SAFRSBase, Base):
    __tablename__ = "language"

    language_id = Column(TINYINT(3), primary_key=True)
    name = Column(CHAR(20), nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


t_nicer_but_slower_film_list = Table(
    "nicer_but_slower_film_list",
    metadata,
    Column("FID", SMALLINT(5), server_default=text("'0'")),
    Column("title", String(255)),
    Column("description", Text),
    Column("category", String(25)),
    Column("price", DECIMAL(4, 2), server_default=text("'4.99'")),
    Column("length", SMALLINT(5)),
    Column("rating", Enum("G", "PG", "PG-13", "R", "NC-17"), server_default=text("'G'")),
    Column("actors", Text),
)


class Payment(SAFRSBase, Base):
    __tablename__ = "payment"

    payment_id = Column(SMALLINT(5), primary_key=True)
    customer_id = Column(ForeignKey("customer.customer_id", onupdate="CASCADE"), nullable=False, index=True)
    staff_id = Column(ForeignKey("staff.staff_id", onupdate="CASCADE"), nullable=False, index=True)
    rental_id = Column(ForeignKey("rental.rental_id", ondelete="SET NULL", onupdate="CASCADE"), index=True)
    amount = Column(DECIMAL(5, 2), nullable=False)
    payment_date = Column(DateTime, nullable=False)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    customer = relationship("Customer")
    rental = relationship("Rental")
    staff = relationship("Staff")


class Rental(SAFRSBase, Base):
    __tablename__ = "rental"
    __table_args__ = (Index("rental_date", "rental_date", "inventory_id", "customer_id", unique=True),)

    rental_id = Column(INTEGER(11), primary_key=True)
    rental_date = Column(DateTime, nullable=False)
    inventory_id = Column(ForeignKey("inventory.inventory_id", onupdate="CASCADE"), nullable=False, index=True)
    customer_id = Column(ForeignKey("customer.customer_id", onupdate="CASCADE"), nullable=False, index=True)
    return_date = Column(DateTime)
    staff_id = Column(ForeignKey("staff.staff_id", onupdate="CASCADE"), nullable=False, index=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    customer = relationship("Customer")
    inventory = relationship("Inventory")
    staff = relationship("Staff")


t_sales_by_film_category = Table("sales_by_film_category", metadata, Column("category", String(25)), Column("total_sales", DECIMAL(27, 2)))


t_sales_by_store = Table(
    "sales_by_store", metadata, Column("store", String(101)), Column("manager", String(91)), Column("total_sales", DECIMAL(27, 2))
)


class Staff(SAFRSBase, Base):
    __tablename__ = "staff"

    staff_id = Column(TINYINT(3), primary_key=True)
    first_name = Column(String(45), nullable=False)
    last_name = Column(String(45), nullable=False)
    address_id = Column(ForeignKey("address.address_id", onupdate="CASCADE"), nullable=False, index=True)
    picture = Column(LargeBinary)
    email = Column(String(50))
    store_id = Column(ForeignKey("store.store_id", onupdate="CASCADE"), nullable=False, index=True)
    active = Column(TINYINT(1), nullable=False, server_default=text("'1'"))
    username = Column(String(16), nullable=False)
    password = Column(VARCHAR(40))
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    address = relationship("Addres")
    store = relationship("Store", primaryjoin="Staff.store_id == Store.store_id")


t_staff_list = Table(
    "staff_list",
    metadata,
    Column("ID", TINYINT(3), server_default=text("'0'")),
    Column("name", String(91)),
    Column("address", String(50)),
    Column("zip code", String(10)),
    Column("phone", String(20)),
    Column("city", String(50)),
    Column("country", String(50)),
    Column("SID", TINYINT(3)),
)


class Store(SAFRSBase, Base):
    __tablename__ = "store"

    store_id = Column(TINYINT(3), primary_key=True)
    manager_staff_id = Column(ForeignKey("staff.staff_id", onupdate="CASCADE"), nullable=False, unique=True)
    address_id = Column(ForeignKey("address.address_id", onupdate="CASCADE"), nullable=False, index=True)
    last_update = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    address = relationship("Addres")
    manager_staff = relationship("Staff", primaryjoin="Store.manager_staff_id == Staff.staff_id")
