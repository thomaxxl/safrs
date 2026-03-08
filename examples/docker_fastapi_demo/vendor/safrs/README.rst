SAFRS: Python OpenAPI & JSON:API Framework
==========================================

Please check the `GitHub Readme <https://github.com/thomaxxl/safrs>`__ for documentation.

Overview
--------

SAFRS is an acronym for **S**\ ql\ **A**\ lchemy **F**\ lask-\ **R**\ estful **S**\ wagger. The purpose of this framework is to help python developers create a self-documenting JSON API for sqlalchemy database objects and relationships. These objects can be serialized to JSON and can be created, retrieved, updated and deleted through the JSON API.
Optionally, custom resource object methods can be exposed and invoked using JSON.
Class and method descriptions and examples can be provided in yaml syntax in the code comments. The description is parsed and shown in the swagger web interface.

The result is an easy-to-use `swagger/OpenAPI <https://swagger.io/>`_ and `JSON:API <jsonapi.org>`_ compliant API specification.

Installation
------------

SAFRS can be installed as a `pip package <https://pypi.python.org/pypi/safrs/>`_ or by downloading the latest version from github, for example:

.. code-block:: bash

   git clone https://github.com/thomaxxl/safrs
   cd safrs
   pip3 install -r requirements.txt --user
   python3 setup.py install --user


The examples can then be started with

.. code-block::

   python3 examples/demo_relationship.py "your-interface-ip"


