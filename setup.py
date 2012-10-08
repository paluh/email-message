try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='email_message',
    author='Tomasz Rybarczyk',
    author_email='paluho@gmail.com',
    version = '2012.9.1',
    url='http://github.com/paluh/email_message',
    py_modules=['email_message'],
    description='Email message wrapper ripped from django.',
    zip_safe=False,
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python'
    ]
)
