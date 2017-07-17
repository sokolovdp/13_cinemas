import sys
import argparse
import time
import re
import random
import logging
from datetime import datetime
from collections import namedtuple

import requests
from bs4 import BeautifulSoup

HEADERS = {"USER-AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/59.0.3071.115 Safari/537.36",
           "ACCEPT": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
           "CONNECTION": "keep-alive",
           "ACCEPT_ENCODING": "gzip, deflate, br",
           "ACCEPT_LANGUAGE": "ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4"}

AFISHA_TIMETABLE_URL = "https://www.afisha.ru/msk/schedule_cinema/"
AFISHA_MOVIE_URL = "https://www.afisha.ru/movie/{}/"
AFISHA_MOVIE_SCHEDULE_URL = "https://www.afisha.ru/msk/schedule_cinema_product/{}/"
AFISHA_MOVIE_TITLE_PATTERN = re.compile(r"ru/movie/(\d*)/.>(.*)</a>")
AFISHA_CINEMAS_PATTERN = re.compile(r"href='https://www.afisha.ru/\w*/cinema/\d*/")
YEAR_PATTERN = re.compile(r"(\d{4})")

KINOPOISK_MOVIE_URL_PATTERN = "www.kinopoisk.ru/film/"
KINOPOISK_API_RATING_URL = "https://www.kinopoisk.ru/rating/{}.xml"
KINOPOISK_API_SEARH_URL = "https://www.kinopoisk.ru/search/handler-chromium-extensions"
KINOPOISK_MOVIE_ID_PATTERN = re.compile(r"www.kinopoisk.ru/film/(\d+)")

NPSB = '\xa0'
MIN_SLEEP = 1.5
MAX_SLEEP = 3.0
MAX_TIMEOUT = 6
MAX_RETRIES = 4
MAX_TOP_MOVIES = 21

Response = namedtuple('response', ['html', 'url', 'err'])


def make_response(html=None, url=None, err=None):
    return Response(html=html, url=url, err=err)


def load_html(url_to_load: "str", params=None) -> "Response":
    for _ in range(MAX_RETRIES):
        time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))
        try:
            response = requests.get(url_to_load, headers=HEADERS, params=params, timeout=MAX_TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.RequestException as rer:
            logger.error('load_html: RequestException err={} url={}'.format(rer, url_to_load))
        else:
            return make_response(html=response.text, url=response.url)
    else:
        logger.error('load_html: too many retries {} url={}'.format(MAX_RETRIES, url_to_load))
        return make_response(err=MAX_RETRIES)


def get_movies_ids_and_titles_from_afisha(html: "str") -> "list":
    movies_ids_titles = list(set(AFISHA_MOVIE_TITLE_PATTERN.findall(html)))
    return movies_ids_titles


def get_rating_votes_year_from_afisha(html: str) -> "tuple":
    rating, votes, year = None, None, None
    soup = BeautifulSoup(html, "html.parser")
    rating_text = soup.find('p', attrs={'class': 'stars pngfix'}).text.replace(',', '.').split(' ')
    votes_text = soup.find('p', attrs={'class': 'details s-update-clickcount'}).text.strip()
    year_text = soup.find('span', attrs={'class': 'creation'}).text
    try:
        rating = float(rating_text[4].split(NPSB)[0])
        votes = int(votes_text.split(' ')[1])
        year = int(YEAR_PATTERN.findall(year_text)[0])
    except ValueError:
        logger.error(
            "scrape_afisha_for_movies_info: values errors r={} v={} y={}".format(rating_text, votes_text, year_text))
    return rating, votes, year


def get_cinemas_number_from_afisha(html: str) -> "int":
    return len(AFISHA_CINEMAS_PATTERN.findall(html))


def scrape_afisha_for_movies_info(movies_ids_titles: "list") -> "list":
    rating, votes, year, cinemas = None, None, None, None
    movies_info = list()
    for movie_id, movie_title in movies_ids_titles:
        movie_page = load_html(AFISHA_MOVIE_URL.format(movie_id))
        if movie_page.err is None:
            rating, votes, year = get_rating_votes_year_from_afisha(movie_page.html)
        else:
            logger.error(
                "scrape_afisha_for_movies_info: movie page {} error {}".format(AFISHA_MOVIE_URL.format(movie_id),
                                                                               movie_page.err))
        schedule_page = load_html(AFISHA_MOVIE_SCHEDULE_URL.format(movie_id))
        if schedule_page.err is None:
            cinemas = get_cinemas_number_from_afisha(schedule_page.html)
        else:
            logger.error(
                "scrape_afisha_for_movies_info: movie schedule page {} error {}".format(
                    AFISHA_MOVIE_SCHEDULE_URL.format(movie_id), schedule_page.html))
        movies_info.append(dict(title=movie_title, year=year, cinemas=cinemas, af_rating=rating, af_votes=votes))
    return movies_info


def get_kinopoisk_movie_id(movie_url: "str") -> "int":
    kinopoisk_id = None
    if KINOPOISK_MOVIE_URL_PATTERN in movie_url:
        kinopoisk_id = int(KINOPOISK_MOVIE_ID_PATTERN.findall(movie_url)[0])
    else:
        logger.error("get_kinopoisk_movie_id: no movie id in the url={}".format(movie_url))
    return kinopoisk_id


def get_rating_votes_from_kinopoisk(html: "str") -> "tuple":
    rating, votes = None, None
    soup = BeautifulSoup(html, "html.parser")
    try:
        rating = float(soup('kp_rating')[0].text)
        votes = int(soup('kp_rating')[0]['num_vote'])
    except ValueError:
        logger.error(
            "get_rating_votes_from_kinopoisk: value errors {} {}".format(soup('kp_rating')[0].text,
                                                                         soup('kp_rating')[0]['num_vote']))
    return rating, votes


def scrape_kinopoisk_for_movies_info(movies_info_from_afisha: "list") -> "list":
    assert movies_info_from_afisha

    movies_full_info = movies_info_from_afisha.copy()
    for movie in movies_full_info:
        kinopoisk_id, rating, votes = None, None, None
        search_page = load_html(KINOPOISK_API_SEARH_URL,
                                params=dict(query="{} {}".format(movie['title'], movie['year']), go=1))
        if search_page.err is None:
            kinopoisk_id = get_kinopoisk_movie_id(search_page.url)
            if kinopoisk_id is not None:
                rating_page = load_html(KINOPOISK_API_RATING_URL.format(kinopoisk_id))
                if rating_page.err is None:
                    rating, votes = get_rating_votes_from_kinopoisk(rating_page.html)
        movie["kp_id"], movie["kp_rating"], movie["kp_votes"] = kinopoisk_id, rating, votes
    return movies_full_info


def print_result_to_console(movies_list: "list", total_movies: "int"):
    print("{} top movies from {} with best kinopoisk ratings are:".format(len(movies_list), total_movies))
    for movie_info in movies_list:
        print("  ", movie_info)


def main(n_top_movies: "int"):
    afisha_timetable_page = load_html(AFISHA_TIMETABLE_URL)
    if afisha_timetable_page.err is not None:
        logger.error("can't load afisha timetable, error {}".format(afisha_timetable_page.err))
    else:
        movies_ids_titles = get_movies_ids_and_titles_from_afisha(afisha_timetable_page.html)
        total_titles = len(movies_ids_titles)
        print("on {} {} movies run in cinemas across city".format(datetime.today().strftime('%Y-%m-%d'), total_titles))
        movies_afisha_info = scrape_afisha_for_movies_info(movies_ids_titles)
        movies_full_info = scrape_kinopoisk_for_movies_info(movies_afisha_info)
        best_movies = sorted(movies_full_info, key=lambda movie: movie['kp_rating'], reverse=True)[
                      :min(n_top_movies, total_titles)]
        print_result_to_console(best_movies, total_titles)


def create_logger(log_to_file=False, log_to_console=False) -> "class 'logging.RootLogger'":
    new_logger = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s %(name)-4s %(levelname)-5s %(message)s')
    new_logger.setLevel(logging.ERROR)
    if log_to_file:
        file_handler = logging.FileHandler('cinemas_log_file.txt', mode='w')
        file_handler.setLevel(logging.ERROR)
        file_handler.setFormatter(formatter)
        new_logger.addHandler(file_handler)
    if log_to_console:
        channel_handler = logging.StreamHandler()
        channel_handler.setLevel(logging.ERROR)
        channel_handler.setFormatter(formatter)
        new_logger.addHandler(channel_handler)
    return new_logger


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="finds top movies with highest kinopoisk ratings")
    ap.add_argument("--top", dest="top", action="store", type=int, default=7, help="  number of top movies")
    ap.add_argument("--log", dest="log", action="store_true", default=False,
                    help="  create log file 'cinemas_log_file.txt'")
    ap.add_argument("--verbose", dest="verbose", action="store_true", default=False,
                    help="  output debug information to console")
    args = ap.parse_args(sys.argv[1:])

    if 1 <= args.top <= MAX_TOP_MOVIES:
        logger = create_logger(log_to_file=args.log, log_to_console=args.verbose)
        main(args.top)
    else:
        print("invalid parameter --top value must be less or equal than {}".format(MAX_TOP_MOVIES))
