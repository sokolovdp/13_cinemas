import argparse
import sys
import requests
from bs4 import BeautifulSoup
import time
import re
from operator import itemgetter

PAUSE = 0.5  # time between requests in sec  0.7 is OK
user_agent = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/39.0.2171.95 Safari/537.36'}


def get_html_from_url(url_full: "str") -> "dict":
    response = requests.get(url_full, headers=user_agent)
    time.sleep(PAUSE)
    if response.ok:
        return {"html": response.text, "err": None}
    else:
        return {'html': None, "err": response.status_code}


def fetch_afisha_page() -> "class 'bytes'":
    page = get_html_from_url("https://www.afisha.ru/msk/schedule_cinema/")
    if page['html']:
        return page['html']
    else:
        print("can't load Afisha page, error {}".format(page['err']))
        exit()


def parse_afisha_list(raw_html: "class 'bytes'") -> "list":
    soup = BeautifulSoup(raw_html, "lxml")
    movies = soup.find_all('div', attrs={'class': 'm-disp-table'})
    movies_info = [(movie.find('h3', attrs={'class': 'usetags'}).text, movie.find('a').attrs['href'])
                   for movie in movies]
    return movies_info


def get_afisha_movie_rating(soup: "class 'bs4.BeautifulSoup'") -> "float":
    rating_text = soup.find('p', attrs={'class': 'stars pngfix'}).attrs['title']
    if rating_text:
        rating_text = rating_text.split(' ')[2].split('\xa0')[0]
    else:  # no rating yet
        rating_text = "0"
    try:
        rating = float(rating_text.replace(',', '.'))
    except ValueError:
        rating = 0
        print("get rating value error: '{}'".format(rating_text))
    return rating


def get_movie_votes(soup: "class 'bs4.BeautifulSoup'") -> "int":
    votes_text = soup.find('p', attrs={'class': 'details s-update-clickcount'}).text.strip()
    if votes_text:
        votes_text = votes_text.split(' ')[1]
    else:
        votes_text = "0"
    try:
        votes = int(votes_text)
    except ValueError:
        votes = 0
        print("get votes value error: '{}'".format(votes_text))
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
        print("get year value error: '{}'".format(year_text))
    return year


def get_movie_cinemas(soup: "class 'bs4.BeautifulSoup'") -> "int":
    timetable_url = soup.find('a', attrs={'id': 'ctl00_CenterPlaceHolder_ucTab_rpTabs_ctl02_hlItem'}).attrs['href']
    movie_timetable_page = get_html_from_url("https://www.afisha.ru" + timetable_url)
    if movie_timetable_page['html']:
        soup2 = BeautifulSoup(movie_timetable_page['html'], "lxml")
        cinemas_list = soup2.find_all('td', attrs={'class': "b-td-item"})
        return len(cinemas_list)
    else:
        print("can't load movie's timetable page from afisha site, error {}".format(movie_timetable_page['err']))
        return 0


def fetch_movie_info(movie_title: "str", movie_url: "str") -> "tuple":
    movie_page = get_html_from_url(movie_url)
    if movie_page['html']:
        soup = BeautifulSoup(movie_page['html'], "lxml")
        votes = get_movie_votes(soup)
        rating = get_afisha_movie_rating(soup)
        year = get_movie_production_year(soup)
        cinemas = get_movie_cinemas(soup)
        return year, rating, votes, cinemas
    else:
        print("can't load movies page from afisha site, error {}".format(movie_page['err']))


def output_movies_to_console(movies_list: "list"):
    for movie_info in movies_list:
        # title, year, afisha_rating, afisha_votes, cinemas = movie_info
        print("{0}({1}) has rating {2}({3}) in {4} cinemas".format(*movie_info))


def main(min_rating, how_many_movies):
    list_of_movies_title_and_url = parse_afisha_list(fetch_afisha_page())
    print("today {} movies are in cinemas".format(len(list_of_movies_title_and_url)))
    top_movies_list = list()
    for title, url in list_of_movies_title_and_url:
        movie_info = fetch_movie_info(title, url)
        if movie_info:
            year, afisha_rating, afisha_votes, cinemas = movie_info
            if afisha_rating >= min_rating:
                top_movies_list.append((title, year, afisha_rating, afisha_votes, cinemas))
            # if afisha_rating == 0:
            #     print("movie {} has no rating yet".format(title))
    if how_many_movies <= len(top_movies_list):
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)[:how_many_movies]
    else:
        best_movies = sorted(top_movies_list, key=itemgetter(2), reverse=True)
    output_movies_to_console(best_movies)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="finds top N movies with star rating greater STARS")
    ap.add_argument("--n", dest="n", action="store", type=int, default=7, help="  number of movies")
    ap.add_argument("--stars", dest="stars", action="store", type=float, default=4.1, help="  stars rating")
    args = ap.parse_args(sys.argv[1:])

    main(args.stars, args.n)
