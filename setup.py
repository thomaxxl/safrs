"""
python -m build
twine upload dist/*
"""
from typing import Any

from setuptools import setup, find_packages


def safrs_setup() -> Any:
    with open("requirements.txt", "rt") as fp:
        install_requires = fp.read().strip().split("\n")

    version = "3.1.7"

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
            "admin": ["Flask-Admin>=1.5.8", "Flask-Cors>=3.0.9"],
            "db2api": ["inflect==5.0.2", "Flask-Cors>=3.0.9"],
            "fastapi": ['fastapi[standard]'],
},

    )


safrs_setup()  # pragma: no cover
