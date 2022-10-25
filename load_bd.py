import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "telegram_models.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

django.setup()

import json

with open('wp_movies_10k.ndjson') as fin:
    all_movies = [json.loads(l) for l in fin]

from similar_movies import models

film_names = set()
links = set()
for movie in all_movies:
    film_names.add(movie[0])
    for link in movie[2]:
        links.add(link)

save_movies = []
for film_name in film_names:
    save_movies.append(models.Movie(name=film_name))
models.Movie.objects.bulk_create(save_movies)

save_links = []
for link in links:
    save_links.append(models.Link(name=link))
models.Link.objects.bulk_create(save_links)
