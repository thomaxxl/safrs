from distutils.core import setup
setup(
  name = 'safrs',
  packages = ['safrs'],
  version = '1.0.0',
  description = 'safrs : SqlAlchemy Flask-Restful Swagger2',
  author = 'Thomas Pollet',
  author_email = 'thomas.pollet@gmail.com',
  url = 'https://github.com/thomaxxl/safrs',
  download_url = 'https://github.com/thomaxxl/safrs/archive/1.0.0.tar.gz', 
  keywords = ['SqlAlchemy', 'Flask', 'REST', 'Swagger'], 
  python_requires='<4',
  classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Framework :: Flask',  
        ],
)
