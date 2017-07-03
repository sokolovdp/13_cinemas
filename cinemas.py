import argparse
import sys
import requests
from bs4 import BeautifulSoup
import time
import re
from operator import itemgetter
import random
import logging

afisha_page = "https://www.afisha.ru/msk/schedule_cinema/"
NPSB = '\xa0'  # special space character &npsb;
user_agent = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/59.0.3071.104 Safari/537.36"}
MAX_RESPONSE_TIMEOUT = 7  # max response timeout to get answer from site
TIME_UPDATE_PROXY = 30 * 60 - 1  # 30 minutes - 1 sec
start_time = 0  # start time to count 30 minutes of proxies validity
next_proxy = 0
ERROR = -1
NO_DATA = 0

proxies_list = list()  # list of valid proxies to use for parsing


def good_proxy(proxy_ip: "str") -> "bool":
    try:
        proxy_addr = "http://" + proxy_ip
        requests.get("http://www.example.com", proxies={"http": proxy_addr, "https": proxy_addr}, timeout=1)
    except OSError:
        return False
    except requests.exceptions.Timeout:
        return False
    else:
        return True


def load_good_proxy_list() -> "list":
    response = requests.get("http://www.freeproxy-list.ru/api/proxy?token=demo")
    if response.ok:
        return list(filter(good_proxy, response.text.split('\n')))


def next_valid_proxy() -> "dict":
    global proxies_list
    global next_proxy

    proxy_addr = "http://" + proxies_list[next_proxy]
    next_proxy += 1
    if next_proxy >= len(proxies_list):
        next_proxy = 0
    return {"http": proxy_addr, "https": proxy_addr}


def update_proxies_list_if_needed():  # reload proxies list after 30 minutes
    global start_time
    global proxies_list

    if time.clock() - start_time >= TIME_UPDATE_PROXY:
        proxies_list = load_good_proxy_list()
        start_time = time.clock()


def make_response(html=None, url=None, err=None):
    return dict(html=html, url=url, err=err)


def load_html(url: "str") -> "dict":
    update_proxies_list_if_needed()
    while True:
        try:
            response = requests.get(url, headers=user_agent, timeout=MAX_RESPONSE_TIMEOUT, proxies=next_valid_proxy())
            if response.ok:
                time.sleep(random.random())  # wait random period between 0 - 1 sec
                return make_response(html=response.text, url=response.url)
            else:
                logger.debug('load_html - response error')
                return make_response(err=str(response.status_code))
        except requests.exceptions.Timeout:
            logger.debug('load_html - timeout error')
            return make_response(err="load_html timeout error")
        except OSError:  # Tunnel connection failed: 403 Forbidden
            logger.debug('load_html - OSError: Tunnel connection failed: 403 Forbidden')
            continue


def fetch_afisha_page() -> "class 'bytes'":
    page = load_html(afisha_page)
    if page['html']:
        return page['html']
    else:
        print("can't load afisha page, error {}".format(page['err']))


def parse_afisha_list(raw_html: "class 'bytes'") -> "list":
    assert raw_html

    soup = BeautifulSoup(raw_html, "lxml")
    movies = soup.find_all('div', attrs={'class': 'm-disp-table'})
    movies_info = [(movie.find('h3', attrs={'class': 'usetags'}).text, movie.find('a').attrs['href'])
                   for movie in movies]
    return movies_info


def scrape_afisha_movie_rating(soup: "class 'bs4.BeautifulSoup'") -> "float":
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
        logger.debug("get rating value error: '{}'".format(rating_text))
    return rating


def scrape_afisha_movie_votes(soup: "class 'bs4.BeautifulSoup'") -> "int":
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
        logger.debug("get votes value error: '{}'".format(votes_text))
    return votes


def scrape_afisha_movie_year(soup: "class 'bs4.BeautifulSoup'") -> "int":
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
        logger.debug("get year value error: '{}'".format(year_text))
    return year


def scrape_afisha_cinemas(soup: "class 'bs4.BeautifulSoup'") -> "int":
    assert soup

    try:
        timetable_url = soup.find('a', attrs={'id': 'ctl00_CenterPlaceHolder_ucTab_rpTabs_ctl02_hlItem'}).attrs['href']
    except AttributeError:
        logger.debug("attr 'href' error in scrape_afisha_cinemas()")
        return NO_DATA
    else:
        movie_time_page = load_html("https://www.afisha.ru" + timetable_url)
        if movie_time_page['html']:
            soup2 = BeautifulSoup(movie_time_page['html'], "lxml")
            cinemas_list = soup2.find_all('td', attrs={'class': "b-td-item"})
            return len(cinemas_list)
        else:
            logger.debug("can't load time page {} error {}".format(movie_time_page['url'], movie_time_page['err']))
            return NO_DATA


def scrape_rating_votes_kp_result_page(html_result: "str") -> "tuple":
    assert html_result

    soup = BeautifulSoup(html_result, "lxml")
    rating_block = soup.find('div', attrs={'class': 'element most_wanted'})
    if rating_block:
        class_list = ['rating ', 'rating  ', 'rating ratingGreenBG', 'rating  ratingGreenBG']
        try:
            rating_text = rating_block.find('div', attrs={'class': class_list}).attrs['title'].replace(NPSB, '')
        except AttributeError:  # rating is hidden (not enough votes)
            return NO_DATA, NO_DATA
        else:
            rating = re.search(r"(\d*\.\d+|\d+)", rating_text).group(1)
            votes = re.search(r"\((\d+)\)", rating_text).group(1)
            return float(rating), int(votes)
    else:
        logger.debug("can't find class 'element most_wanted' at scrape_rating_votes_from_kinopoisk_find_page")
        return ERROR, ERROR


def scrape_rating_votes_kp_movie_page(html_movie: "str") -> "tuple":
    assert html_movie

    soup = BeautifulSoup(html_movie, "lxml")
    rating_block = soup.find('div', attrs={'id': 'block_rating'})
    if not rating_block:
        logger.debug("error for div with id='block_rating' at scrape_rating_votes_from_kinopoisk_movie_page")
        return ERROR, ERROR
    else:
        try:
            rating = rating_block.find('span', attrs={'class': 'rating_ball'}).text
            votes = rating_block.find('span', attrs={'class': 'ratingCount'}).text.replace(NPSB, '')
        except AttributeError:
            logger.debug("attr error for span with class='rating...' at scrape_rating_votes_from_kinopoisk_movie_page")
            return ERROR, ERROR
        else:
            return float(rating), int(votes)


def convert_string_to_ascii_hex(string: "str") -> "str":
    return "%" + "%".join("{:02x}".format(b) for b in bytearray(string.encode('utf-8'))).upper()


def make_kp_find_url(movie_title: "str", year: int):
    find_url_1 = "http://www.kinopoisk.ru/s/type/film/find/"
    find_url_2 = "/m_act%5Byear%5D/"
    title_hex = convert_string_to_ascii_hex(movie_title)
    return "{0}{1}{2}{3}".format(find_url_1, title_hex, find_url_2, year)


def scrape_rating_votes_from_kp(page: "str") -> "tuple":
    assert page

    if "/type/film/find/" in page:  # kinopoisk is in the search results page - list of many movies
        kp_rating, kp_votes = scrape_rating_votes_kp_result_page(page)
    elif "www.kinopoisk.ru/film/" in page:  # kinopoisk is in the page of the movie
        kp_rating, kp_votes = scrape_rating_votes_kp_movie_page(page)
    else:
        logger.debug("can't get rating and votes from invalid kinopoisk movie url {}".format(page))
        kp_rating, kp_votes = NO_DATA, NO_DATA
    if kp_rating == ERROR:  # check if there were some errors
        logger.debug("rating and votes parsing problem in kinopoisk.ru ")
        kp_rating, kp_votes = NO_DATA, NO_DATA
    return kp_rating, kp_votes


def fetch_movie_info(movie_title: "str", movie_page: "str") -> "tuple":
    assert movie_page
    assert movie_title

    soup = BeautifulSoup(movie_page, "lxml")
    votes = scrape_afisha_movie_votes(soup)
    rating = scrape_afisha_movie_rating(soup)
    year = scrape_afisha_movie_year(soup)
    cinemas = scrape_afisha_cinemas(soup)
    # scrape movie info from kinopoisk.ru
    kp_url_find = make_kp_find_url(movie_title, year)
    kp_page = load_html(kp_url_find)
    if kp_page['html']:
        kp_rating, kp_votes = scrape_rating_votes_from_kp(kp_page['html'])
    else:
        logger.debug("can't load kinopoisk page {} error {}".format(kp_page['url'], kp_page['err']))
        kp_rating, kp_votes = NO_DATA, NO_DATA
    return year, rating, votes, cinemas, kp_rating, kp_votes


def output_movies_to_console(movies_list: "list"):
    print("{0} top movies with best ratings are:".format(len(movies_list)))
    for i, movie_info in enumerate(movies_list):
        # title, year, afisha_rating, afisha_votes, cinemas, kp_rating, kp_votes = movie_info
        print(" {0:2d}. {1}({2}) has ratings {3}({4}) and {6:.1f}({7}) in {5} cinemas".format(i + 1, *movie_info))


def main(min_rating: "float", how_many_movies: "int"):
    list_of_movies_title_and_url = parse_afisha_list(fetch_afisha_page())
    print("total {} movies are in cinemas today".format(len(list_of_movies_title_and_url)))
    top_movies_list = list()
    for title, url in list_of_movies_title_and_url:
        movie_page = load_html(url)
        if movie_page['html']:
            movie_info = fetch_movie_info(title, movie_page['html'])
            if movie_info:
                year, afisha_rating, afisha_votes, cinemas, kp_rating, kp_votes = movie_info
                if afisha_rating >= min_rating:
                    top_movies_list.append((title, year, afisha_rating, afisha_votes, cinemas, kp_rating, kp_votes))
        else:
            logger.debug(
                "can't load movie page {} from afisha site, error {}".format(movie_page['url'], movie_page['err']))
    if how_many_movies <= len(top_movies_list):
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)[:how_many_movies]
    else:
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)
    output_movies_to_console(best_movies)


def create_logger(log_to_file=False, log_to_console=False):
    log = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    log.setLevel(logging.DEBUG)
    if log_to_file:
        fh = logging.FileHandler('cinemas_log_file.txt', mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        log.addHandler(fh)
    if log_to_console:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
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

    proxies_list = load_good_proxy_list()
    assert proxies_list
    print("loaded {} good proxies".format(len(proxies_list)))

    main(args.stars, args.n)
