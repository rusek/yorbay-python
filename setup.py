from setuptools import setup, find_packages

setup(
    name='yorbay',
    version='0.1.dev1',
    author='Krzysztof Rusek',
    author_email='savix5@gmail.com',
    description='Localization framework based on l20n file format',
    url='https://github.com/rusek/yorbay-python',
    license='Apache License, Version 2.0',
    keywords='localization',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Internationalization',
    ],
)
