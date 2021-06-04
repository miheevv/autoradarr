# -*- coding: utf-8 -*-
import codecs
import datetime
import os

import mongomock
import pymongo
import pytest
import pytest_mock
import requests
import requests_mock
from autoradarr.autoradarr import (
    filter_in_db,
    filter_regular_result,
    get_db,
    get_new_films,
    get_imdb_data
)

db_host = os.environ.get('AUTORADARR_DB_HOST')
DB_NAME = 'autoradarr'
db_user: str = os.environ.get('AUTORADARR_DB_USERNAME')
db_password: str = os.environ.get('AUTORADARR_DB_PASSWORD')


@pytest.fixture()
def dbconnection():
    pymongo_client = pymongo.MongoClient(db_host,
                                         username=db_user,
                                         password=db_password,
                                         authSource=DB_NAME)

    yield pymongo_client

    pymongo_client.close()


def test_get_db_pass(dbconnection):
    ''' Testing returned db object, insert and delete object '''

    assert get_db(db_host, DB_NAME, db_user, db_password) == dbconnection[DB_NAME]
    # create and remove object in db
    inserted_id = dbconnection[DB_NAME].test.insert_one({"test": "test"}).inserted_id
    assert dbconnection[DB_NAME].test.delete_one({'_id': inserted_id})


def test_get_db_fail():
    assert get_db('incorrect dbname', DB_NAME, db_user, db_password) is None
    assert get_db(db_host, DB_NAME, 'bad_user', db_password) is None
    assert get_db(db_host, DB_NAME, db_user, 'bad_password') is None


@pytest.mark.parametrize(('newfilms, expected'), [
    (
        [
            {'year': '2021', 'imDbRating': '5.9', 'imDbRatingCount': '952'},
            {'year': '2020', 'imDbRating': '6.5', 'imDbRatingCount': '27165'},
            {'year': '2021', 'imDbRating': '7.3', 'imDbRatingCount': '4999'},
            {'year': '2021', 'imDbRating': '6.4', 'imDbRatingCount': '5000'}
        ],
        [
            {'year': '2020', 'imDbRating': '6.5', 'imDbRatingCount': '27165'}
        ]
    ),
    (
        [
            {'year': '2019', 'imDbRating': '6.5', 'imDbRatingCount': '5000'},
            {'year': '2021', 'imDbRating': '7.3', 'imDbRatingCount': '4999'},
            {'imDbRating': '7.3', 'imDbRatingCount': '5000'},
            {'year': '2021', 'imDbRatingCount': '5000'},
            {'year': '2021', 'imDbRating': '7.3'},
            {'year': '2021', 'imDbRating': '6.4', 'imDbRatingCount': '5000'}
        ],
        []
    )
])
def test_filter_regular_result(newfilms, expected):
    assert expected == filter_regular_result(newfilms, 
                                             'imDbRating', 
                                             'imDbRatingCount', 
                                             'year', 
                                             2021)


@pytest.mark.parametrize(('film_in_db, newfilms, expected'), [
    (
        [{'imdbId': 'tt7979580'}],    # film in db
        [
            {'id': 'tt7979580'},    # newfilms 
            {'id': 'tt7979581'},
            {'id': 'tt79795801'}
        ],
        [
            {'id': 'tt7979581'},    # expected
            {'id': 'tt79795801'}
        ]
    ),
    (
        [
            {'imdbId': 'tt180'},        # film in db
            {'imdbId': 'tt8080'},
            {'imdbId': 'tt8'}

        ],         
        [
            {'id': 'tt180'},        # newfilms 
            {'id': 'tt8080'},
            {'id': 'tt8'}
        ],
        []                          # expected
    )
])
def test_filter_in_db(newfilms, film_in_db, expected):
    # breakpoint()
    db_client = mongomock.MongoClient()
    db = db_client.db
    collection = db.films
    collection.insert_many(film_in_db)   # If persist in db

    assert filter_in_db(db, newfilms, 'id') == expected


def test_get_imdb_data_from_site():
    ''' Test 'details' param from 'imdb-api.com' '''

    r = get_imdb_data(requests.session(), 'details', 'tt7979580')
    r.json()['id']
    assert r.json()['id'] == 'tt7979580'    


def test_get_imdb_data_mock(requests_mock):
    ''' Test 'popular' param from requests_mock '''

    url = 'https://imdb-api.com/ru/API/MostPopularMovies/' + os.environ.get('IMDB_APIKEY')
    requests_mock.get(url, text='tt7979580', status_code=200)
    assert get_imdb_data(requests.session(), 'popular').text == 'tt7979580'   


def test_get_imdb_data_fail(requests_mock):
    url = 'https://imdb-api.com/ru/API/MostPopularMovies/' + os.environ.get('IMDB_APIKEY')
    requests_mock.get(url, text='tt7979580', status_code=300)
    assert get_imdb_data(requests.session(), 'popular') is None   


#TODO test_get_radarr_data


'''

def test_datestr_to_date_fail():
    with pytest.raises(ValueError):
        datestr_to_date('1 мартобря 2016')
    with pytest.raises(AttributeError):
        datestr_to_date('восьмого марта 2025')
    with pytest.raises(ValueError):
        datestr_to_date('31 февраля 2025')
    with pytest.raises(ValueError):
        datestr_to_date('2015 февраля 13')
    with pytest.raises(AttributeError):
        datestr_to_date('12.12.2012')
    with pytest.raises(AttributeError):
        datestr_to_date('февраля 2025')
    with pytest.raises(AttributeError):
        datestr_to_date('1 мая')


def test_main_cinemate_fail(mocker):
    mocker.patch('autocinemator.cinematorprobe.loginin_cinemate', return_value=None)
    assert main() is None


def test_main_db_fail(mocker):
    mocker.patch('autocinemator.cinematorprobe.loginin_cinemate', return_value=None)
    mocker.patch('autocinemator.cinematorprobe.get_db', return_value=True)
    assert main() is None


def test_main_no_films_pass(mocker):
    mocker.patch('autocinemator.cinematorprobe.loginin_cinemate', return_value=True)
    mocker.patch('autocinemator.cinematorprobe.get_db', return_value=True)
    mocker.patch('autocinemator.cinematorprobe.get_new_films', return_value=[])
    assert main() == 0


def test_main_add_to_db_fail(mocker):
    mocker.patch('autocinemator.cinematorprobe.loginin_cinemate', return_value=True)
    mocker.patch('autocinemator.cinematorprobe.get_new_films', return_value=[])
    newfilms = [
        {'name': 'Test Name', 'date': datetime.datetime.utcnow(),
         'categories': ['Test Category']},
        {'name': 'Test Name 2', 'date': datetime.datetime.utcnow(),
         'categories': ['Test Category 2']}
    ]
    mocker.patch('autocinemator.cinematorprobe.add_torrurl_and_mark', return_value=newfilms)

    class Col:
        inserted_ids = []

    films_col = Col()
    mocker.patch.object(pymongo.collection.Collection, 'insert_many', return_value=films_col)
    assert main() is None


def test_main_pass(mocker):
    mocker.patch('autocinemator.cinematorprobe.loginin_cinemate', return_value=True)
    mocker.patch('autocinemator.cinematorprobe.get_new_films', return_value=[])
    newfilms = [
        {'name': 'Test Name', 'date': datetime.datetime.utcnow(),
         'categories': ['Test Category']},
        {'name': 'Test Name 2', 'date': datetime.datetime.utcnow(),
         'categories': ['Test Category 2']}
    ]
    mocker.patch('autocinemator.cinematorprobe.add_torrurl_and_mark', return_value=newfilms)

    class Col:
        inserted_ids = ['1', '2']

    films_col = Col()
    mocker.patch.object(pymongo.collection.Collection, 'insert_many', return_value=films_col)
    assert main() == 2

'''
