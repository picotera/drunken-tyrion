from setuptools import setup

setup(name='manager',
      version='1.0',
      description='Search manager gear',
      author='Koby Bass',
      author_email='kobybum@gmail.com.com',
      install_requires=['Flask>=0.10.1','flask-wtf', 'WTForms', 'psycopg2','pika'],
     )
