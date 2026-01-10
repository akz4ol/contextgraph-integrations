from setuptools import setup, find_packages

setup(
    name="contextgraph-crewai",
    version="0.1.0",
    description="ContextGraph Cloud observer for CrewAI",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="ContextGraph",
    author_email="blog.mot2gmob@gmail.com",
    url="https://github.com/akz4ol/contextgraph-integrations",
    packages=find_packages(),
    py_modules=["contextgraph_observer"],
    install_requires=[
        "crewai>=0.28.0",
        "httpx>=0.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="crewai ai agents governance audit compliance",
)
