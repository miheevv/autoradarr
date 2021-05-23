# -*- coding: utf-8 -*-
'''IMDB scanner

Regulary insert into radarr new films links from IMDB, Kinopoisk, etc.

Films DB structure:
films: title, originalTitle, imdbId, categories, date, countries, overview
       IMDB_rate, IMDB_count,
       added_datetime, torrent_url?, bad_torrent?, new (resently added)
       filmfolder (by default - 'films'), to_download, downloaded,
       to_delete (to delete on server),
       deleted (don't download in future again)
TODO
autoradarrlist.py ? - list for radarr if not using radarr api.
radarralice.py

'''

import datetime
from pprint import pprint
import locale
import os
import re
# from urllib.request import Request, urlopen
import sys

import pymongo
from pymongo.mongo_client import MongoClient
import requests
from typing import Any, Union
from requests.models import Response

from requests.sessions import Session
# import json
# from bs4 import BeautifulSoup


def get_db(host: str, dbname: str, user: str, passw: str) -> Union[MongoClient, None]:
    ''' Connect to mongo and return client db object '''

    try:
        client: Union[MongoClient, None] = pymongo.MongoClient(host,
                                                               username=user,
                                                               password=passw,
                                                               authSource=dbname)
    # Force connection on a request as the connect=True parameter of MongoClient
    # seems to be useless here
        client.server_info()

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
    return client[dbname]


def filter_regular_result(newfilms: Any, rating_field: str, rating_count_field: str, year_field: str, current_year: int = 0) -> Any:
    ''' Filter regular list (MostPopularMovies, new, daily or other) of new films and return json to add'''
    year: int = current_year
    if not year:
        year = datetime.datetime.utcnow().year

    notfiltred_films: Any = []
    for item in newfilms:
        removeflag: bool = False
        if (rating_field not in item) or (not item[rating_field]) or (float(item[rating_field]) < 6.5):
            removeflag = True
        if (rating_count_field not in item) or (not item[rating_count_field]) or (int(item[rating_count_field]) < 5000):
            removeflag = True
        if (year_field not in item) or (not item[year_field]) or (int(item[year_field]) < year-1):
            removeflag = True

        if not removeflag:
            notfiltred_films.append(item)

    return notfiltred_films


def filter_in_db(db: MongoClient, newfilms: Any, title_field_name: str) -> Any:
    ''' Remove if film is persist in DB '''

    films: Any = db.get_collection('films')

    notfiltred_films: Any = []
    for item in newfilms:
        removeflag: bool = False
        if films.find_one({title_field_name: item['title']}):
            removeflag = True
        if not removeflag:
            notfiltred_films.append(item)

    return notfiltred_films


def get_imdb_data(client: Session, data_type: str, param: str = '') -> Response:
    ''' Get imdb api data, data_type - 'popular', 'details'. param - imdb id, etc. '''
    imdb_apikey: str = os.environ.get('IMDB_APIKEY')
    if not imdb_apikey:
        print('Could not get env IMDB_APIKEY', file=sys.stderr)
        return

    headers: dict[str,str] = {'User-Agent': 'Mozilla/5.0'}
    if data_type == 'popular':
        return client.get('https://imdb-api.com/ru/API/MostPopularMovies/' + imdb_apikey, headers=headers)
    if data_type == 'details':
        return client.get('https://imdb-api.com/ru/API/Title/' + imdb_apikey + '/' + param, headers=headers)


def mark_filtred_in_db(db:MongoClient, id: str, title: str) -> None:
    films: Any = db.get_collection('films')
    films.insert_one({'id': id, 'title': title, 'filtred': 1, 'added': datetime.datetime.utcnow()})


def filter_by_detail(client: Session, db: MongoClient, newfilms: Any, rating_type:str = 'imdb-api.com') -> Any:
    ''' Filter by film's genres, etc. '''

    accepted_genres: set[str] = {'Action', 'Adventure', 'Sci-Fi', 'Animation', 'Comedy'}
    bad_genres: set[str] = {'Drama'}
    notfiltred_films: Any = []

    for item in newfilms:
        removeflag: bool = True
        genres: list[str] = []
        rating: float = 0
        if rating_type == 'imdb-api.com':
            r: Response = get_imdb_data(client, 'details', item['id'])
            genres = r.json()['genres'].split(', ')
            rating = float(item['imDbRating'])

        if set.intersection(accepted_genres, genres):
            removeflag = False  # if accepted_genres persist
        if set.intersection(bad_genres, genres) and (rating < 7):
            removeflag = True  # if bad_genres persist and low rating

        if not removeflag:
            notfiltred_films.append(item)
        else:
            mark_filtred_in_db(db, item['id'], item['title']) # next scan will ignore this film

    return notfiltred_films


def filter_imdb_films(client: Session, db: MongoClient, newfilms: Any) -> Any:
    ''' Filter: first (new or popular films list) result (by rating & year, etc), if not persist in DB, film's detail (by genres or other) '''

    filtred: Any = filter_regular_result(newfilms, 'imDbRating', 'imDbRatingCount', 'year')
    filtred = filter_in_db(db, filtred, 'originalTitle')
    filtred = filter_by_detail(client, db, filtred)
    return filtred


def convert_imdb_in_radarr(newfilms: Any) -> list:
    #TODO convert return in radarr api format list[dict]
    radarr_films: list[dict[Union[str, int]]] = []
    replace_map: dict[str] = {'originalTitle': 'title', 'imdbId':'id', 'year': 'year'}
    return replace_map

def get_new_from_imdb(client: Session, db: MongoClient) -> list:
    ''' Get new films from imdb-api.com:
        1. Convert fields in radarr format
        2. NOT ADD film if old, allready persist in DB or marked_filtred. '''

    r: Response = get_imdb_data(client, 'popular')
    newfilms: Any = filter_imdb_films(client, db, r.json()['items'])
    radarr_newfilms = convert_imdb_in_radarr(newfilms)
    return radarr_newfilms

def get_new_films(client: Session, db: MongoClient) -> Any:
    ''' Get new films from some kind of rating providers - get_new_from_imdb, get_new_from_kinopoisk (TODO) if enabled (TODO).
        Geters must return fields in raddarr format.
        schema: get_new_films - get_new_from_imdb|kinopoisk|etc - filter_imdb|kinopoisk|etc - filter_*. '''

    newfilms: Any = get_new_from_imdb(client, db)
    return newfilms


#TODO get_film_info


#TODO get_trackers


#TODO
''' Add torrent url and mark it for download if right catagory
def add_torrurl_and_mark(client, films, usr, pwd):

    ret_films = []
    for i in range(len(films)):
        film_to_add = films[i]
        url = get_best_torrent_url(client, film_to_add, usr, pwd)
        if not url:
            continue    # Don't add if hasn't torrent url
        film_to_add['torrent_url'] = url
        film_to_add['filmfolder'] = 'films'
        if 'мультфильм' in film_to_add['categories']:
            film_to_add['filmfolder'] = 'mults'
            film_to_add['to_download'] = 1
        if ('боевик' in film_to_add['categories']) or ('фантастика' in film_to_add['categories']):
            film_to_add['to_download'] = 1
        film_to_add['added_datetime'] = datetime.datetime.utcnow()
        ret_films.append(film_to_add)
    return ret_films
'''

def main():
    ''' Return number of added films of None if error '''

    locale.setlocale(locale.LC_ALL, '')
    # DB
    db_host: str = os.environ.get('AUTORADARR_DB_HOST')
    DB_NAME: str = 'autoradarr'
    db_user: str = os.environ.get('AUTORADARR_DB_USERNAME')
    db_password: str = os.environ.get('AUTORADARR_DB_PASSWORD')

    # Prelogin into DB
    db: MongoClient = get_db(db_host, DB_NAME, db_user, db_password)
    if not db:
        return

    # Get new films (if not persist in db) from cinemate.cc
    client: Session = requests.session()
    newfilms: list[str] = get_new_films(client, db)
    pprint(newfilms)
    # Get film's info for every film
    #for item in newfilms:
    #    film_info = get_film_info(client, item)
    #    item.update(film_info)
    #newfilms = filter_films(newfilms)
    #newfilms = add_torrurl_and_mark(client, newfilms, cinemate_user, cinemate_password)
    #if not newfilms:
    #    print('Can\'t find new films')
    #    return 0
    # pprint(newfilms)

    # Add new films to db
    #films = db.get_collection('films')
    #if films and db and newfilms:
    #    result = films.insert_many(newfilms)
    #if not result.inserted_ids:
    #    print('Can\'t added any new films to DB')
    #    return

    #print('New films added into DB:')
    #for film in newfilms:
    #    print(film['name'], film['date'].strftime('(%d %b %Y)'), ', '.join(film['categories']))
    #return len(result.inserted_ids)


if __name__ == '__main__':
    main()
