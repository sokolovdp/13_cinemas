import re

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

KINOPOISK_API_RATING_URL = "https://www.kinopoisk.ru/rating/{}.xml"
KINOPOISK_API_SEARH_URL = "https://www.kinopoisk.ru/search/handler-chromium-extensions"
KINOPOISK_MOVIE_ID_PATTERN = re.compile(r"www.kinopoisk.ru/film/(\d+)")

NPSB = '\xa0'
MIN_SLEEP = 1.5
MAX_SLEEP = 3.0
MAX_TIMEOUT = 6
MAX_RETRIES = 4
MAX_TOP_MOVIES = 21
SOUP_PARSER = 'html.parser'
