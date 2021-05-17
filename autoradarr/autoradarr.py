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
myimdblist.py - list for radarr
imdbworker.py - (on server to add torrent url for download)??? radarr???, and delete old films
imdbalice.py

'''

import datetime
from pprint import pprint
import locale
import os
import re
# from urllib.request import Request, urlopen
import sys

import pymongo
import requests
import json
# from bs4 import BeautifulSoup


def get_db(host, dbname, user, passw):
    ''' Connect to mongo and return db object '''

    try:
        client = pymongo.MongoClient(host,
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


def filter_by_rating_year(newfilms, rating_field, rcount_field, year_field, current_year=0):
    ''' Filter new films and return list to add (with autoset filmfolders, etc. params) '''
    if not current_year:
        current_year = datetime.datetime.utcnow().year

    notfiltred_films = []
    for item in newfilms:
        removeflag = None
        if (rating_field not in item) or (not item[rating_field]) or (float(item[rating_field]) < 6.0):
            removeflag = 1
        if (rcount_field not in item) or (not item[rcount_field]) or (int(item[rcount_field]) < 5000):
            removeflag = 1
        if (year_field not in item) or (not item[year_field]) or (int(item[year_field]) < current_year-1):
            removeflag = 1

        if removeflag is None:
            notfiltred_films.append(item)

    return notfiltred_films


def filter_in_db(db, newfilms, title_field_name):
    '''Remove if film is persist in DB'''
    films = db.get_collection('films')

    notfiltred_films = []
    for item in newfilms:
        removeflag = None
        if films.find_one({title_field_name: item['title']}):
            removeflag = 1
        if removeflag is None:
            notfiltred_films.append(item)

    return notfiltred_films


def filter_imdb(client, db, newfilms):
    '''Filter: by rating & year, if not persist in DB, by genres'''
    filtred = filter_by_rating_year(newfilms, 'imDbRating', 'imDbRatingCount', 'year')
    filtred = filter_in_db(db, filtred, 'originalTitle')

    return filtred


def get_new_from_imdb(client, db):
    ''' Get new films from imdb-api.com:
        1. Convert fields in radarr format
        2. NOT ADD film if old, allready persist in DB or marked_filtred.
        '''

    imdb_apikey = os.environ.get('IMDB_APIKEY')
    if not imdb_apikey:
        print('Could not get env IMDB_APIKEY', file=sys.stderr)
        return

    headers = {'User-Agent': 'Mozilla/5.0'}
    r = client.get('https://imdb-api.com/ru/API/MostPopularMovies/' + imdb_apikey, headers=headers)
    newfilms = filter_imdb(client, db, r.json()['items'])
    return newfilms


def get_new_films(client, db):
    ''' Get new films from some kind of rating providers - get_new_from_imdb, get_new_from_kinopoisk (TODO) if enabled (TODO).
        Getters must return fields in raddarr format.
        schema: get_new_films - get_new_from_imdb - filter_imdb - imdb_film_info, mark_filtred and filter_categories'''

    #films_in_db = db.films
    #if not current_year:
    #    current_year = datetime.datetime.utcnow().year
    return get_new_from_imdb(client, db)


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
    db_host = os.environ.get('AUTORADARR_DB_HOST')
    DB_NAME = 'autoradarr'
    db_user = os.environ.get('AUTORADARR_DB_USERNAME')
    db_password = os.environ.get('AUTORADARR_DB_PASSWORD')

    # Prelogin into DB
    db = get_db(db_host, DB_NAME, db_user, db_password)
    if not db:
        return

    # Get new films (if not persist in db) from cinemate.cc
    client = requests.session()
    newfilms = get_new_films(client, db)
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
