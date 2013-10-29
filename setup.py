try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import email_message


CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 2.7',
]

setup(
    name='email-message',
    author='Tomasz Rybarczyk',
    author_email='paluho@gmail.com',
    version = email_message.__version__,
    url='http://github.com/paluh/email-message',
    py_modules=['email_message'],
    description='Email message wrapper ripped from django.',
    zip_safe=False,
    classifiers=CLASSIFIERS,
)
