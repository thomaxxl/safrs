# coding: utf-8
from sqlalchemy import CHAR, Column, Date, Enum, ForeignKey, INTEGER, String, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from safrs import SAFRSBase


def INTEGER(*args):
    return db.INTEGER


Base = db.Model
metadata = Base.metadata


t_current_dept_emp = Table(
    "current_dept_emp",
    metadata,
    Column("emp_no", INTEGER(11)),
    Column("dept_no", CHAR(4)),
    Column("from_date", Date),
    Column("to_date", Date),
)


class Department(SAFRSBase, Base):
    __tablename__ = "departments"

    dept_no = Column(CHAR(4), primary_key=True)
    dept_name = Column(String(40), nullable=False, unique=True)


t_dept_emp_latest_date = Table(
    "dept_emp_latest_date", metadata, Column("emp_no", INTEGER(11)), Column("from_date", Date), Column("to_date", Date)
)


class Employee(SAFRSBase, Base):
    __tablename__ = "employees"

    emp_no = Column(INTEGER(11), primary_key=True)
    birth_date = Column(Date, nullable=False)
    first_name = Column(String(14), nullable=False)
    last_name = Column(String(16), nullable=False)
    gender = Column(Enum("M", "F"), nullable=False)
    hire_date = Column(Date, nullable=False)


class DeptEmp(SAFRSBase, Base):
    __tablename__ = "dept_emp"

    emp_no = Column(ForeignKey("employees.emp_no", ondelete="CASCADE"), primary_key=True, nullable=False)
    dept_no = Column(ForeignKey("departments.dept_no", ondelete="CASCADE"), primary_key=True, nullable=False, index=True)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)

    department = relationship("Department")
    employee = relationship("Employee")


class DeptManager(SAFRSBase, Base):
    __tablename__ = "dept_manager"

    emp_no = Column(ForeignKey("employees.emp_no", ondelete="CASCADE"), primary_key=True, nullable=False)
    dept_no = Column(ForeignKey("departments.dept_no", ondelete="CASCADE"), primary_key=True, nullable=False, index=True)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)

    department = relationship("Department")
    employee = relationship("Employee")


class Salary(SAFRSBase, Base):
    __tablename__ = "salaries"

    emp_no = Column(ForeignKey("employees.emp_no", ondelete="CASCADE"), primary_key=True, nullable=False)
    salary = Column(INTEGER(11), nullable=False)
    from_date = Column(Date, primary_key=True, nullable=False)
    to_date = Column(Date, nullable=False)

    employee = relationship("Employee")


class Title(SAFRSBase, Base):
    __tablename__ = "titles"

    emp_no = Column(ForeignKey("employees.emp_no", ondelete="CASCADE"), primary_key=True, nullable=False)
    title = Column(String(50), primary_key=True, nullable=False)
    from_date = Column(Date, primary_key=True, nullable=False)
    to_date = Column(Date)

    employee = relationship("Employee")
