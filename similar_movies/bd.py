import os
import django
from asgiref.sync import sync_to_async
from django.db.models import Q

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "telegram_models.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

django.setup()

from similar_movies import models


@sync_to_async
def get_model(model_id):
    return models.EmbeddingModel.objects.get(id=model_id)


@sync_to_async
def get_user_models(user_id):
    user, create = models.User.objects.get_or_create(telegram_id=user_id)
    user_models = models.EmbeddingModel.objects.filter(Q(user=user) | Q(user__role="default"))
    return user_models


@sync_to_async
def find_similar_film(film):
    print([film])
    movies = models.Movie.objects.filter(name__iexact=film)
    if movies.count() == 1:
        return movies.first(), True
    movies = models.Movie.objects.filter(name__icontains=film)
    return movies, False
