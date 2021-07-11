# -*- coding: utf-8 -*-
'''Automatization for Radarr - Scanner for new good films.

Regulary insert into radarr new films links from IMDB, Kinopoisk, etc.

Films DB structure:
films: originalTitle, imdbId, folderName, year, filtred, persistInRadarr, added

       IMDB_rate, IMDB_count,
       added_datetime, torrent_url?, bad_torrent?, new (resently added)
       downloaded, to_delete (to delete on server),
       deleted (don't download in future again)
TODO
radarralice.py

'''
import time
import datetime
# from pprint import pprint
import locale
import os
import re
import sys
import unicodedata
from typing import Any, Optional, Union

import pymongo
# from pymongo.common import VALIDATORS
import requests
from pymongo.database import Database
from pymongo.mongo_client import MongoClient
from requests.models import Response
from requests.sessions import Session

# import json


def get_db(host: str, dbname: str, user: str, passw: str) -> Optional[Database]:
    ''' Connect to mongo and return client db object '''

    try:
        db_client: MongoClient = pymongo.MongoClient(host,
                                                     username=user,
                                                     password=passw,
                                                     authSource=dbname)
    # Force connection on a request as the connect=True parameter of MongoClient
    # seems to be useless here
        db_client.server_info()

    except pymongo.errors.ServerSelectionTimeoutError as err:
        print("Could not connect to server '",
              host, "' with error: ",
              err, file=sys.stderr)
        return None
    except pymongo.errors.OperationFailure as err:
        print("Could not get database '",
              dbname, "' to server '",
              host, "' with error: ",
              err, file=sys.stderr)
        return None
    return db_client[dbname]


def filter_regular_result(newfilms: Any,
                          rating_field: str,
                          rating_count_field: str,
                          year_field: str,
                          current_year: int = 0) -> Any:
    ''' Filter regular list (MostPopularMovies, news, daily or other) of
        new films and return json to add '''

    year: int = current_year
    if not year:
        year = datetime.datetime.utcnow().year

    notfiltred_films: Any = []
    for item in newfilms:
        removeflag: bool = False
        if (rating_field not in item) or \
           (not item[rating_field]) or \
           (float(item[rating_field]) < 6.5):
            removeflag = True
        if (rating_count_field not in item) or \
           (not item[rating_count_field]) or \
           (int(item[rating_count_field]) < 5000):
            removeflag = True
        try:
            if (year_field not in item) or \
               (not item[year_field]) or \
               (int(item[year_field]) < year - 1):
                removeflag = True
        # Year format incorrect - next film
        except ValueError:
            continue
        if not removeflag:
            notfiltred_films.append(item)

    return notfiltred_films


def filter_in_db(db: Database, newfilms: Any, imdbid_field_name: str) -> Any:
    ''' Remove film if persist in DB '''

    films: Any = db.get_collection('films')

    notfiltred_films: Any = []
    for item in newfilms:
        removeflag: bool = False
        if films.find_one({'imdbId': item[imdbid_field_name]}):
            removeflag = True
        if not removeflag:
            notfiltred_films.append(item)

    return notfiltred_films


def get_imdb_data(client: Session,
                  data_type: str,
                  param: str = '') -> Optional[Response]:
    ''' Get imdb api data, data_type - 'popular', 'details'. param - imdb id, etc. '''

    imdb_apikey: Optional[str] = os.environ.get('IMDB_APIKEY')
    if not imdb_apikey:
        print('Could not get env IMDB_APIKEY', file=sys.stderr)
        raise Exception('Could not get env IMDB_APIKEY')

    headers: dict[str, str] = {'User-Agent': 'Mozilla/5.0'}
    if data_type == 'popular':
        r: Response = client.get('https://imdb-api.com/ru/API/MostPopularMovies/' +
                                 imdb_apikey, headers=headers)
    if data_type == 'details':
        r = client.get('https://imdb-api.com/ru/API/Title/' + imdb_apikey +
                       '/' + param, headers=headers)

    if r.status_code == 200:
        return r

    return None


def get_radarr_data(client: Session,
                    data_type: str,
                    api_json: Any = '') -> Optional[Response]:
    ''' Get radarr data, data_type - 'get_movie', 'add_movie'.

        Prefix - json film to add, etc.

    '''

    radarr_apikey: Optional[str] = os.environ.get('RADARR_APIKEY')
    if not radarr_apikey:
        print('Could not get env RADARR_APIKEY', file=sys.stderr)
        raise Exception('Could not get env RADARR_APIKEY')
    radarr_url: Optional[str] = os.environ.get('RADARR_URL')
    if not radarr_url:
        print('Could not get env RADARR_URL', file=sys.stderr)
        raise Exception('Could not get env RADARR_URL')

    headers: dict[str, str] = {'User-Agent': 'Mozilla/5.0'}
    if data_type == 'get_movie':
        r: Response = client.get(radarr_url + '/api/v3/movie?apiKey=' +
                                 radarr_apikey, headers=headers)
        if r.status_code == 200:
            return r
    if data_type == 'add_movie':
        r = client.post(radarr_url + '/api/v3/movie?apiKey=' +
                        radarr_apikey, json=api_json, headers=headers)
        if r.status_code == 201:
            return r

    return None


def get_radarr_imdbid_list(r: Response) -> 'list[str]':
    imdb_list: list[str] = []
    for item in r.json():
        if 'imdbId' not in item:
            imdb_list.append({'imdbId': '0'})
        elif item['imdbId']:
            imdb_list.append(item['imdbId'])
    return imdb_list


def mark_filtred_in_db(db: Database,
                       imdbid: str,
                       title: str,
                       persist_in_radarr: int = 0) -> bool:
    ''' Mark film 'filtred' in DB and return True.

        If already founded in DB - return False

    '''

    films: Any = db.get_collection('films')

    if films.find_one({'imdbId': imdbid}):
        return False

    if persist_in_radarr == 1:
        films.insert_one({'imdbId': imdbid, 'originalTitle': title,
                          'persistInRadarr': persist_in_radarr,
                          'added': datetime.datetime.utcnow()})
    else:
        films.insert_one({'imdbId': imdbid, 'originalTitle': title, 'filtred': 1,
                          'added': datetime.datetime.utcnow()})

    return True


def filter_in_radarr(client: Session,
                     db: Database,
                     newfilms: Any,
                     imdbid_field_name: str,
                     title_field_name: str) -> Any:
    ''' Filter if film already persist in Radarr '''

    r: Optional[Response] = get_radarr_data(client, 'get_movie')
    if r is None:
        return newfilms
    imdbid_list: list[str] = get_radarr_imdbid_list(r)

    notfiltred_films: Any = []
    for item in newfilms:
        removeflag: bool = False
        if item[imdbid_field_name] in imdbid_list:
            removeflag = True
            mark_filtred_in_db(db, item[imdbid_field_name], item[title_field_name], 1)
        if not removeflag:
            notfiltred_films.append(item)

    return notfiltred_films


def normalize_filepath(filepath: str) -> str:
    value: str = str(filepath)
    # TODO get replace format from env
    value = value.replace(':', ' - ')   # Radarr format
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^-()\w\s]', '', value)
    return re.sub(r'[-\t\n\r\f\v]+', '-', value).strip('-_').replace('  ', ' ').strip()


def set_root_folders_by_genres(film: Any, genres: Any) -> Any:
    ''' Sort in radarr root folders by genres '''

    # TODO parse many types of genres path from env
    radarr_root_other: str = str(os.environ.get('RADARR_ROOT_OTHER'))
    radarr_root_animations: str = str(os.environ.get('RADARR_ROOT_ANIMATIONS'))
    # TODO getformat from radarr template (from env?) -
    # '{Movie Title} ({Release Year})'

    if normalize_filepath(film['fullTitle']) == '':
        raise Exception('Directory name can\'t be empty')

    film['rootFolderPath'] = radarr_root_other
    film['folderName'] = radarr_root_other + '/' + normalize_filepath(film['fullTitle'])
    if 'Animation' in genres:
        film['rootFolderPath'] = radarr_root_animations
        film['folderName'] = radarr_root_animations + '/' + normalize_filepath(film['fullTitle'])
    return film


def filter_by_detail(client: Session,
                     db: Database,
                     newfilms: Any,
                     rating_type: str = 'imdb-api.com') -> Any:
    ''' Filter by film's genres, etc. '''

    accepted_genres: set[str] = {'Action', 'Adventure', 'Sci-Fi', 'Animation', 'Comedy'}
    bad_genres: set[str] = {'Drama'}
    notfiltred_films: Any = []

    for item in newfilms:
        removeflag: bool = True
        genres: Any = []
        rating: float = 0
        if rating_type == 'imdb-api.com':
            r: Union[Response, None] = get_imdb_data(client, 'details', item['id'])
            # Skip film - don't add to notfiltred and NOT filter it in db.
            if r is None:
                continue
            genres = r.json()['genres'].split(', ')
            rating = float(item['imDbRating'])

        if set.intersection(accepted_genres, genres):
            removeflag = False  # if accepted_genres persist
        if set.intersection(bad_genres, genres) and (rating < 7):
            removeflag = True  # if bad_genres persist and low rating

        if not removeflag:
            new_film: Any = set_root_folders_by_genres(item, genres)
            notfiltred_films.append(new_film)
        else:
            # Next scan will ignore this film
            mark_filtred_in_db(db, item['id'], item['title'])

    return notfiltred_films


def filter_imdb_films(client: Session, db: Database, newfilms: Any) -> Any:
    ''' Filter: first (new or popular films list) result (by rating & year,
        etc), if not persist in DB, film's detail (by genres or other) '''

    filtred: Any = filter_regular_result(newfilms, 'imDbRating', 'imDbRatingCount', 'year')
    filtred = filter_in_db(db, filtred, 'id')
    filtred = filter_in_radarr(client, db, filtred, 'id', 'title')
    filtred = filter_by_detail(client, db, filtred)
    return filtred


def convert_imdb_in_radarr(newfilms: Any) -> 'list[dict[str, Union[str, int]]]':
    ''' return newfilms in radarr api format (list[dict]) '''

    new_radarr_films: list[dict[str, Union[str, int]]] = []
    for item in newfilms:
        new_radarr_films.append({
            'originalTitle': item['title'],
            'imdbId': item['id'],
            'year': int(item['year']),
            'folderName': item['folderName'],
            'rootFolderPath': item['rootFolderPath']
        })
    return new_radarr_films


def get_new_from_imdb(client: Session, db: Database) -> 'list[dict[str, Union[str, int]]]':
    ''' Get new films from imdb-api.com.

        1. Get new films
        2. NOT ADD film if old, allready persist in DB or marked_filtred, etc.
        3. Convert in radarr format.

    '''

    radarr_newfilms: list[dict[str, Union[str, int]]] = []
    r: Union[Response, None] = get_imdb_data(client, 'popular')
    if r is None:
        return radarr_newfilms
    newfilms: Any = filter_imdb_films(client, db, r.json()['items'])
    radarr_newfilms = convert_imdb_in_radarr(newfilms)
    return radarr_newfilms


def get_new_films(client: Session, db: Database) -> 'list[dict[str, Union[str, int]]]':
    ''' Get new films from some kind of rating providers.

        Get_new_from_imdb, get_new_from_kinopoisk (TODO) if enabled (TODO).
        Geters must return fields IN RADARR format.
        schema: get_new_films - get_new_from_imdb|kinopoisk|etc -
                filter_imdb|kinopoisk|etc - filter_*.

    '''

    newfilms: list[dict[str, Union[str, int]]] = get_new_from_imdb(client, db)
    # TODO get_new_from_kinopoisk(client, db)
    return newfilms


def get_tmdbid_by_imdbid(client: Session, imdbId: str) -> int:
    ''' Get tmdbId by imdbId useing TMDB API.

        https://developers.themoviedb.org/3/find/find-by-id
    '''

    tmdb_apikey: str = str(os.environ.get('TMDB_APIKEY'))
    if not tmdb_apikey:
        print('Could not get env TMDB_APIKEY', file=sys.stderr)
        raise Exception('Could not get env TMDB_APIKEY')

    headers: dict[str, str] = {'User-Agent': 'Mozilla/5.0'}
    r: Response = client.get('https://api.themoviedb.org/3/find/' + imdbId +
                             '?api_key=' + tmdb_apikey +
                             '&language=en-US&external_source=imdb_id', headers=headers)

    if (r.status_code == 200) and (r.json()['movie_results']):
        return r.json()['movie_results'][0]['id']
    return 0


def necessary_fields_for_radarr(client: Session,
                                film: 'dict[str, Union[str, int]]') -> 'dict[str, Union[str, int]]':
    ''' Add necessary fields for radarr import '''

    radarr_film: 'dict[str, Union[str, int]]' = film
    radarr_film['qualityProfileId'] = int(str(os.environ.get('RADARR_DEFAULT_QUALITY')))
    radarr_film['path'] = film['folderName']
    radarr_film['title'] = film['originalTitle']
    radarr_film['tmdbId'] = get_tmdbid_by_imdbid(client, str(film['imdbId']))

    return radarr_film


def add_to_radarr(client: Session,
                  db: Database,
                  newfilms: 'list[dict[str, Union[str, int]]]') -> int:
    ''' Add new films to radarr and return count of added items '''

    r: Optional[Response] = None
    count: int = 0
    for item in newfilms:
        radarr_film: dict[str, Union[str, int]] = necessary_fields_for_radarr(client, item)
        r = get_radarr_data(client, 'add_movie', api_json=radarr_film)
        if r is not None:
            mark_filtred_in_db(db, str(radarr_film['imdbId']), str(radarr_film['originalTitle']))
            count = count + 1
    return count


# TODO validate_provider - from jsonschema import validate
# https://ru.stackoverflow.com/questions/939817/
# %D0%92%D0%B0%D0%BB%D0%B8%D0%B4%D0%B0%D1%86%D0%B8%D1%8F-json-
# %D0%B4%D0%B0%D0%BD%D0%BD%D1%8B%D1%85-%D0%B2-python


def main() -> Optional[int]:
    ''' Return count of added films or None if error '''
    locale.setlocale(locale.LC_ALL, '')
    print('Autoradarr has been started at {}'.format(datetime.datetime.utcnow()))

    # DB
    db_host: str = str(os.environ.get('AUTORADARR_DB_HOST'))
    DB_NAME: str = 'autoradarr'
    db_user: str = str(os.environ.get('AUTORADARR_DB_USERNAME'))
    db_password: str = str(os.environ.get('AUTORADARR_DB_PASSWORD'))

    # Prelogin into DB
    db: Database = get_db(db_host, DB_NAME, db_user, db_password)
    if not db:
        return None

    # Get new films
    client: Session = requests.session()
    newfilms: list[dict[str, Union[str, int]]] = get_new_films(client, db)

    # Add to Radarr
    count: int = add_to_radarr(client, db, newfilms)

    if count == 0:
        print('Can\'t find new films')
        return 0

    print('New films added into DB:')
    for film in newfilms:
        if 'fullTitle' in film:
            print(film['fullTitle'])
        elif 'title' in film:
            print(film['title'])
    return count


if __name__ == '__main__':
    while True:
        main()
        # day * hour * min * sec
        time.sleep(1 * 24 * 60 * 60)
