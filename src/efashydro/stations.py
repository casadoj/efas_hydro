import os
os.environ['USE_PYGEOS'] = '0'
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
import requests
import unicodedata
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from typing import Optional, Union, List, Tuple, Literal
import logging
from pathlib import Path


def remove_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text) if unicodedata.category(c) != 'Mn'
    )


def get_stations(
    user: str, 
    password: str, 
    kind: Optional[Literal['river', 'reservoir']] = None, 
    country_id: Optional[Union[str, List[str]]] = None,
    provider_id: Optional[Union[int, List[int]]] = None, 
    station_id: Optional[Union[int, List[int]]] = None,
    extent: Optional[List[float]] = None,
) -> gpd.GeoDataFrame:
    """
    Retrieves station metadata from the API and returns it as a GeoDataFrame. By default it extracts all the stations in the database, but several attibutes allow to filter the results.
    
    Parameters:
    -----------
    user: string
    password: string
    kind: string (optional)
        Type of station to extract: 'river' for gauging stations or 'reservoir'. If None, both types will be extracted
    country_id: string or list of strings (optional)
        Country code. For instance, 'ES' for Spain', 'PT' for portugal...
    provider_id: integer or list of integers (optional)
        ID of the data provider
    station_id: integer or list of integers (optional)
        ID of the station
    extent: list (optional)
        Bounding box of the stations to be extracted. It must contain 4 values: [xmin, ymin, xmax, ymax]
        
    Returns:
    --------
    stations: geopandas.GeoDataFrame
        A table of stations that pass the specified filters and their metadata
    """
    
    API_URL = 'https://ehdcc.soologic.com/wsOperational/webapi'
    SERVICE = 'stationsmdv2'   
        
    # request data
    url = f'{API_URL}/{SERVICE}/json/' 
    response = requests.get(url, auth=requests.auth.HTTPBasicAuth(user, password))
    if response.status_code == 200:
        stations = pd.DataFrame(response.json())
    else:
        logging.error(f'API request to {url} failed.\nStatus code: {response.status_code}')
        return None
    
    # process data
    stations.columns = stations.columns.str.upper()
    stations.set_index('EFAS_ID', drop=True, inplace=True)
    stations.sort_index(axis=1, inplace=True)
    
    # remove empty or unnecessary columns
    stations.dropna(axis=1, how='all', inplace=True)
    stations.drop(
        ['LATITUDE_GEODESIC', 'LONGITUDE_GEODESIC', 'GEODESIC_REFERENCE_SYSTEM', 'VARIABLES', 'CATCHMENT_AREA_UNITS', 'HEIGHT_UNITS'],
        axis=1,
        inplace=True,
        errors='ignore'
    )
    
    # simplify column names
    rename_cols = {
        'HAS_RTDATA': 'DATA_RT',
        'HAS_HISTORICAL_DATA': 'DATA_HIST',
        'NATIONAL_STATION_IDENTIFIER': 'LOCAL_ID',
        'PROVIDER_ID': 'PROV_ID',
        'COUNTRY-CODE': 'COUNTRY_ID',
        'BASIN_ENGLISH': 'BASIN_EN',
        'BASIN_LOCAL': 'BASIN_LOC',
        'RIVERNAME_LOCAL': 'RIVER_LOC',
        'RIVERNAME_ENGLISH': 'RIVER_EN',
        'CATCHMENT_AREA': 'CATCH_SKM',
        'LATITUDE_WGS84': 'LAT',
        'LONGITUDE_WGS84': 'LON',
        'COORDINATES_CHECKED': 'COORD_TEST',
        'HEIGHT': 'DAM_HGT_M',
        'HEIGHT_REFERENCE_SYSTEM': 'HEIGHT_RS',
        'LOCAL_REFERENCE_SYSTEM': 'LOCAL_Rs',
        'DATE_OF_STARTING_MEASUREMENT': 'START',
        'DATE_OF_ENDING_MEASUREMENT': 'END',
        'DATE_OF_REGISTRATION': 'REGISTERED',
        'LAST_CHANGE_COMMENT': 'COMMENT_',
        'X-COORDINATE': 'X',
        'Y-COORDINATE': 'Y',
        'CALIBRATION_ID': 'CALIB_ID',
        'DELIVERY_POLICY': 'DELIVERY',
        'INTERNAL_NATIONALSTATIONIDENTIFIER': 'INT_ID',
        'LOCAL_PROJECTION_INFO': 'LOC_PROJ',
        'LOCATION_ON_RIVER_KM': 'RIVER_KM',
        'VERTICAL_DATUM': 'VERT_DATUM'
    }
    stations.rename(columns=rename_cols, inplace=True)
    
    # fix country names
    stations.COUNTRY_ID = stations.COUNTRY_ID.str.upper().replace('SP', 'ES')
    stations.COUNTRY = stations.COUNTRY.str.capitalize()
    
    country_map = {
        'CY': 'Cyprus',
        'MK': 'North Macedonia',
        'DK': 'Denmark',
        'AM': 'Armenia',
        'AL': 'Albania'
    } # these are country codes that have no associated name in the database
    for ID in stations.COUNTRY_ID.unique():
        try:
            country_map[ID] = stations[stations.COUNTRY_ID == ID].COUNTRY.value_counts().index[0]
        except:
            logging.info(f' {ID} has no country name associated')
    stations.COUNTRY = stations.COUNTRY_ID.map(country_map)

    # normalize string columns
    text_columns = ['NAME', 'BASIN_LOC', 'BASIN_EN', 'RIVER_LOC', 'RIVER_EN']
    stations[text_columns] = stations[text_columns].fillna('').astype(str)
    for col in text_columns:
        stations[col] = stations[col].str.capitalize().apply(remove_accents)
    
    # apply filters
    
    if kind:
        if stations.TYPE.isnull().any():
            logging.warning(f' {stations.TYPE.isnull().sum()} stations are missing the type')
        stations = stations[stations.TYPE.eq(kind.upper())]
    
    if country_id:
        if stations.COUNTRY_ID.isnull().any():
            logging.warning(f' {stations.COUNTRY_ID.isnull().sum()} stations are missing the country ID')
        if isinstance(country_id, str):
            country_id = [country_id]
        stations = stations[stations.COUNTRY_ID.isin(country_id)]
        
    if provider_id:
        if stations.PROV_ID.isnull().any():
            logging.warning(f' {stations.PROV_ID.isnull().sum()} stations are missing the provider ID')
        if isinstance(provider_id, int):
            provider_id = [provider_id]
        stations = stations[stations.PROV_ID.isin(provider_id)]
        
    if station_id:
        if isinstance(station_id, int):
            station_id = [station_id]
        stations = stations.loc[station_id]
                
    # convert to geopandas
    if stations.LON.isnull().any():
        logging.warning(f' {stations.LON.isnull().sum()} stations are missing the longitude')
    if stations.LAT.isnull().any():
        logging.warning(f' {stations.LAT.isnull().sum()} stations are missing the latitude')  
    stations = stations[stations.LON.notnull() & stations.LAT.notnull()]
    stations = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations['LON'], stations['LAT']),
        crs='epsg:4326'
    )
    
    if extent:
        if len(extent) == 4:
            bbox = gpd.GeoSeries([box(*extent)], crs='epsg:4326')
            stations = stations[stations.geometry.within(bbox.iloc[0])]
        else:
            logging.warning('The extent filter could not be applied because the format is not correct: [xmin, ymin, xmax, ymax]')
        
    return stations


def plot_stations(
    geometry,
    area: Optional[pd.Series] = None,
    save: Union[str, Path] = None,
    **kwargs
):
    """Creates a maps where reservoirs are represented as dots. The size of the dots reflects the catchment area (if provided)
    
    Parameters:
    -----------
    geometry: gpd.GeoSeries
        Geometry of the points
    area: pandas.Series (optional)
        Reservoir catchment area (km2)
    save: str or pathlib.Path (optional)
        If provided, file where the plot will be saved
    """
    
    figsize = kwargs.get('figsize', (20, 5))
    title = kwargs.get('title', None)
    alpha = kwargs.get('alpha', .7)
    size = kwargs.get('size', 12)
    color = kwargs.get('color', 'steelblue')
    
    # set up plot
    proj = ccrs.PlateCarree()
    fig, ax = plt.subplots(
        figsize=figsize, 
        subplot_kw={'projection': proj}
    )
    ax.add_feature(
        cfeature.NaturalEarthFeature('physical', 'land', '10m', edgecolor='face', facecolor='wheat'),#'lightgray'),
        alpha=.5,
        zorder=0
    )
    ax.add_feature(
        cfeature.NaturalEarthFeature('physical', 'rivers_lake_centerlines', '10m', edgecolor='lightslategrey', facecolor='none', linewidth=.5),
        alpha=0.7,
        zorder=1
    )
    if 'extent' in kwargs:
        ax.set_extent(kwargs['extent'], crs=proj)
    if title is not None:
        ax.text(.5, 1.125, title, horizontalalignment='center', verticalalignment='bottom', transform=ax.transAxes, fontsize=12)
    ax.axis('off')
    
    # plot reservoir poitns
    s = np.cbrt(area) if area is not None else size
    scatter = ax.scatter(
        geometry.x,
        geometry.y,
        s=s,
        c=color,
        alpha=alpha,
        zorder=2
    )  
    
    # legend
    # if area is not None:
    #     legend = ax.legend(
    #         *scatter.legend_elements(prop='sizes', num=4, alpha=alpha),
    #         title='catchment (km²)',
    #         # bbox_to_anchor=(1.2, 0.5),
    #         bbox_to_anchor=[1.025, .6, .06, .25],
    #         loc='center left',
    #         frameon=False
    #         )
    #     ax.add_artist(legend)    

    # save
    if save is not None:
        plt.savefig(save, dpi=300, bbox_inches='tight')

        
def find_duplicates(
    gdf: gpd.GeoDataFrame,
    provider_col: str = 'PROV_ID',
    distance_thr: float = .01667, 
):
    """Finds duplicates in the input GeoDataFrame based on distance (points closer than the threshold) and provider (if they have different provider)
    
    Parameters:
    -----------
    gdf: geopandas.GeoDataFrame
        table of reservoirs/stations in the database. For instance, the result from `get_stations()`
    provider_col: str
        column in "gdf" that defines the provider. Duplicates must have a different provider
    distance_thr: float
        distance below which duplicates can exist. Points further apart than this distance will not be spotted as duplicates. The values depend on the reference coordinate system in "gdf". By default, it uses a value in degrees, as the output from `get_stations()` is in a geographical reference system (epsg:4326)
        
    Returns:
    --------
    A list of lists with groups of duplicates. The values are the index in "gdf"
    """
    
    duplicates = []
    for ID, point in gdf.geometry.items():
        if any(ID in sublist for sublist in duplicates):
            continue
        
        prov_id = gdf.loc[ID, provider_col]

        # distance to the other reservoirs
        others = gdf[gdf.index != ID]
        distance = others.geometry.distance(point)

        # find close reservoirs
        if distance.min() < distance_thr:
            ids = distance[distance < distance_thr].index.tolist()
            ids = [id for id in ids if gdf.loc[id, provider_col] != prov_id]
            if len(ids) > 0:
                duplicates.append([ID] + ids)
                
    return duplicates