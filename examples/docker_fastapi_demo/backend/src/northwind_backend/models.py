from __future__ import annotations

from safrs import SAFRSBase
from sqlalchemy import Boolean, Column, Float, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class BaseModel(SAFRSBase, Base):
    __abstract__ = True


class Category(BaseModel):
    __tablename__ = "CategoryTableNameTest"
    _s_collection_name = "Category"

    Id = Column(Integer, primary_key=True)
    CategoryName_ColumnName = Column(String(8000))
    Description = Column(String(8000))
    Client_id = Column(Integer)

    ProductList = relationship("Product", back_populates="Category")


class Customer(BaseModel):
    __tablename__ = "Customer"
    _s_collection_name = "Customer"
    allow_client_generated_ids = True

    Id = Column(String(8000), primary_key=True)
    CompanyName = Column(String(8000))
    ContactName = Column(String(8000))
    ContactTitle = Column(String(8000))
    Address = Column(String(8000))
    City = Column(String(8000))
    Region = Column(String(8000))
    PostalCode = Column(String(8000))
    Country = Column(String(8000))
    Phone = Column(String(8000))
    Fax = Column(String(8000))
    Balance = Column(Numeric)
    CreditLimit = Column(Numeric)
    OrderCount = Column(Integer, default=0)
    UnpaidOrderCount = Column(Integer, default=0)
    Client_id = Column(Integer)

    OrderList = relationship(
        "Order",
        back_populates="Customer",
        cascade="all, delete-orphan",
        single_parent=True,
    )


class CustomerDemographic(BaseModel):
    __tablename__ = "CustomerDemographic"
    _s_collection_name = "CustomerDemographic"
    allow_client_generated_ids = True

    Id = Column(String(8000), primary_key=True)
    CustomerDesc = Column(String(8000))


class Department(BaseModel):
    __tablename__ = "Department"
    _s_collection_name = "Department"

    Id = Column(Integer, primary_key=True)
    DepartmentId = Column(Integer, ForeignKey("Department.Id"))
    DepartmentName = Column(String(100))
    SecurityLevel = Column(Integer, default=0)

    Department = relationship("Department", remote_side=[Id], back_populates="DepartmentList")
    DepartmentList = relationship("Department", back_populates="Department")
    EmployeeList = relationship(
        "Employee",
        foreign_keys="Employee.OnLoanDepartmentId",
        back_populates="OnLoanDepartment",
    )
    WorksForEmployeeList = relationship(
        "Employee",
        foreign_keys="Employee.WorksForDepartmentId",
        back_populates="WorksForDepartment",
    )


class Location(BaseModel):
    __tablename__ = "Location"
    _s_collection_name = "Location"
    allow_client_generated_ids = True

    country = Column(String(50), primary_key=True)
    city = Column(String(50), primary_key=True)
    notes = Column(String(256))

    OrderList = relationship("Order", back_populates="Location")


class Region(BaseModel):
    __tablename__ = "Region"
    _s_collection_name = "Region"

    Id = Column(Integer, primary_key=True)
    RegionDescription = Column(String(8000))


class SampleDBVersion(BaseModel):
    __tablename__ = "SampleDBVersion"
    _s_collection_name = "SampleDBVersion"

    Id = Column(Integer, primary_key=True)
    Notes = Column(String(800))


class Shipper(BaseModel):
    __tablename__ = "Shipper"
    _s_collection_name = "Shipper"

    Id = Column(Integer, primary_key=True)
    CompanyName = Column(String(8000))
    Phone = Column(String(8000))


class Supplier(BaseModel):
    __tablename__ = "Supplier"
    _s_collection_name = "Supplier"

    Id = Column(Integer, primary_key=True)
    CompanyName = Column(String(8000))
    ContactName = Column(String(8000))
    ContactTitle = Column(String(8000))
    Address = Column(String(8000))
    City = Column(String(8000))
    Region = Column(String(8000))
    PostalCode = Column(String(8000))
    Country = Column(String(8000))
    Phone = Column(String(8000))
    Fax = Column(String(8000))
    HomePage = Column(String(8000))


class Territory(BaseModel):
    __tablename__ = "Territory"
    _s_collection_name = "Territory"
    allow_client_generated_ids = True

    Id = Column(String(8000), primary_key=True)
    TerritoryDescription = Column(String(8000))
    RegionId = Column(Integer)

    EmployeeTerritoryList = relationship(
        "EmployeeTerritory",
        back_populates="Territory",
        cascade="all, delete",
    )


class Union(BaseModel):
    __tablename__ = "Union"
    _s_collection_name = "Union"

    Id = Column(Integer, primary_key=True)
    Name = Column(String(80))

    EmployeeList = relationship("Employee", back_populates="Union")


class Employee(BaseModel):
    __tablename__ = "Employee"
    _s_collection_name = "Employee"

    Id = Column(Integer, primary_key=True)
    LastName = Column(String(8000))
    FirstName = Column(String(8000))
    Title = Column(String(8000))
    TitleOfCourtesy = Column(String(8000))
    BirthDate = Column(String(8000))
    HireDate = Column(String(8000))
    Address = Column(String(8000))
    City = Column(String(8000))
    Region = Column(String(8000))
    PostalCode = Column(String(8000))
    Country = Column(String(8000))
    HomePhone = Column(String(8000))
    Extension = Column(String(8000))
    Notes = Column(String(8000))
    ReportsTo = Column(Integer)
    PhotoPath = Column(String(8000))
    EmployeeType = Column(String(16))
    Salary = Column(Numeric)
    WorksForDepartmentId = Column(Integer, ForeignKey("Department.Id"))
    OnLoanDepartmentId = Column(Integer, ForeignKey("Department.Id"))
    UnionId = Column(Integer, ForeignKey("Union.Id"))
    Dues = Column(Numeric)
    Email = Column(Text)

    OnLoanDepartment = relationship(
        "Department",
        foreign_keys=[OnLoanDepartmentId],
        back_populates="EmployeeList",
    )
    Union = relationship("Union", back_populates="EmployeeList")
    WorksForDepartment = relationship(
        "Department",
        foreign_keys=[WorksForDepartmentId],
        back_populates="WorksForEmployeeList",
    )
    EmployeeAuditList = relationship(
        "EmployeeAudit",
        back_populates="Employee",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    EmployeeTerritoryList = relationship(
        "EmployeeTerritory",
        back_populates="Employee",
        cascade="all, delete",
    )
    OrderList = relationship("Order", back_populates="Employee")


class Product(BaseModel):
    __tablename__ = "Product"
    _s_collection_name = "Product"

    Id = Column(Integer, primary_key=True)
    ProductName = Column(String(8000))
    SupplierId = Column(Integer)
    CategoryId = Column(Integer, ForeignKey("CategoryTableNameTest.Id"), nullable=False)
    QuantityPerUnit = Column(String(8000))
    UnitPrice = Column(Numeric, nullable=False)
    UnitsInStock = Column(Integer, nullable=False)
    UnitsOnOrder = Column(Integer, nullable=False)
    ReorderLevel = Column(Integer, nullable=False)
    Discontinued = Column(Integer, nullable=False)
    UnitsShipped = Column(Integer)

    Category = relationship("Category", back_populates="ProductList")
    OrderDetailList = relationship("OrderDetail", back_populates="Product")


class EmployeeAudit(BaseModel):
    __tablename__ = "EmployeeAudit"
    _s_collection_name = "EmployeeAudit"

    Id = Column(Integer, primary_key=True)
    Title = Column(String)
    Salary = Column(Numeric)
    LastName = Column(String)
    FirstName = Column(String)
    EmployeeId = Column(Integer, ForeignKey("Employee.Id"))
    CreatedOn = Column(Text)
    UpdatedOn = Column(Text)
    CreatedBy = Column(Text)
    UpdatedBy = Column(Text)

    Employee = relationship("Employee", back_populates="EmployeeAuditList")


class EmployeeTerritory(BaseModel):
    __tablename__ = "EmployeeTerritory"
    _s_collection_name = "EmployeeTerritory"
    allow_client_generated_ids = True

    Id = Column(String(8000), primary_key=True)
    EmployeeId = Column(Integer, ForeignKey("Employee.Id"), nullable=False)
    TerritoryId = Column(String(8000), ForeignKey("Territory.Id"))

    Employee = relationship("Employee", back_populates="EmployeeTerritoryList")
    Territory = relationship("Territory", back_populates="EmployeeTerritoryList")


class Order(BaseModel):
    __tablename__ = "Order"
    _s_collection_name = "Order"
    __table_args__ = (
        ForeignKeyConstraint(["Country", "City"], ["Location.country", "Location.city"]),
    )

    Id = Column(Integer, primary_key=True)
    CustomerId = Column(String(8000), ForeignKey("Customer.Id"), nullable=False)
    EmployeeId = Column(Integer, ForeignKey("Employee.Id"), nullable=False)
    OrderDate = Column(String(8000))
    RequiredDate = Column(String(64))
    ShippedDate = Column(String(8000))
    ShipVia = Column(Integer)
    Freight = Column(Numeric, default=0)
    ShipName = Column(String(8000))
    ShipAddress = Column(String(8000))
    ShipCity = Column(String(8000))
    ShipRegion = Column(String(8000))
    ShipPostalCode = Column(String(8000))
    ShipCountry = Column(String(8000))
    AmountTotal = Column(Numeric)
    Country = Column(String(50))
    City = Column(String(50))
    Ready = Column(Boolean)
    OrderDetailCount = Column(Integer, default=0)
    CloneFromOrder = Column(Integer, ForeignKey("Order.Id"))

    Order = relationship("Order", remote_side=[Id], back_populates="OrderList")
    Location = relationship("Location", back_populates="OrderList")
    Customer = relationship("Customer", back_populates="OrderList")
    Employee = relationship("Employee", back_populates="OrderList")
    OrderList = relationship("Order", back_populates="Order")
    OrderDetailList = relationship(
        "OrderDetail",
        back_populates="Order",
        cascade="all, delete-orphan",
        single_parent=True,
    )


class OrderDetail(BaseModel):
    __tablename__ = "OrderDetail"
    _s_collection_name = "OrderDetail"

    Id = Column(Integer, primary_key=True)
    OrderId = Column(Integer, ForeignKey("Order.Id"), nullable=False)
    ProductId = Column(Integer, ForeignKey("Product.Id"), nullable=False)
    UnitPrice = Column(Numeric)
    Quantity = Column(Integer, nullable=False, default=1)
    Discount = Column(Float, default=0)
    Amount = Column(Numeric)
    ShippedDate = Column(String(8000))

    Order = relationship("Order", back_populates="OrderDetailList")
    Product = relationship("Product", back_populates="OrderDetailList")


EXPOSED_MODELS = [
    Category,
    Customer,
    CustomerDemographic,
    Department,
    Employee,
    EmployeeAudit,
    EmployeeTerritory,
    Location,
    Order,
    OrderDetail,
    Product,
    Region,
    SampleDBVersion,
    Shipper,
    Supplier,
    Territory,
    Union,
]

EXPOSED_RESOURCE_NAMES = [str(model._s_collection_name) for model in EXPOSED_MODELS]
