
import os
import json
from datetime import datetime
from urllib3.util.retry import Retry

import requests
from requests.adapters import HTTPAdapter
from requests_futures.sessions import FuturesSession

from usgs import USGS_API, USGSError, USGSAuthExpiredError, __version__
from usgs import payloads


TMPFILE = os.path.join(os.path.expanduser("~"), ".usgs")


def _get_api_key(api_key):

    if api_key is None and os.path.exists(TMPFILE):
        with open(TMPFILE, "r") as f:
            api_key_info = json.load(f)
        api_key = api_key_info['apiKey']

    return api_key

def _check_for_usgs_error(data):

    error_code = data['errorCode']
    if error_code is None:
        return

    error = data['errorMessage']

    if error_code == 'AUTH_EXPIRED':
        raise USGSAuthExpiredError("API key has expired. Try logging out and logging back in.")

    raise USGSError('%s: %s' % (error_code, error))

def _create_session(api_key):
    api_key = _get_api_key(api_key)

    headers = {
        'User-Agent': 'Python usgs v{}'.format(__version__)
    }
    if api_key:
        headers['X-Auth-Token'] = api_key

    session = requests.Session()
    session.headers.update(headers)
    retries = Retry(total=5, backoff_factor=2)
    session.mount(USGS_API, HTTPAdapter(max_retries=retries))

    return session

def dataset_filters(dataset, api_key=None):
    api_key = _get_api_key(api_key)

    with _create_session(api_key) as session:
        url = '{}/dataset-filters'.format(USGS_API)
        payload = payloads.dataset_filters(dataset)
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)

    return response

def download_options(dataset, entity_ids, api_key=None):
    api_key = _get_api_key(api_key)

    with _create_session(api_key) as session:
        url = '{}/download-options'.format(USGS_API)
        payload = payloads.download_options(dataset, entity_ids)
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)

    return response

def dataset_download_options(dataset, api_key=None):
    """
    The dataset download options method is used to discover downloadable
    products for a specified dataset. Unlike the `download_options` method,
    this does not check product availability.

    :param str dataset: Used to identify the which dataset to return results for.
    """
    api_key = _get_api_key(api_key)

    with _create_session(api_key) as session:
        url = '{}/dataset-download-options'.format(USGS_API)
        payload = payloads.dataset_download_options(dataset)
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)

    return response

def download_request(dataset, entity_id, product_id, api_key=None):
    """
    This method is used to insert the requested downloads into the download queue
    and returns the available download URLs.
    """
    api_key = _get_api_key(api_key)

    with _create_session(api_key) as session:
        url = '{}/download-request'.format(USGS_API)
        payload = payloads.download_request(dataset, entity_id, product_id)
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)

    return response

def dataset_search(dataset=None, catalog=None, ll=None, ur=None, start_date=None, end_date=None, api_key=None):
    api_key = _get_api_key(api_key)

    with _create_session(api_key) as session:
        url = '{}/dataset-search'.format(USGS_API)
        payload = payloads.dataset_search(
            dataset=dataset, catalog=catalog, start_date=start_date,
            end_date=end_date, ll=ll, ur=ur)
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)

    return response

def login(username, token, save=True):
    """
    Log in, creating a temporary API key and optionally storing it for later use.

    :param str username: Username of the USGS account to log in with.
    :param str token: Application Token of the USGS account to log in with.
    :param bool save: If true, the API key will be stored in a local file (~/.usgs)
        until `api.logout` is called to remove it. The stored key will be used by
        other functions to authenticate requests whenever an API key is not explicitly
        provided.
    """
    url = '{}/login-token'.format(USGS_API)
    payload = payloads.login(username, token)

    with _create_session(api_key=None) as session:
        created = datetime.now().isoformat()
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)

    api_key = response["data"]

    if api_key is None:
        raise USGSError(response.get("errorMessage", "Authentication failed"))

    if save:
        with open(TMPFILE, "w") as f:
            json.dump({
                "apiKey": api_key,
                "created": created
            }, f)

    return response

def logout():
    """
    Log out by deactivating and removing the stored API key, if one exists.
    """
    if not os.path.exists(TMPFILE):
        return

    url = '{}/logout'.format(USGS_API)

    with _create_session(api_key=None) as session:
        r = session.post(url)

    response = r.json()

    try:
        _check_for_usgs_error(response)
    except USGSAuthExpiredError:
        pass

    os.remove(TMPFILE)

    return response

def scene_metadata(dataset, entity_id, api_key=None):
    """
    Request metadata for a given scene in a USGS dataset.

    :param str dataset:
    :param str entity_id:
    :param str api_key:
    """
    api_key = _get_api_key(api_key)

    url = '{}/scene-metadata'.format(USGS_API)
    payload = payloads.scene_metadata(dataset, entity_id)

    with _create_session(api_key) as session:
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)
    return response


def scene_search(dataset,
        max_results=5000, metadata_type=None,
        start_date=None, end_date=None,
        ll=None, ur=None,
        lat=None, lng=None, distance=100,
        where=None, starting_number=1, sort_order="DESC", api_key=None):
    """
    :param dataset:
        USGS dataset (e.g. EO1_HYP_PUB, LANDSAT_8)
    :param lat:
        Latitude
    :param lng:
        Longitude
    :param distance:
        Distance in meters used to for a radial search
    :param ll:
        Dictionary of longitude/latitude coordinates for the lower left corner
        of a bounding box search. e.g. { "longitude": 0.0, "latitude": 0.0 }
    :param ur:
        Dictionary of longitude/latitude coordinates for the upper right corner
        of a bounding box search. e.g. { "longitude": 0.0, "latitude": 0.0 }
    :param start_date:
        Start date for when a scene has been acquired
    :param end_date:
        End date for when a scene has been acquired
    :where:
        Dictionary representing key/values for finer grained conditional
        queries. Only a subset of metadata fields are supported. Available
        fields depend on the value of `dataset`, and maybe be found by
        submitting a dataset_filters query.
    :max_results:
        Maximum results returned by the server
    :starting_number:
        Starting offset for results of a query.
    :sort_order:
        Order in which results are sorted. Ascending or descending w.r.t the acquisition date.
    :api_key:
        API key for EROS. Required for searching.
    """
    api_key = _get_api_key(api_key)

    with _create_session(api_key) as session:
        url = '{}/scene-search'.format(USGS_API)
        payload = payloads.scene_search(
            dataset, max_results=max_results, metadata_type=metadata_type,
            start_date=start_date, end_date=end_date,
            ll=ll, ur=ur, lat=lat, lng=lng, distance=distance, where=where,
            starting_number=starting_number)
        r = session.post(url, payload)

    response = r.json()

    _check_for_usgs_error(response)

    return response
