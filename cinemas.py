# standard modules
import sys
import argparse
import time
import re
import random
import logging
from datetime import datetime
# application modules
import requests
from bs4 import BeautifulSoup

# Global constants
HTTP = "http://"
PROXY_SERVICE_URL = "http://www.freeproxy-list.ru/api/proxy?token=demo"
USER_AGENT = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/59.0.3071.104 Safari/537.36"}

AF_MAIN_URL = "https://www.afisha.ru"
AF_TIMETABLE_URL = "https://www.afisha.ru/msk/schedule_cinema/"
AF_MOVIE_URL = "https://www.afisha.ru/movie/{}/"
AF_MOVIE_SCHEDULE_URL = "https://www.afisha.ru/msk/schedule_cinema_product/{}/"

KP_MOVIE_URL_PATTERN = "www.kinopoisk.ru/film/"
KP_RATING_API_URL = "http://www.kinopoisk.ru/rating/{}.xml"
KP_QUERY_URL_1st_PART = "https://www.kinopoisk.ru/index.php?first=yes&what=film&kp_query="  # choose 1st film from list

AF_MOVIE_TITLE_PATTERN = re.compile(r"ru/movie/(\d*)/.>(.*)</a>")
AF_CINEMAS_PATTERN = re.compile(r"href='https://www.afisha.ru/\w*/cinema/\d*/")
YEAR_PATTERN = re.compile(r"(\d{4})")

MAX_TIMEOUT = 4
MAX_RETRIES = 3
NPSB = '\xa0'  # special space character &npsb;
NO_DATA = 0
MAX_TOP_MOVIES = 20

# Global variables
live_proxies = dict(proxies=list(), current=0)


def is_proxy_alive(proxy_ip: "str") -> "bool":
    result = True
    try:
        proxy = HTTP + proxy_ip
        resp = requests.get(AF_TIMETABLE_URL, proxies=dict(http=proxy, https=proxy), timeout=MAX_TIMEOUT)
    except (OSError, requests.exceptions.Timeout):
        result = False
    else:
        if not resp.ok:
            result = False
    return result


def load_working_proxies():
    global live_proxies

    for _ in range(MAX_RETRIES):
        response = requests.get(PROXY_SERVICE_URL, headers=USER_AGENT, timeout=MAX_TIMEOUT)
        if response.ok:
            alive_proxies = [proxy for proxy in response.text.split() if is_proxy_alive(proxy)]
            logger.error("info!!! load_working_proxies: loaded only {} good proxies".format(len(alive_proxies)))
            if len(alive_proxies):
                live_proxies['current'] = 0
                live_proxies['proxies'] = alive_proxies
                break
        else:
            logger.error("load_working_proxies: response.status_code={}".format(response.status_code))


def make_response(html=None, url=None, err=None):
    return dict(html=html, url=url, err=err)


def take_next_live_proxy():
    global live_proxies
    live_proxies['current'] += 1
    if live_proxies['current'] >= len(live_proxies['proxies']):
        live_proxies['current'] = 0


def remove_current_proxy_from_proxies_list():
    global live_proxies
    live_proxies['proxies'].remove(live_proxies['proxies'][live_proxies['current']])
    if len(live_proxies['proxies']) <= 0:
        load_working_proxies()
    else:
        live_proxies['current'] = 0


def load_html(url_to_load: "str") -> "dict":
    error_message = "load_html: unexpected error"
    for _ in range(MAX_RETRIES):
        time.sleep(random.random())
        try:
            proxy_url = HTTP + str(live_proxies['proxies'][live_proxies['current']])
            response = requests.get(url_to_load, headers=USER_AGENT, timeout=MAX_TIMEOUT,
                                    proxies=dict(http=proxy_url, https=proxy_url))
        except requests.exceptions.Timeout:
            error_message = 'load_html: timeout error url={}'.format(url_to_load)
        except OSError as ose:  # Proxy became inactive
            remove_current_proxy_from_proxies_list()
            error_message = "load_html: OSError url={} err='{}'".format(url_to_load, ose)
        else:
            if response.status_code == 200:
                result = make_response(html=response.text, url=response.url)
                break
            else:
                take_next_live_proxy()
                error_message = 'load_html: url={} response error={}'.format(url_to_load, response.status_code)
                logger.error(error_message)
    else:
        result = make_response(err=error_message)

    return result


def fetch_af_movies_titles() -> "list":
    page = load_html(AF_TIMETABLE_URL)
    if page['html']:
        movies_ids_titles = list(set(AF_MOVIE_TITLE_PATTERN.findall(page['html'])))  # remove duplicated titles
    else:
        logger.error("fetch_af_movies_titles: page {}, error {}".format(AF_TIMETABLE_URL, page['err']))
        movies_ids_titles = list()
    return movies_ids_titles


def scrape_af_info(movies_ids_titles: "list") -> "list":
    assert movies_ids_titles

    movies_info = list()
    for movie_data in movies_ids_titles:
        mv_id, title = movie_data
        year, cinemas, rating, votes = NO_DATA, NO_DATA, NO_DATA, NO_DATA
        url_movie = AF_MOVIE_URL.format(mv_id)
        page_movie = load_html(url_movie)
        if page_movie['html']:
            soup = BeautifulSoup(page_movie['html'], "html.parser")
            rating_text = soup.find('p', attrs={'class': 'stars pngfix'}).text.replace(',', '.').split(' ')
            votes_text = soup.find('p', attrs={'class': 'details s-update-clickcount'}).text.strip()
            year_text = soup.find('span', attrs={'class': 'creation'}).text
            try:
                rating = float(rating_text[4].split(NPSB)[0])
                votes = int(votes_text.split(' ')[1])
                year = int(YEAR_PATTERN.findall(year_text)[0])
            except ValueError:
                logger.error("scrape_af_info: value error url={} r={} v={} y={}".format(url_movie, rating_text,
                                                                                        votes_text, year_text))
                rating, votes, year = NO_DATA, NO_DATA, NO_DATA
        else:
            logger.error("scrape_af_info: movie page {} error {}".format(url_movie, page_movie['err']))
        url_movie_schedule = AF_MOVIE_SCHEDULE_URL.format(mv_id)
        page_schedule = load_html(url_movie_schedule)
        if page_schedule['html']:
            cinemas = len(AF_CINEMAS_PATTERN.findall(page_schedule['html']))
        else:
            logger.error("scrape_af_info: movie schedule page {} error {}".format(url_movie, page_schedule['err']))
        movies_info.append(dict(title=title, year=year, cinemas=cinemas, af_rating=rating, af_votes=votes))
    return movies_info


def form_kp_query_url(title: "str", year: int):
    t_hex = "%".join("{:02x}".format(b) for b in bytearray(title.encode('utf-8'))).upper().replace("%20", "+")
    return "{}%{}+{}".format(KP_QUERY_URL_1st_PART, t_hex, year)


def fetch_kp_movie_id(movie_title: "str", year: "int") -> "int":
    movie_url = form_kp_query_url(movie_title, year)
    page = load_html(movie_url)
    kp_id = NO_DATA
    if page['html']:
        if KP_MOVIE_URL_PATTERN in page['url']:  # it is in the kinopoisk movie page
            kp_id_text = YEAR_PATTERN.findall(page['url'])[0]
        else:
            soup = BeautifulSoup(page['html'], 'html.parser')
            try:
                kp_id_text = soup.find('a', {'class': 'js-serp-metrika'}).attrs['data-id']
            except AttributeError:
                logger.error("fetch_kp_movie_id: attr 'data-id' error url {}".format(movie_url))
                kp_id_text = ''
        if not kp_id_text:
            kp_id = NO_DATA
        else:
            kp_id = int(kp_id_text)
    return int(kp_id)


def get_kp_rating_votes(kp_id: "int") -> "tuple":
    api_url = KP_RATING_API_URL.format(kp_id)
    page = load_html(api_url)
    if page['html']:
        soup = BeautifulSoup(page['html'], "html.parser")
        votes = int(soup('kp_rating')[0]['num_vote'])
        rating = float(soup('kp_rating')[0].text)
    else:
        logger.error("get_kp_rating_votes: url {} error {}".format(api_url, page['err']))
        votes, rating = 0, 0
    return rating, votes


def scrape_kp_info(movies_ap_info: "list") -> "list":
    assert movies_ap_info

    movies_full_info = movies_ap_info.copy()
    for movie in movies_full_info:
        kp_id = fetch_kp_movie_id(movie['title'], movie['year'])
        if kp_id != NO_DATA:
            kp_rating, kp_votes = get_kp_rating_votes(kp_id)
            movie["kp_id"], movie["kp_rating"], movie["kp_votes"] = kp_id, kp_rating, kp_votes
    return movies_full_info


def output_movies_to_console(movies_list: "list", total_movies: "int"):
    print("{} top movies from {} with best kp ratings are:".format(len(movies_list), total_movies))
    for mv in movies_list:
        print("  ", mv)


def main(n_top_movies: "int"):
    movies_titles = fetch_af_movies_titles()
    total_titles = len(movies_titles)
    print("today {} {} movies run in cinemas across city".format(datetime.today().strftime('%Y-%m-%d'), total_titles))
    movies_ap_info = scrape_af_info(movies_titles)
    movies_full_info = scrape_kp_info(movies_ap_info)
    best_movies = sorted(movies_full_info, key=lambda movie: movie['kp_rating'], reverse=True)[:min(n_top_movies,
                                                                                                    total_titles)]
    output_movies_to_console(best_movies, total_titles)


def create_logger(log_to_file=False, log_to_console=False) -> "class 'logging.RootLogger'":
    log = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s %(name)-4s %(levelname)-5s %(message)s')
    log.setLevel(logging.ERROR)
    if log_to_file:
        fh = logging.FileHandler('cinemas_log_file.txt', mode='w')
        fh.setLevel(logging.ERROR)
        fh.setFormatter(formatter)
        log.addHandler(fh)
    if log_to_console:
        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        ch.setFormatter(formatter)
        log.addHandler(ch)
    return log


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="finds N movies with highest ratings (N <= {}".format(MAX_TOP_MOVIES))
    ap.add_argument("--n", dest="n", action="store", type=int, default=7, help="  number of best movies")
    ap.add_argument("--log", dest="log", action="store_true", default=False,
                    help="  create log file 'cinemas_log_file.txt'")
    ap.add_argument("--verbose", dest="verbose", action="store_true", default=False,
                    help="  output debug information to console")
    args = ap.parse_args(sys.argv[1:])

    if 1 <= args.n <= MAX_TOP_MOVIES:
        logger = create_logger(log_to_file=args.log, log_to_console=args.verbose)
        load_working_proxies()
        if live_proxies:
            main(args.n)
    else:
        print("invalid parameter --n value {}".format(args.n))
