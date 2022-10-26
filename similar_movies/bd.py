import os
import django
from asgiref.sync import sync_to_async
from django.db.models import Q

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "telegram_models.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

django.setup()

from similar_movies import models
from recommend_films import _get_default_model

usage_models = {"default": {"model": _get_default_model(),
                            "name": "default",
                            "epochs": 15}}

@sync_to_async
def get_model(model_id):
    return usage_models.get(model_id)


@sync_to_async
def get_user_models(user_id):
    user_model = usage_models.get(user_id)
    default_model = usage_models.get("default")
    if user_model:
        return default_model, user_model
    else:
        return default_model,


@sync_to_async
def save_user_model(user_id, model, name, epochs):
    usage_models[user_id] = {"model": model,
                             "name": name,
                             "epochs": epochs}


@sync_to_async
def fit_user_model(user_id, model, epochs):
    usage_models[user_id]['model'] = model
    usage_models[user_id]['epochs'] = usage_models[user_id]['epochs'] + epochs


@sync_to_async
def find_similar_film(film):
    movies = models.Movie.objects.filter(name__iexact=film)
    if movies.count() == 1:
        return movies.first(), True
    movies = models.Movie.objects.filter(name__icontains=film)
    return movies, False


@sync_to_async
def find_similar_link(link):
    links = models.Link.objects.filter(name__iexact=link)
    if links.count() == 1:
        return links.first(), True
    links = models.Link.objects.filter(name__icontains=link)
    return links, False
