from distutils.core import setup
setup(
  name = 'safrs',
  packages = ['safrs'],
  version = '1.0.1',
  description = 'safrs : SqlAlchemy Flask-Restful Swagger2',
  author = 'Thomas Pollet',
  author_email = 'thomas.pollet@gmail.com',
  url = 'https://github.com/thomaxxl/safrs',
  download_url = 'https://github.com/thomaxxl/safrs/archive/1.0.1.tar.gz', 
  keywords = ['SqlAlchemy', 'Flask', 'REST', 'Swagger', 'JsonAPI', 'OpenAPI'], 
  python_requires='>=2.6, !=3.0.*, !=3.1.*, !=3.2.*, <4',
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
