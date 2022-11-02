import os
import django
from asgiref.sync import sync_to_async

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "telegram_models.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

django.setup()

from similar_movies import models
from recommend_films import _get_default_model

usage_models = {"default": {"model": _get_default_model(),
                            "name": "default",
                            "view_name": "На основе всех ссылок",
                            "epochs": 15},
                "default2": {"model": _get_default_model('2'),
                            "name": "default2",
                            "view_name": "На основе всех ссылок (исключая дубли)",
                            "epochs": 15},
                "default3": {"model": _get_default_model('3'),
                            "name": "default3",
                            "view_name": "На основе ссылок категорий",
                            "epochs": 15},
                "default4": {"model": _get_default_model('4'),
                            "name": "default4",
                            "view_name": "На основе ссылок на фильмы",
                            "epochs": 15},
                }


@sync_to_async
def get_model(model_id):
    return usage_models.get(model_id)


@sync_to_async
def get_user_models(user_id):
    user_model = usage_models.get(user_id)
    default_models = (usage_models.get("default"), usage_models.get("default2"), usage_models.get("default3"),
                      usage_models.get("default4"))
    if user_model:
        return *default_models, user_model
    else:
        return *default_models,


@sync_to_async
def save_user_model(user_id, model, name, epochs):
    usage_models[user_id] = {"model": model,
                             "name": name,
                             "view_name": name,
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
