from django.db import models


class User(models.Model):
    telegram_id = models.CharField(max_length=50)
    role = models.CharField(max_length=20, default='user')


class EmbeddingModel(models.Model):
    user = models.ForeignKey('User', models.CASCADE, related_name='embeddings')
    name = models.CharField(max_length=50)
    epochs = models.PositiveSmallIntegerField(default=0)
    create_dt = models.DateTimeField(auto_now_add=True)
    path = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.create_dt.strftime('%d.%m.%Y %H:%M')} {self.name} (Эпохи: {self.epochs})"


class Movie(models.Model):
    name = models.CharField(max_length=150, unique=True)


class Link(models.Model):
    name = models.CharField(max_length=150, unique=True)
