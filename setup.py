"""
python3 setup.py sdist
twine upload dist/*
"""

from distutils.core import setup

with open("requirements.txt", "rt") as fp:
    install_requires = fp.read().strip().split("\n")

version = "2.8.1"

setup( # pragma: no cover
    name="safrs",
    packages=["safrs"],
    version=version,
    license="MIT",
    description="safrs : SqlAlchemy Flask-Restful Swagger2",
    long_description=open("README.rst").read(),
    author="Thomas Pollet",
    author_email="thomas.pollet@gmail.com",
    url="https://github.com/thomaxxl/safrs",
    download_url="https://github.com/thomaxxl/safrs/archive/{}.tar.gz".format(version),
    keywords=["SqlAlchemy", "Flask", "REST", "Swagger", "JsonAPI", "OpenAPI"],
    python_requires=">=3.0, !=3.0.*, !=3.1.*, !=3.2.*, <4",
    install_requires=install_requires,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Intended Audience :: Developers",
        "Framework :: Flask",
        "Topic :: Software Development :: Libraries",
        "Environment :: Web Environment",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
    ],
)
