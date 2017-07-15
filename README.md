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
today 2017-07-15 93 movies run in cinemas across city
7 top movies from 93 with best kp ratings are:
   {'title': 'Звезда пленительного счастья', 'year': 1975, 'cinemas': 1, 'af_rating': 4.2, 'af_votes': 51, 'kp_id': 4541, 'kp_rating': 8.252, 'kp_votes': 239754}
   {'title': 'Стражи Галактики. Часть 2', 'year': 2017, 'cinemas': 3, 'af_rating': 4.2, 'af_votes': 501, 'kp_id': 8412, 'kp_rating': 8.096, 'kp_votes': 1960}
   {'title': 'Ла-Ла Ленд', 'year': 2016, 'cinemas': 2, 'af_rating': 3.9, 'af_votes': 678, 'kp_id': 8410, 'kp_rating': 7.821, 'kp_votes': 3671}
   {'title': 'Галапагосы: Зачарованные острова', 'year': 2014, 'cinemas': 1, 'af_rating': 0.0, 'af_votes': 0, 'kp_id': 8229, 'kp_rating': 7.748, 'kp_votes': 12925}
   {'title': 'Планета обезьян: Война', 'year': 2017, 'cinemas': 169, 'af_rating': 3.2, 'af_votes': 54, 'kp_id': 8192, 'kp_rating': 7.718, 'kp_votes': 13479}
   {'title': 'Босс-молокосос', 'year': 2017, 'cinemas': 1, 'af_rating': 4.1, 'af_votes': 336, 'kp_id': 8425, 'kp_rating': 7.666, 'kp_votes': 20839}
   {'title': 'Гадкий я-3', 'year': 2017, 'cinemas': 167, 'af_rating': 3.5, 'af_votes': 203, 'kp_id': 8205, 'kp_rating': 7.646, 'kp_votes': 351}
Process finished with exit code 0
```
# Project Goals
The code is written for educational purposes. Training course for web-developers - [DEVMAN.org](https://devman.org)
