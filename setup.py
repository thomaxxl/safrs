'''
python3 setup.py sdist
twine upload dist/*
'''

from distutils.core import setup
try: # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements

install_requires=[str(ir.req) for ir in parse_requirements('requirements.txt', session=False)]

setup(
  name = 'safrs',
  packages = ['safrs'],
  version = '2.3.0',
  license = 'MIT',
  description = 'safrs : SqlAlchemy Flask-Restful Swagger2',
  long_description=open('README.rst').read(),
  author = 'Thomas Pollet',
  author_email = 'thomas.pollet@gmail.com',
  url = 'https://github.com/thomaxxl/safrs',
  download_url = 'https://github.com/thomaxxl/safrs/archive/2.3.0.tar.gz', 
  keywords = ['SqlAlchemy', 'Flask', 'REST', 'Swagger', 'JsonAPI', 'OpenAPI'], 
  python_requires='>=3.0, !=3.0.*, !=3.1.*, !=3.2.*, <4',
  install_requires=install_requires,
  classifiers = [
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Framework :: Flask',  
        'Topic :: Software Development :: Libraries',
        'Environment :: Web Environment',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4'
        ],
)
