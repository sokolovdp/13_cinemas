# Cinemas
```
finds top N movies with star rating greater than STARS
usage: cinemas.py [--help] [--n N] [--stars STARS]
optional arguments:
  --help         show this help message and exit
  --n N          number of movies
  --stars STARS  stars rating
  --log          create log file 'cinemas_log_file.txt'
  --verbose      output debug information to console
```
# Sample output
```bazaar
today 2017-07-14 80 movies run in cinemas across city
7 top movies from 80 with best kp ratings are:
   {'title': 'Стражи Галактики. Часть 2', 'year': 2017, 'cinemas': 2, 'af_rating': 4.2, 'af_votes': 501, 'kp_id': 8412, 'kp_rating': 8.096, 'kp_votes': 1960}
   {'title': 'Сияние. Сияние', 'year': 1980, 'cinemas': 1, 'af_rating': 3.7, 'af_votes': 9117, 'kp_id': 5492, 'kp_rating': 8.021, 'kp_votes': 227286}
   {'title': 'Ла-Ла Ленд', 'year': 2016, 'cinemas': 1, 'af_rating': 3.9, 'af_votes': 677, 'kp_id': 8410, 'kp_rating': 7.821, 'kp_votes': 3671}
   {'title': 'Скафандр и бабочка', 'year': 2007, 'cinemas': 1, 'af_rating': 3.3, 'af_votes': 5554, 'kp_id': 7743, 'kp_rating': 7.817, 'kp_votes': 1191}
   {'title': 'Большой', 'year': 2016, 'cinemas': 4, 'af_rating': 4.0, 'af_votes': 217, 'kp_id': 1549, 'kp_rating': 7.788, 'kp_votes': 23422}
   {'title': 'Планета обезьян: Война', 'year': 2017, 'cinemas': 167, 'af_rating': 3.2, 'af_votes': 34, 'kp_id': 8192, 'kp_rating': 7.718, 'kp_votes': 13474}
   {'title': 'Босс-молокосос', 'year': 2017, 'cinemas': 1, 'af_rating': 4.1, 'af_votes': 335, 'kp_id': 8425, 'kp_rating': 7.666, 'kp_votes': 20834}

Process finished with exit code 0
```
# Project Goals
The code is written for educational purposes. Training course for web-developers - [DEVMAN.org](https://devman.org)
