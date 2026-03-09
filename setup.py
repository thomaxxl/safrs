"""
python -m build
twine upload dist/*
"""
from typing import Any

from setuptools import setup, find_packages


def safrs_setup() -> Any:
    install_requires = [
        "Flask>=3.1.3",
        "Flask-SQLAlchemy>=3.1.1",
        "PyYAML>=6.0.3",
        "SQLAlchemy>=2.0.48",
        "Flask-RESTful>=0.3.10",
        "flask-restful-swagger-2>=0.35",
        "flask-swagger-ui>=5.21.0",
        "Flask-Cors>=6.0.2",
        "fastapi[standard]>=0.135.1",
    ]
    flask_extra = [
        "Flask-RESTful>=0.3.10",
        "flask-restful-swagger-2>=0.35",
        "flask-swagger-ui>=5.21.0",
        "Flask-Cors>=6.0.2",
    ]
    fastapi_extra = ["fastapi[standard]>=0.135.1"]

    version = "3.2.0"

    setup(
        name="safrs",
        packages=find_packages(exclude=['test']),
        version=version,
        license="MIT",
        description="safrs : SqlAlchemy Flask-Restful Swagger2",
        long_description=open("README.rst").read(),
        author="Thomas Pollet",
        author_email="thomas.pollet@gmail.com",
        url="https://github.com/thomaxxl/safrs",
        download_url="https://github.com/thomaxxl/safrs/archive/{}.tar.gz".format(version),
        keywords=["SqlAlchemy", "Flask", "REST", "Swagger", "JsonAPI", "OpenAPI"],
        python_requires=">=3.10, <4",
        install_requires=install_requires,
        classifiers=[
            "Development Status :: 3 - Alpha",
            "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
            "Intended Audience :: Developers",
            "Framework :: Flask",
            "Topic :: Software Development :: Libraries",
            "Environment :: Web Environment",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
        ],
        extras_require={
            "admin": ["Flask-Admin>=1.5.8", "Flask-Cors>=6.0.2"],
            "db2api": ["inflect==5.0.2", "Flask-Cors>=6.0.2"],
            "flask": flask_extra,
            "fastapi": fastapi_extra,
            "all": flask_extra + fastapi_extra,
            "dev": flask_extra + fastapi_extra,
            "test": flask_extra + fastapi_extra,
        },
    )


safrs_setup()  # pragma: no cover
