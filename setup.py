#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='mkbooklet',
    version='1.0.0',
    description='Prepare PDF files for booklet printing',
    author='Paul Baecher',
    author_email='pbaecher@gmail.com',
    url='https://github.com/pb-/mkbooklet',
    packages=find_packages('.'),
    install_requires=[
        'pyPdf ==1.13',
    ],
    entry_points={
        'console_scripts': [
            'mkbooklet = mkbooklet.main:run',
        ],
    },
)
