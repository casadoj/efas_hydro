import pandas as pd
import re
import requests
from datetime import datetime, timedelta
from tqdm.auto import tqdm
from typing import Union, Optional, List
import logging


def get_timeseries(
    user: str,
    password: str,
    station_id: int,
    service: str,
    variable: Optional[Union[str, List[str]]] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
):
    """It extracts time series from the hydrological data base based on the specified filters.
    Refer to the documentation (https://confluence.smhi.tds.tieto.com/pages/viewpage.action?spaceKey=EHDCC&title=D2-07.2.+API) for further reference about services and variables.
    
    Parameters:
    -----------
    user: string
    password: string
    station_id: int
        Station identifier in the database
    service: string
        Type of data to be extracted. Possible values:
            Near-real-time data: 'noperational1h', 'noperational6h', 'noperational24h'
            Historical data: 'nhoperational1h', 'nhoperational6h', 'nhoperational24h'
    variable: string or list of strings (optional)
        Abbreviations of the variables of interest. Possible values: 
            'W': river stage
            'D': river discharge
            'I': reservoir inflow
            'O': reservoir outflow
            'V': reservoir storage
            'R': reservoir level
        If not provided, all the variables above will be tried.
    start: datetime (optional)
        Beginning of the period of interest. If not provided, 1950-01-01 will be used as the lower limit.
    end: datetime (optional)
        End of the period of interest. If not provided, the current time will be used as the upper limit.
        
    Returns:
    --------
    data: pandas.DataFrame
        The time series for that station, service and variables.
    """
    
    API_URL = 'https://ehdcc.soologic.com/wsOperational/webapi'
    VARIABLES = {
        'W': 'water_level',
        'D': 'discharge',
        'I': 'inflow',
        'O': 'outflow',
        'V': 'volume',
        'R': 'level',
    }
    SERVICES = {
        'noperational1h': '1 hour near-real-time operational data', 
        'noperational6h': '6 hour near-real-time operational data', 
        'noperational24h': '24 hour near-real-time operational data', 
        'nhoperational1h': '1 hour historical operational data', 
        'nhoperational6h': '6 hour historical operational data', 
        'nhoperational24hw': '24 hour historical operational data', 
        # 'nrt': 'Near-real-time data. Output in the same format that was being originally used in FTP files', 
        # 'historic': 'Historic data. Output in the same format that was being originally used in FTP files'
    }
    strftime = '%Y-%m-%dT%H:%M:%S'
    
    if service not in SERVICES:
        logging.error(f'Service {service} is not correct. Choose one of these: {list(SERVICES)}')
        return None
    
    if variable is None:
        variable = list(VARIABLES)
    if isinstance(variable, str):
        variable = [variable]
        
    # time resolution of the service
    time_resolution = int(re.findall(r'\d+', service)[0]) # hours
    
    # data must be downloaded in batches due to server limitations
    start = start or datetime(1950, 1, 1)
    end = end or datetime.now()
    batch_dates = pd.date_range(start, end, periods=11).date

    # download data
    data_list = []
    for var in tqdm(variable, desc='Variables'):

        if var not in VARIABLES:
            logging.warning(f'Variable {var} is not a correct variable abbreviation.')
            continue
            
        var_name = VARIABLES[var]
        serie_list = []
        for i, (st, en) in enumerate(zip(batch_dates[:-1], batch_dates[1:])):
            if i > 0:
                st += timedelta(hours=time_resolution)     
                
            # request data
            url = f'{API_URL}/{service}/{st.strftime(strftime)}/{en.strftime(strftime)}/{station_id}/{var}'
            response = requests.get(url, auth=requests.auth.HTTPBasicAuth(user, password))
            
            # process response
            if response.ok:
                if 'message' in response.json():
                    logging.info(response.json())
                    continue
                df = pd.DataFrame(response.json())
                if not df.empty:
                    df = df[['Timestamp', 'AvgValue']].rename(columns={'AvgValue': var_name})
                    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                    df.set_index('Timestamp', inplace=True)
                    serie_list.append(df)

        if serie_list:
            data_list.append(pd.concat(serie_list, axis=0).sort_index())

    # combine all data
    if data_list:  
        data = pd.concat(data_list, axis=1)
        
        # ensure a complete index with the expected resolution
        idx = pd.date_range(data.first_valid_index(), data.last_valid_index(), freq=f'{time_resolution}h')
        if len(idx) > len(data):
            data = data.reindex(idx)
        data.index.name = 'time'
        return data
    
    logging.info(f'No data was found for station with EFAS_ID {station_id}')
    return None