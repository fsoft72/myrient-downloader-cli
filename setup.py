from setuptools import setup

setup(
    name="myrient-downloader-cli",
    version="0.4.0",
    py_modules=["myrient"],
    install_requires=[
        "requests==2.32.3",
        "beautifulsoup4==4.13.4",
        "textual==6.7.1",
    ],
    entry_points={
        "console_scripts": [
            "myrient-cli=myrient:main",
        ],
    },
)
