from setuptools import setup, find_packages

setup(
    name='efas-hydro',
    version='1.0.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    # entry_points={
    #     'console_scripts': [
    #         'simulate=lisfloodreservoirs.simulate:main',
    #         'calibrate=lisfloodreservoirs.calibrate:main',
    #     ],
    # },
    install_requires=[
        'numpy',
        'pandas',
        'geopandas',
        'requests',
        'statsmodels',
        'tqdm',
        'unidecode',
        'xarray',
    ],
    author='Jesús Casado Rodríguez',
    author_email='jesus.casado-rodriguez@ec.europa.eu',
    description='Tools to extract data from the Hydrological Data Collection Centre of the European Flood Awareness System',
    keywords='hydrologgic-database efas glofas',
)