# EFAS-Hydro

Tools to extract data from the Hydrological Data Colection Centre of the European Flood Awareness System.

## Installation

Get a local copy of the repository. You can either download it from GitHub or clone it with Git:

```Bash
git clone https://github.com/casadoj/efas_hydro.git
```

Move to the root directory of the repository you've just copied:

```Bash
cd <YOUR_PATH>/efas_hydro/
```

Install the package with PiP:

```Bash
pip install .
```

## Tools

To be able to use these functions you need credentials to access the Hydrological Data Management Service database. If you already have credentials, this [tutorial](./notebook/tutorial.ipynb) explains how to use the tools.

### Stations

#### `get_stations()`

This function retrieves station metadata from the API and returns it as a GeoDataFrame. By default it extracts all the stations in the database, but several attibutes allow to filter the results:

* `kind` allows you to extract only gauging stations (`river`) or only reservoirs (`reservoir`).
* The `country_id` allows you to extract the stations in one or more countries. You need to use the country ISO 3166-1 alfa-2 code, e.g., 'PT' for Portual, 'IT' for Italy...
* You can also filter by provider(s) using the `provider_id` attribute.
* If you already know the EFAS_ID of the stations, you can use the `station_id` attribute.
* You can also filter statios with a bounding box using the `extent` argument. You need to provide a list of 4 values: minimum longitud, minimum latitud, maximum longitude and maximum latitude.

The function returns a point `geopandas.GeoDataFrame` with the stations that passed the filters and their metadata.

#### `find_duplicates()`

This function finds duplicated stations in the database based on distance (points closer than the threshold) and provider (if they have different provider). The input is a `geopandas.GeoDataFrame` like that produced using [`get_stations()`](#get_stations()). Two extra attributes can be defined:

* `provider_col` to define the column in the input table that contains the provider ID. Only necessary if the input table was not produced by `get_stations()`.
* `distance_thr` is the distance below which duplicates can exist. Points further apart than this distance will not be considered as duplicates. The values depend on the reference coordinate system in the input table. By default, it uses a value in degrees, as the output from `get_stations()` is in a geographical reference system (epsg:4326).

It returns a list of lists with groups of duplicated stations. The values in these lists are the index in the input table.

### Time series

#### `get_timeseries()`

This function extracts time series from the hydrological data base for a single station an service, but multiple variables. Refer to the [database documentation](https://confluence.smhi.tds.tieto.com/pages/viewpage.action?spaceKey=EHDCC&title=D2-07.2.+API) for further reference about services and variables. The function allows to limit the period extracted using the `start` and `end` attributes.

It returns a `pandas.DataFrame` with time steps as rows and variables as columns.