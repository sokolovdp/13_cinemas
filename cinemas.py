import argparse
import sys
import requests
from bs4 import BeautifulSoup
import time
import re
from operator import itemgetter
import random
import logging
from collections import namedtuple
from datetime import datetime

# Global constants
afisha_page = "https://www.afisha.ru/msk/schedule_cinema/"
proxy_url = "http://www.freeproxy-list.ru/api/proxy?token=demo"
user_agent = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/59.0.3071.104 Safari/537.36"}
MAX_RESPONSE_TIMEOUT = 9  # max response timeout to get answer from site
TIME_UPDATE_PROXY = 30 * 60 - 1  # 30 minutes - 1 sec
MAX_TIMEOUT_RETRIES = 5
NPSB = '\xa0'  # special space character &npsb;
ERROR = -1
NO_DATA = 0
# Global variables
Rating = namedtuple('movie_rating', ['rating', 'votes'])
Movie_info = namedtuple('movie_info', ['title', 'year', 'af_rating', 'cinemas', 'kp_rating'])
Proxies_list = namedtuple('proxies_list', ['proxies', 'next_proxy'])  # list of valid proxies to use for parsing

proxies_list = Proxies_list(list(), 0)
start_time = 0  # start time to count 30 minutes of proxies validity


def is_proxy_good(proxy_ip: "str") -> "bool":
    try:
        proxy_addr = "http://" + proxy_ip
        requests.get(afisha_page, proxies={"http": proxy_addr, "https": proxy_addr},
                     timeout=MAX_RESPONSE_TIMEOUT)
    except OSError:
        return False
    except requests.exceptions.Timeout:
        return False
    else:
        return True


def load_good_proxy_list():
    global proxies_list

    response = requests.get(proxy_url)
    if response.ok:
        good_proxies = [proxy for proxy in response.text.split('\n') if is_proxy_good(proxy)]
        logger.error("info!!!! loaded {} good proxies".format(len(good_proxies)))
        proxies_list.next_proxy = 0
        proxies_list.proxies = good_proxies


def next_valid_proxy() -> "dict":
    global proxies_list

    proxy_addr = "http://" + proxies_list[proxies_list.next_proxy]
    proxies_list.next_proxy += 1
    if proxies_list.next_proxy >= len(proxies_list):
        proxies_list.next_proxy = 0
    return {"http": proxy_addr, "https": proxy_addr}


def update_proxies_list_if_needed():  # reload proxies list after 30 minutes
    global start_time
    global proxies_list

    if time.clock() - start_time >= TIME_UPDATE_PROXY:
        load_good_proxy_list()
        start_time = time.clock()


def remove_from_proxies_list(ip: "str"):
    global proxies_list

    ip = ip.replace("http://", '')
    proxies_list.proxies = [proxy for proxy in proxies_list.proxies if proxy != ip]
    proxies_list.next_proxy = 0
    if len(proxies_list.proxies) == 0:
        load_good_proxy_list()
    time.sleep(2)


def make_response(html=None, url=None, err=None):
    return dict(html=html, url=url, err=err)


def load_html(url: "str") -> "dict":
    update_proxies_list_if_needed()
    timeout_retries = 0
    while True:
        try:
            proxy = next_valid_proxy()
            response = requests.get(url, headers=user_agent, timeout=MAX_RESPONSE_TIMEOUT, proxies=proxy)
            if response.status_code == 200:
                time.sleep(random.random())  # wait random period between 0 - 1 sec
                return make_response(html=response.text, url=response.url)
            else:
                logger.error('load_html: url={} response error={}'.format(url, response.status_code))
                return make_response(err=str(response.status_code))
        except requests.exceptions.Timeout:
            logger.error('load_html: url={} timeout={} secs'.format(url, MAX_RESPONSE_TIMEOUT))
            timeout_retries += 1
            if timeout_retries >= MAX_TIMEOUT_RETRIES:
                return make_response(err="load_html timeout error")
            continue
        except OSError as ose:  # Tunnel connection failed: 403 Forbidden
            remove_from_proxies_list(proxy['http'])
            logger.error("load_html: OSError! url={} proxy={} err='{}'".format(url, proxy['http'], ose))
            continue


def fetch_af_page() -> "class 'bytes'":
    page = load_html(afisha_page)
    if page['html']:
        return page['html']
    else:
        logger.error("fetch_af_page: can't load afisha page, error {}".format(page['err']))


def parse_af_list(raw_html: "class 'bytes'") -> "list":
    assert raw_html

    soup = BeautifulSoup(raw_html, "lxml")
    movies = soup.find_all('div', attrs={'class': 'm-disp-table'})
    movies_titles = [(movie.find('h3', attrs={'class': 'usetags'}).text, movie.find('a').attrs['href'])
                     for movie in movies]
    return movies_titles


def scrape_af_movie_rating(soup: "class 'bs4.BeautifulSoup'") -> "float":
    assert soup

    try:
        rating_text = soup.find('p', attrs={'class': 'stars pngfix'}).attrs['title']
        rating_text = rating_text.split(' ')[2].split(NPSB)[0]
    except (AttributeError, IndexError):
        rating_text = str(NO_DATA)
    try:
        rating = float(rating_text.replace(',', '.'))
    except ValueError:
        rating = NO_DATA
        logger.error("scrape_af_movie_rating: get rating value error: '{}'".format(rating_text))
    return rating


def scrape_af_movie_votes(soup: "class 'bs4.BeautifulSoup'") -> "int":
    assert soup

    try:
        votes_text = soup.find('p', attrs={'class': 'details s-update-clickcount'}).text.strip()
        votes_text = votes_text.split(' ')[1]
    except AttributeError:
        votes_text = str(NO_DATA)
    try:
        votes = int(votes_text)
    except ValueError:
        votes = NO_DATA
        logger.error("scrape_af_movie_votes: get votes value error: '{}'".format(votes_text))
    return votes


def scrape_af_movie_year(soup: "class 'bs4.BeautifulSoup'") -> "int":
    assert soup

    year_text = soup.find('span', attrs={'class': 'creation'}).text.strip()
    if year_text:
        year_text = re.search(r"(\d{4})", year_text).group(1)
    else:
        year_text = str(NO_DATA)
    try:
        year = int(year_text)
    except ValueError:
        year = NO_DATA
        logger.error("scrape_af_movie_year: get year value error: '{}'".format(year_text))
    return year


def scrape_af_cinemas(soup: "class 'bs4.BeautifulSoup'") -> "int":
    assert soup

    try:
        timetable_url = soup.find('a', attrs={'id': 'ctl00_CenterPlaceHolder_ucTab_rpTabs_ctl02_hlItem'}).attrs['href']
    except AttributeError:
        logger.error("scrape_af_cinemas: attr 'href' error in scrape_af_cinemas()")
        return NO_DATA
    else:
        movie_time_page = load_html("https://www.afisha.ru" + timetable_url)
        if movie_time_page['html']:
            soup2 = BeautifulSoup(movie_time_page['html'], "lxml")
            cinemas_list = soup2.find_all('td', attrs={'class': "b-td-item"})
            return len(cinemas_list)
        else:
            logger.error("scrape_af_cinemas: can't load time page {} error {}".format(movie_time_page['url'],
                                                                                      movie_time_page['err']))
            return NO_DATA


def scrape_rating_votes_kp_result_page(html_result: "str") -> "Rating":
    assert html_result

    soup = BeautifulSoup(html_result, "lxml")
    rating_block = soup.find('div', attrs={'class': 'element most_wanted'})
    if rating_block:
        class_list = ['rating ', 'rating  ', 'rating ratingGreenBG', 'rating  ratingGreenBG']
        try:
            rating_text = rating_block.find('div', attrs={'class': class_list}).attrs['title'].replace(NPSB, '')
        except AttributeError:  # rating is hidden (not enough votes)
            return Rating(NO_DATA, NO_DATA)
        else:
            rating = re.search(r"(\d*\.\d+|\d+)", rating_text).group(1)
            votes = re.search(r"\((\d+)\)", rating_text).group(1)
            return Rating(float(rating), int(votes))
    else:
        logger.error("scrape_rating_votes_kp_result_page: no class 'element most_wanted' in page")
        return Rating(ERROR, ERROR)


def scrape_rating_votes_kp_movie_page(html_movie: "str") -> "Rating":
    assert html_movie

    soup = BeautifulSoup(html_movie, "lxml")
    rating_block = soup.find('div', attrs={'id': 'block_rating'})
    if not rating_block:
        logger.error("scrape_rating_votes_kp_movie_page: no div with id='block_rating'")
        return Rating(ERROR, ERROR)
    else:
        try:
            rating = rating_block.find('span', attrs={'class': 'rating_ball'}).text
            votes = rating_block.find('span', attrs={'class': 'ratingCount'}).text.replace(NPSB, '')
        except AttributeError:
            logger.error("scrape_rating_votes_from_kinopoisk_movie_page: no attrs for span with class='rating...'")
            return Rating(ERROR, ERROR)
        else:
            return Rating(float(rating), int(votes))


def convert_title_to_ascii_hex(string: "str") -> "str":
    line = "%" + "%".join("{:02x}".format(b) for b in bytearray(string.encode('utf-8'))).upper()
    return line.replace("%20", "+")


def make_kp_find_url(movie_title: "str", year: int):
    find_url_1 = "http://www.kinopoisk.ru/s/type/film/find/"
    find_url_2 = "/m_act%5Byear%5D/"
    title_hex = convert_title_to_ascii_hex(movie_title)
    return "{0}{1}{2}{3}".format(find_url_1, title_hex, find_url_2, year)


def scrape_rating_votes_from_kp(page: "str") -> "Rating":
    assert page

    if "/type/film/find/" in page:  # kinopoisk is in the search results page - list of many movies
        kp_rating = scrape_rating_votes_kp_result_page(page)
    elif "www.kinopoisk.ru/film/" in page:  # kinopoisk is in the page of the movie
        kp_rating = scrape_rating_votes_kp_movie_page(page)
    else:
        logger.error("scrape_rating_votes_from_kp: can't get rating and votes from url '{}'".format(page.strip()))
        kp_rating = Rating(NO_DATA, NO_DATA)
    if kp_rating.votes == ERROR:  # check if there were some errors
        logger.error("scrape_rating_votes_from_kp: error, rating and votes set to NO_DATA")
        kp_rating = Rating(NO_DATA, NO_DATA)
    return kp_rating


def fetch_movie_info(movie_title: "str", af_movie_page: "str") -> "Movie_info":
    assert af_movie_page
    assert movie_title

    soup = BeautifulSoup(af_movie_page, "lxml")
    af_rating = Rating(scrape_af_movie_rating(soup), scrape_af_movie_votes(soup))
    year = scrape_af_movie_year(soup)
    cinemas = scrape_af_cinemas(soup)
    # scrape movie info from kinopoisk.ru
    kp_url_find = make_kp_find_url(movie_title, year)
    kp_page = load_html(kp_url_find)
    if kp_page['html']:
        kp_rating = scrape_rating_votes_from_kp(kp_page['html'])
    else:
        logger.error("fetch_movie_info: can't load kinopoisk page {} error {}".format(kp_page['url'], kp_page['err']))
        kp_rating = Rating(NO_DATA, NO_DATA)
    return Movie_info(movie_title, year, af_rating, cinemas, kp_rating)


def output_movies_to_console(movies_list: "list", all_movies: "int"):
    print("on {} {} top movies from {} with best ratings are:".format(datetime.today().strftime('%Y-%m-%d'),
                                                                      len(movies_list), all_movies))
    for i, movie_info in enumerate(movies_list):
        print(" {0:2d}. {1}({2}) ratings {3}({4}) and {6:.1f}({7}) in {5} cinemas".format(i + 1, movie_info.title,
                                                                                          movie_info.year,
                                                                                          movie_info.af_rating.rating,
                                                                                          movie_info.af_rating.votes,
                                                                                          movie_info.cinemas,
                                                                                          movie_info.kp_rating.rating,
                                                                                          movie_info.kp_rating.votes
                                                                                          ))


def main(min_rating: "float", how_many_movies: "int"):
    list_of_movies_title_and_url = parse_af_list(fetch_af_page())
    logger.error("info!!! {} movies loaded from afisha.ru".format(len(list_of_movies_title_and_url)))
    top_movies_list = list()
    for title, url in list_of_movies_title_and_url:
        movie_page = load_html(url)
        if movie_page['html']:
            movie_info = fetch_movie_info(title, movie_page['html'])
            if movie_info:
                if movie_info.af_rating.rating >= min_rating:
                    top_movies_list.append(movie_info)
        else:
            logger.error("main: no afisha movie page {}, error {}".format(movie_page['url'], movie_page['err']))
    if how_many_movies <= len(top_movies_list):
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)[:how_many_movies]
    else:
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)
    output_movies_to_console(best_movies, len(list_of_movies_title_and_url))


def create_logger(log_to_file=False, log_to_console=False):
    log = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
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
    ap = argparse.ArgumentParser(description="finds top N movies with star rating greater STARS")
    ap.add_argument("--n", dest="n", action="store", type=int, default=7, help="  number of movies")
    ap.add_argument("--stars", dest="stars", action="store", type=float, default=3.1, help="  stars rating")
    ap.add_argument("--log", dest="log", action="store_true", default=False,
                    help="  create log file 'cinemas_log_file.txt'")
    ap.add_argument("--verbose", dest="verbose", action="store_true", default=False,
                    help="  output debug information to console")
    args = ap.parse_args(sys.argv[1:])
    logger = create_logger(log_to_file=args.log, log_to_console=args.verbose)  # initialize global logger handler
    start_time = time.clock()
    load_good_proxy_list()
    if proxies_list:
        main(args.stars, args.n)
