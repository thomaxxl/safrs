# python setup.py sdist
# twine upload dist/*
from distutils.core import setup
from pip.req import parse_requirements


install_requires=[str(ir.req) for ir in parse_requirements('requirements.txt', session=False)]

setup(
  name = 'safrs',
  packages = ['safrs'],
  version = '1.0.6',
  license = 'MIT',
  description = 'safrs : SqlAlchemy Flask-Restful Swagger2',
  author = 'Thomas Pollet',
  author_email = 'thomas.pollet@gmail.com',
  url = 'https://github.com/thomaxxl/safrs',
  download_url = 'https://github.com/thomaxxl/safrs/archive/1.0.5.tar.gz', 
  keywords = ['SqlAlchemy', 'Flask', 'REST', 'Swagger', 'JsonAPI', 'OpenAPI'], 
  python_requires='>=2.6, !=3.0.*, !=3.1.*, !=3.2.*, <4',
  install_requires=install_requires,
  classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Framework :: Flask',  
        'Topic :: Software Development :: Libraries',
        'Environment :: Web Environment',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4'
        ],
)
