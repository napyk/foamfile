from setuptools import setup, find_packages

with open("README.md", 'r') as f:
    long_description = f.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(name="foamfile",
      version="0.1",
      description='OpenFOAM config file parser',
      long_description=long_description,
      long_description_content_type='text/markdown',
      author="Nikolas Pfister",
      author_email="pfister.nikolas@gmail.com",
      packages=find_packages(),
      install_requires=required)
