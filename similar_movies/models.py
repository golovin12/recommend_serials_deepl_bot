from django.db import models


class Movie(models.Model):
    name = models.CharField(max_length=150, unique=True)


class Link(models.Model):
    name = models.CharField(max_length=150, unique=True)
