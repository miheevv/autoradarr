# -*- coding: utf-8 -*-
import os

import mongomock
import pymongo
import pytest
import requests
from autoradarr.autoradarr import (
    convert_imdb_in_radarr,
    filter_by_detail,
    filter_in_db,
    filter_in_radarr,
    filter_regular_result,
    get_db,
    get_imdb_data,
    get_radarr_data,
    get_tmdbid_by_imdbid,
    main,
    mark_filtred_in_db,
    necessary_fields_for_radarr,
    set_root_folders_by_genres,
)

db_host = os.environ.get('AUTORADARR_DB_HOST')
DB_NAME = 'autoradarr'
db_user = os.environ.get('AUTORADARR_DB_USERNAME')
db_password = os.environ.get('AUTORADARR_DB_PASSWORD')


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


@pytest.mark.parametrize((('newfilms'), ('expected')), [
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


@pytest.mark.parametrize((('film_in_db'), ('newfilms'), ('expected')), [
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
    db_client = mongomock.MongoClient()
    db = db_client.db
    collection = db.films
    collection.insert_many(film_in_db)   # If persist in db

    assert filter_in_db(db, newfilms, 'id') == expected


def test_get_imdb_data_from_site():
    ''' Test 'details' param from 'imdb-api.com' '''

    r = get_imdb_data(requests.session(), 'details', 'tt7979580')
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


def test_get_radarr_data_get_movie(requests_mock):
    url = os.environ.get('RADARR_URL') + '/api/v3/movie?apiKey=' + \
        os.environ.get('RADARR_APIKEY')
    requests_mock.get(url, text='tt7979580', status_code=200)
    assert get_radarr_data(requests.session(), 'get_movie').text == 'tt7979580'


def test_get_radarr_data_add_movie(requests_mock):
    url = os.environ.get('RADARR_URL') + '/api/v3/movie?apiKey=' + \
        os.environ.get('RADARR_APIKEY')
    requests_mock.post(url, text='tt7979580', status_code=201)
    assert get_radarr_data(requests.session(),
                           'add_movie',
                           api_json={'a': 'b'}).text == 'tt7979580'


def test_get_radarr_data_fail(requests_mock):
    url = os.environ.get('RADARR_URL') + '/api/v3/movie?apiKey=' + \
        os.environ.get('RADARR_APIKEY')
    requests_mock.get(url, text='tt7979580', status_code=300)
    assert get_radarr_data(requests.session(), 'get_movie') is None
    requests_mock.post(url, text='tt7979580', status_code=301)
    assert get_radarr_data(requests.session(),
                           'add_movie',
                           api_json={'a': 'b'}) is None


@pytest.mark.parametrize((('film_in_db'),
                          ('imdbid'),
                          ('title'),
                          ('persist_in_radarr'),
                          ('expected')), [
    (
        [
            {'imdbId': 'tt180'},        # film in db
            {'imdbId': 'tt8080'},
            {'imdbId': 'tt8'}

        ],
        'tt180',
        'tt180 title',
        0,
        False
    ),
    (
        [
            {'imdbId': 'tt180'},        # film in db
            {'imdbId': 'tt8080'},
            {'imdbId': 'tt8'}

        ],
        'tt170',
        'tt170 title',
        1,
        True
    ),
    (
        [
            {'imdbId': 'tt180'}        # film in db

        ],
        'tt170',
        'tt170 title',
        0,
        True
    )
])
def test_mark_filtred_in_db(film_in_db, imdbid, title, persist_in_radarr, expected):
    db_client = mongomock.MongoClient()
    db = db_client.db
    collection = db.films
    collection.insert_many(film_in_db)   # If persist in db
    assert mark_filtred_in_db(db, imdbid, title, persist_in_radarr) == expected
    if expected:
        film = collection.find_one({'imdbId': imdbid})
        assert film['originalTitle'] == title
        assert film['added']
        if persist_in_radarr == 1:
            assert film['persistInRadarr'] == 1
        else:
            assert film['filtred'] == 1


def test_filter_in_radarr(mocker):
    mocker.patch('autoradarr.autoradarr.get_radarr_data', return_value=True)
    # imdbid_list in filter_in_radarr:
    mocker.patch('autoradarr.autoradarr.get_radarr_imdbid_list',
                 return_value=['tt180', 'tt190'])
    db_client = mongomock.MongoClient()
    db = db_client.db
    newfilms = [{'id': 'tt180', 'title': 'Title'},
                {'id': 'tt170', 'title': 'Title2'}]
    expected = [{'id': 'tt170', 'title': 'Title2'}]
    result = filter_in_radarr(requests.session(), db, newfilms, 'id', 'title')
    assert result == expected
    film_in_db = db.films.find_one({'imdbId': 'tt180'})
    assert film_in_db['imdbId'] == 'tt180'
    assert film_in_db['originalTitle'] == 'Title'

    # Test empty return
    mocker.patch('autoradarr.autoradarr.get_radarr_imdbid_list',
                 return_value=['tt180', 'tt190', 'tt170'])
    assert filter_in_radarr(requests.session(), db, newfilms, 'id', 'title') == []


def test_filter_in_radarr_fail(mocker):
    mocker.patch('autoradarr.autoradarr.get_radarr_data', return_value=None)
    # imdbid_list in filter_in_radarr:
    newfilms = [{'id': 'tt180', 'title': 'Title'},
                {'id': 'tt170', 'title': 'Title2'}]
    db_client = mongomock.MongoClient()
    db = db_client.db
    assert filter_in_radarr(requests.session(), db, newfilms, 'id', 'title') == newfilms


def test_set_root_folders_by_genres():
    radarr_root_animations = os.environ.get('RADARR_ROOT_ANIMATIONS')
    film = {'fullTitle': 'Normal Full Title (2021)'}
    genres = ['Action', 'Animation']
    expected = {'fullTitle': 'Normal Full Title (2021)',
                'rootFolderPath': radarr_root_animations,
                'folderName': radarr_root_animations + '/Normal Full Title (2021)'}
    assert set_root_folders_by_genres(film, genres) == expected

    film = {'fullTitle': '%Normal-Full\t\n\r\f\vTitle_ (2021)'}
    expected = {'fullTitle': '%Normal-Full\t\n\r\f\vTitle_ (2021)',
                'rootFolderPath': radarr_root_animations,
                'folderName': radarr_root_animations + '/Normal-Full-Title_ (2021)'}
    assert set_root_folders_by_genres(film, genres) == expected

    radarr_root_other = os.environ.get('RADARR_ROOT_OTHER')
    genres = ['Action', 'Crime']
    film = {'fullTitle': ' %/Normal-Full\t/Title_  (2021)_  '}
    expected = {'fullTitle': ' %/Normal-Full\t/Title_  (2021)_  ',
                'rootFolderPath': radarr_root_other,
                'folderName': radarr_root_other + '/Normal-Full-Title_ (2021)_'}
    assert set_root_folders_by_genres(film, genres) == expected


def test_set_root_folders_by_genres_fail():
    with pytest.raises(Exception, match='Directory name can\'t be empty'):
        set_root_folders_by_genres({'fullTitle': ' %^$&%  Ё  '}, ['Action'])


def test_filter_by_detail(requests_mock):
    url1 = 'https://imdb-api.com/ru/API/Title/' + os.environ.get('IMDB_APIKEY') + '/tt7979580'
    requests_mock.get(url1, json={'genres': 'Action, Adventure'})
    url2 = 'https://imdb-api.com/ru/API/Title/' + os.environ.get('IMDB_APIKEY') + '/tt170'
    requests_mock.get(url2, json={'genres': 'Action, Drama'})
    url3 = 'https://imdb-api.com/ru/API/Title/' + os.environ.get('IMDB_APIKEY') + '/tt190'
    requests_mock.get(url3, json={'genres': 'Drama'})
    newfilms = [{'id': 'tt7979580', 'imDbRating': '6.9', 'title': 'Title1', 'fullTitle': '1'},
                {'id': 'tt170', 'imDbRating': '7', 'title': 'Title2', 'fullTitle': '2'},
                {'id': 'tt190', 'imDbRating': '6.9', 'title': 'Title3', 'fullTitle': '3'}]

    db_client = mongomock.MongoClient()
    db = db_client.db
    result = filter_by_detail(requests.session(), db, newfilms)

    assert len(result) == 2
    assert result[0]['id'] == 'tt7979580'
    assert result[1]['id'] == 'tt170'

    # mark_filtred_in_db
    assert db.films.find_one({'imdbId': 'tt190'})['imdbId'] == 'tt190'


def test_filter_by_detail_fail(mocker):
    mocker.patch('autoradarr.autoradarr.get_imdb_data', return_value=None)
    # imdbid_list in filter_in_radarr:
    newfilms = [{'id': 'tt180', 'title': 'Title'},
                {'id': 'tt170', 'title': 'Title2'}]
    db_client = mongomock.MongoClient()
    db = db_client.db
    assert filter_by_detail(requests.session(), db, newfilms) == []


@pytest.mark.parametrize((('newfilms'), ('expected')), [
    (
        [
            {'title': 'Title1', 'id': 'tt180', 'year': '2019',
             'folderName': '/root/folder', 'rootFolderPath': '/root'},
            {'title': 'Title2', 'id': 'tt8080', 'year': '2021',
             'folderName': '/root/folder2', 'rootFolderPath': '/root'}
        ],
        [
            {'originalTitle': 'Title1', 'imdbId': 'tt180', 'year': 2019,
             'folderName': '/root/folder', 'rootFolderPath': '/root'},
            {'originalTitle': 'Title2', 'imdbId': 'tt8080', 'year': 2021,
             'folderName': '/root/folder2', 'rootFolderPath': '/root'}
        ]
    ),
    (
        [
            {'title': 'Title 1', 'id': 'tt180', 'year': '2033',
             'folderName': '/root/folder-(3)', 'rootFolderPath': '/root'}
        ],
        [
            {'originalTitle': 'Title 1', 'imdbId': 'tt180', 'year': 2033,
             'folderName': '/root/folder-(3)', 'rootFolderPath': '/root'}
        ]
    )
])
def test_convert_imdb_in_radarr(newfilms, expected):
    assert convert_imdb_in_radarr(newfilms) == expected


def test_get_tmdbid_by_imdbid():
    assert get_tmdbid_by_imdbid(requests.session(), 'tt7979580') == 501929


def test_get_tmdbid_by_imdbid_fail():
    assert get_tmdbid_by_imdbid(requests.session(), 'tt70') == 0


def test_necessary_fields_for_radarr():
    film = {}
    film['folderName'] = '/folder'
    film['originalTitle'] = 'Title 1'
    film['imdbId'] = 'tt7979580'
    excepted = film
    excepted['path'] = film['folderName']
    excepted['title'] = film['originalTitle']
    excepted['qualityProfileId'] = int(os.environ.get('RADARR_DEFAULT_QUALITY'))
    excepted['tmdbId'] = 501929
    assert necessary_fields_for_radarr(requests.session(), film) == excepted


def test_main_pass(mocker):
    newfilms = [
        {'fullTitle': 'Mortal Kombat (2021)'},
        {'fullTitle': 'I Care a Lot (2020)'}
    ]
    mocker.patch('autoradarr.autoradarr.get_new_films', return_value=newfilms)
    mocker.patch('autoradarr.autoradarr.add_to_radarr', return_value=len(newfilms))
    assert main() == len(newfilms)


def test_main_db_fail(mocker):
    mocker.patch('autoradarr.autoradarr.get_db', return_value=None)
    assert main() is None
