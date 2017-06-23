import argparse
import sys
import requests
from bs4 import BeautifulSoup
import time
import re
from operator import itemgetter
import random
import logging

LOG_MODE = False
NPSB = '\xa0'  # special space character &npsb;
user_agent = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/59.0.3071.104 Safari/537.36"}
MAX_RESPONSE_TIMEOUT = 4  # max response timeout to get answer from site
TIME_UPDATE_PROXY = 30 * 60 - 1  # 30 minutes - 1 sec
start_time = 0  # start time to count 30 minutes of proxies validity
proxies_list = list()  # list of valid proxies to use for parsing
next_proxy = 0


def good_proxy(proxy_ip: "str") -> "bool":
    try:
        proxy_addr = "http://" + proxy_ip
        _ = requests.get("http://www.example.com", proxies={"http": proxy_addr, "https": proxy_addr}, timeout=1)
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
    else:
        if LOG_MODE:
            logger.debug("can't load proxies, program aborted")
        exit(1)


def get_proxy() -> "dict":
    global proxies_list
    global next_proxy

    proxy_addr = "http://" + proxies_list[next_proxy]
    next_proxy += 1
    if next_proxy >= len(proxies_list):
        next_proxy = 0
    return {"http": proxy_addr, "https": proxy_addr}


def get_html(url_full: "str") -> "dict":
    global start_time
    global proxies_list

    if time.clock() - start_time >= TIME_UPDATE_PROXY:  # reload proxies list after 30 minutes
        proxies_list = load_good_proxy_list()
        start_time = time.clock()
    while True:
        try:
            response = requests.get(url_full, headers=user_agent, timeout=MAX_RESPONSE_TIMEOUT, proxies=get_proxy())
            if response.ok:
                time.sleep(random.random())
                return {'html': response.text, 'url': response.url, 'err': None}
            else:
                return {'html': None, 'url': None, 'err': "get error {}".format(response.status_code)}
        except OSError:
            pass
        except requests.exceptions.Timeout:
            return {'html': None, 'url': None, 'err': "get {} secs timeout error".format(MAX_RESPONSE_TIMEOUT)}


def fetch_afisha_page() -> "class 'bytes'":
    page = get_html("https://www.afisha.ru/msk/schedule_cinema/")
    if page['html']:
        return page['html']
    else:
        if LOG_MODE:
            logger.debug("can't load afisha page, error {}, program aborted".format(page['err']))
        exit(2)


def parse_afisha_list(raw_html: "class 'bytes'") -> "list":
    assert (raw_html is not None), "can't parse afisha page"
    soup = BeautifulSoup(raw_html, "lxml")
    movies = soup.find_all('div', attrs={'class': 'm-disp-table'})
    movies_info = [(movie.find('h3', attrs={'class': 'usetags'}).text, movie.find('a').attrs['href'])
                   for movie in movies]
    return movies_info


def get_afisha_movie_rating(soup: "class 'bs4.BeautifulSoup'") -> "float":
    try:
        rating_text = soup.find('p', attrs={'class': 'stars pngfix'}).attrs['title']
        rating_text = rating_text.split(' ')[2].split(NPSB)[0]
    except (AttributeError, IndexError):
        rating_text = "0"
    try:
        rating = float(rating_text.replace(',', '.'))
    except ValueError:
        rating = 0
        if LOG_MODE:
            logger.debug("get rating value error: '{}'".format(rating_text))
    return rating


def get_movie_votes(soup: "class 'bs4.BeautifulSoup'") -> "int":
    try:
        votes_text = soup.find('p', attrs={'class': 'details s-update-clickcount'}).text.strip()
        votes_text = votes_text.split(' ')[1]
    except AttributeError:
        votes_text = "0"
    try:
        votes = int(votes_text)
    except ValueError:
        votes = 0
        if LOG_MODE:
            logger.debug("get votes value error: '{}'".format(votes_text))
    return votes


def get_movie_production_year(soup: "class 'bs4.BeautifulSoup'") -> "int":
    year_text = soup.find('span', attrs={'class': 'creation'}).text.strip()
    if year_text:
        year_text = re.search(r"(\d{4})", year_text).group(1)
    else:
        year_text = "0"
    try:
        year = int(year_text)
    except ValueError:
        year = 0
        if LOG_MODE:
            logger.debug("get year value error: '{}'".format(year_text))
    return year


def get_movie_cinemas(soup: "class 'bs4.BeautifulSoup'") -> "int":
    try:
        timetable_url = soup.find('a', attrs={'id': 'ctl00_CenterPlaceHolder_ucTab_rpTabs_ctl02_hlItem'}).attrs['href']
    except AttributeError:
        if LOG_MODE:
            logger.debug("attr 'href' error in get_movie_cinemas()")
        return 0
    else:
        movie_timetable_page = get_html("https://www.afisha.ru" + timetable_url)
        if movie_timetable_page['html']:
            soup2 = BeautifulSoup(movie_timetable_page['html'], "lxml")
            cinemas_list = soup2.find_all('td', attrs={'class': "b-td-item"})
            return len(cinemas_list)
        else:
            if LOG_MODE:
                logger.debug("can't load timetable page, error {}".format(movie_timetable_page['err']))
            return 0


def get_rating_votes_kp_find_page(html_find: "str") -> "tuple":
    assert html_find is not None, "get_rating_votes_from_kinopoisk_find_page(), empty html_find"
    soup = BeautifulSoup(html_find, "lxml")
    rating_block = soup.find('div', attrs={'class': 'element most_wanted'})
    if rating_block is not None:
        class_list = ['rating ', 'rating  ', 'rating ratingGreenBG', 'rating  ratingGreenBG']
        try:
            rating_text = rating_block.find('div', attrs={'class': class_list}).attrs['title'].replace(NPSB, '')
        except AttributeError:  # rating is hidden, not enough votes
            return 0, 0
        else:
            rating = re.search(r"(\d*\.\d+|\d+)", rating_text).group(1)
            votes = re.search(r"\((\d+)\)", rating_text).group(1)
            return float(rating), int(votes)
    else:
        if LOG_MODE:
            logger.debug("can't find class 'element most_wanted' at get_rating_votes_from_kinopoisk_find_page")
        return -1, -1


def get_rating_votes_kp_movie_page(html_movie: "str") -> "tuple":
    assert html_movie is not None, "get_rating_votes_from_kinopoisk_movie_page(), empty html_movie"
    soup = BeautifulSoup(html_movie, "lxml")
    rating_block = soup.find('div', attrs={'id': 'block_rating'})
    if not rating_block:
        if LOG_MODE:
            logger.debug("error for div with id='block_rating' at get_rating_votes_from_kinopoisk_movie_page")
        return -1, -1
    else:
        try:
            rating = rating_block.find('span', attrs={'class': 'rating_ball'}).text
            votes = rating_block.find('span', attrs={'class': 'ratingCount'}).text.replace(NPSB, '')
        except AttributeError:
            if LOG_MODE:
                logger.debug("attr error for span with class='rating...' at get_rating_votes_from_kinopoisk_movie_page")
            return -1, -1
        else:
            return float(rating), int(votes)


def get_rating_votes_from_kinopoisk(title: "str", year: "int") -> "class 'bytes'":
    title_hex = "%" + "%".join("{:02x}".format(b) for b in bytearray(title.encode('utf-8'))).upper()
    url_find = "http://www.kinopoisk.ru/s/type/film/find/{}/m_act%5Byear%5D/{}".format(title_hex, year)
    page = get_html(url_find)
    if page['html']:
        if "/type/film/find/" in page['url']:  # kinopoisk is in the find page - list of many movies
            kp_rating, kp_votes = get_rating_votes_kp_find_page(page['html'])
        elif "www.kinopoisk.ru/film/" in page['url']:  # kinopoisk is in the page of the exact movie
            kp_rating, kp_votes = get_rating_votes_kp_movie_page(page['html'])
        else:
            if LOG_MODE:
                logger.debug("can't get rating and votes from wrong kinopoisk movie url {}".format(page['url']))
            kp_rating, kp_votes = 0, 0
        if kp_rating == -1:
            if LOG_MODE:
                logger.debug("rating and votes parsing problem with '{}' ({}) in kinopoisk.ru ".format(title, year))
            kp_rating, kp_votes = 0, 0
        return kp_rating, kp_votes
    else:
        if LOG_MODE:
            logger.debug("can't load kinopoisk page, error {}".format(page['err']))
        return 0, 0


def fetch_movie_info(movie_title: "str", movie_url: "str") -> "tuple":
    movie_page = get_html(movie_url)
    if movie_page['html']:
        soup = BeautifulSoup(movie_page['html'], "lxml")
        votes = get_movie_votes(soup)
        rating = get_afisha_movie_rating(soup)
        year = get_movie_production_year(soup)
        cinemas = get_movie_cinemas(soup)
        kp_rating, kp_votes = get_rating_votes_from_kinopoisk(movie_title, year)
        return year, rating, votes, cinemas, kp_rating, kp_votes
    else:
        if LOG_MODE:
            logger.debug("can't load movie page from afisha site, error {}".format(movie_page['err']))


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
        movie_info = fetch_movie_info(title, url)
        if movie_info:
            year, afisha_rating, afisha_votes, cinemas, kp_rating, kp_votes = movie_info
            if afisha_rating >= min_rating:
                top_movies_list.append((title, year, afisha_rating, afisha_votes, cinemas, kp_rating, kp_votes))
    if how_many_movies <= len(top_movies_list):
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)[:how_many_movies]
    else:
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)
    output_movies_to_console(best_movies)


def create_logger(copy_to_console=False):
    mylogger = logging.getLogger()  # logger handler
    mylogger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    fh = logging.FileHandler('cinemas_log_file.txt', mode='w')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    mylogger.addHandler(fh)
    if copy_to_console:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        mylogger.addHandler(ch)
    mylogger.disabled = True
    return mylogger


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="finds top N movies with star rating greater STARS")
    ap.add_argument("--n", dest="n", action="store", type=int, default=7, help="  number of movies")
    ap.add_argument("--stars", dest="stars", action="store", type=float, default=3.1, help="  stars rating")
    ap.add_argument("--log", dest="log", action="store_true", default=False,
                    help="  create log file 'cinemas_log_file.txt'")
    args = ap.parse_args(sys.argv[1:])

    LOG_MODE = args.log
    if LOG_MODE:
        logger = create_logger()  # initialize global logger handler

    start_time = time.clock()
    proxies_list = load_good_proxy_list()
    print("loaded {} good proxies".format(len(proxies_list)))

    main(args.stars, args.n)
