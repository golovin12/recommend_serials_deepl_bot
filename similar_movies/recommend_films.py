import json
from collections import Counter
from keras.models import Model
from keras.layers import Embedding, Input, Reshape
from keras.layers.merge import Dot
from sklearn.linear_model import LinearRegression
import numpy as np
import keras
import random
from sklearn import svm

usages_models = dict()

with open('wp_movies_10k.ndjson') as fin:
    all_movies = [json.loads(l) for l in fin]


class AllLinksEmbedding:
    def __init__(self, movies, embedding_size=50):
        self.movies = movies
        self.embedding_size = embedding_size
        self._set_data()
        self.model = None
        self.normalized_movies = None
        self.normalized_links = None

    def get_model(self):
        if self.model is None:
            self.model = self._get_movie_embedding_model()
        return self.model

    def _get_links_counter(self):
        link_counts = Counter()
        for movie in self.movies:
            link_counts.update(movie[2])
        return link_counts

    def _set_data(self):
        top_links = [link for link, c in self._get_links_counter().items() if c >= 3]
        link_to_idx = {link: idx for idx, link in enumerate(top_links)}
        movie_to_idx = {movie[0]: idx for idx, movie in enumerate(self.movies)}
        pairs = []
        for movie in self.movies:
            pairs.extend((link_to_idx[link], movie_to_idx[movie[0]]) for link in movie[2] if link in link_to_idx)
        pairs_set = set(pairs)

        self.top_links = top_links
        self.link_to_idx = link_to_idx
        self.movie_to_idx = movie_to_idx
        self.pairs = pairs
        self.pairs_set = pairs_set

    def _get_movie_embedding_model(self):
        embedding_size = self.embedding_size
        link = Input(name='link', shape=(1,))
        movie = Input(name='movie', shape=(1,))
        link_embedding = Embedding(name='link_embedding',
                                   input_dim=len(self.top_links),
                                   output_dim=embedding_size)(link)
        movie_embedding = Embedding(name='movie_embedding',
                                    input_dim=len(self.movie_to_idx),
                                    output_dim=embedding_size)(movie)
        dot = Dot(name='dot_product', normalize=True, axes=2)([link_embedding, movie_embedding])
        merged = Reshape((1,))(dot)
        model = Model(inputs=[link, movie], outputs=[merged])
        model.compile(optimizer='nadam', loss='mse')
        return model

    def _batchifier(self, positive_samples=50, negative_ratio=10):
        batch_size = positive_samples * (1 + negative_ratio)
        batch = np.zeros((batch_size, 3))
        while True:
            for idx, (link_id, movie_id) in enumerate(random.sample(self.pairs, positive_samples)):
                batch[idx, :] = (link_id, movie_id, 1)
            idx = positive_samples
            while idx < batch_size:
                movie_id = random.randrange(len(self.movie_to_idx))
                link_id = random.randrange(len(self.top_links))
                if not (link_id, movie_id) in self.pairs_set:
                    batch[idx, :] = (link_id, movie_id, -1)
                    idx += 1
            np.random.shuffle(batch)
            yield {'link': batch[:, 0], 'movie': batch[:, 1]}, batch[:, 2]

    def fit_model(self, epochs=15, positive_samples_per_batch=512, negative_ratio=10):
        self.get_model().fit_generator(
            self._batchifier(positive_samples=positive_samples_per_batch, negative_ratio=negative_ratio),
            epochs=epochs,
            steps_per_epoch=len(self.pairs) // positive_samples_per_batch,
            verbose=2
        )
        return self.get_model().history.history

    def _get_normalized_movies(self):
        if self.normalized_movies is None:
            movie = self.get_model().get_layer('movie_embedding')
            movie_weights = movie.get_weights()[0]
            movie_lengths = np.linalg.norm(movie_weights, axis=1)
            self.normalized_movies = (movie_weights.T / movie_lengths).T
        return self.normalized_movies

    def _get_normalized_links(self):
        if self.normalized_links is None:
            link = self.get_model().get_layer('link_embedding')
            link_weights = link.get_weights()[0]
            link_lengths = np.linalg.norm(link_weights, axis=1)
            self.normalized_links = (link_weights.T / link_lengths).T
        return self.normalized_links

    def similar_movies(self, movie):
        normalized_movies = self._get_normalized_movies()
        dists = np.dot(normalized_movies, normalized_movies[self.movie_to_idx[movie]])
        closest = np.argsort(dists)[-10:]
        result = []
        for c in reversed(closest):
            result.append(f"{self.movies[c][0]} {str(dists[c])[:6]}")
        return result

    def similar_links(self, link):
        normalized_links = self._get_normalized_links()
        dists = np.dot(normalized_links, normalized_links[self.link_to_idx[link]])
        closest = np.argsort(dists)[-10:]
        result = []
        for c in reversed(closest):
            result.append(f"{self.top_links[c]} {str(dists[c])[:6]}")
        return result

    def save(self, model_path):
        self.get_model().save(model_path)


class UnicLinksEmbedding(AllLinksEmbedding):

    def _get_links_counter(self):
        link_counts = Counter()
        for movie in self.movies:
            link_counts.update(list(set(movie[2])))
        return link_counts


class CategoryEmbedding(AllLinksEmbedding):

    def _get_links_counter(self):
        link_counts = Counter()
        for movie in self.movies:
            link_counts.update(list(item for item in movie[2] if item.startswith("Category:")))
        return link_counts


class FilmEmbedding(AllLinksEmbedding):

    def _get_links_counter(self):
        link_counts = Counter()
        unic_names = set(item[0] for item in self.movies)
        for movie in self.movies:
            link_counts.update([item for item in movie[2] if item in unic_names])
        return link_counts


def _get_default_model():
    emb_mod = AllLinksEmbedding(all_movies)
    emb_mod.model = keras.models.load_model("media/default")
    return emb_mod


def get_similar_films(embedding_model, film):
    return embedding_model.similar_movies(film)


def get_similar_links(embedding_model, link):
    return embedding_model.similar_links(link)


class EstimatedMovie:
    def __init__(self, embedding_model, train_class, best, worst, **train_params):
        self.embedding_model = embedding_model
        self.train_class = train_class
        self.best = best
        self.worst = worst
        self.train_params = train_params

    def _get_X_y(self):
        y = np.asarray([1 for _ in self.best] + [0 for _ in self.worst])
        X = np.asarray(
            [self.embedding_model._get_normalized_movies()[self.embedding_model.movie_to_idx[movie]] for movie in
             self.best + self.worst])
        return X, y

    def fit_model(self):
        self.model = self.train_class(**self.train_params)
        self.model.fit(*self._get_X_y())

    def get_estimated_movie_rating(self, count):
        estimated_movie_ratings = self.model.decision_function(self.embedding_model._get_normalized_movies())
        best = np.argsort(estimated_movie_ratings)
        bests = []
        for c in reversed(best[-count:]):
            bests.append(f"{self.embedding_model.movies[c][0]} {str(estimated_movie_ratings[c])[:6]}")

        worsts = []
        for c in best[:count]:
            worsts.append(f"{self.embedding_model.movies[c][0]} {str(estimated_movie_ratings[c])[:6]}")
        return bests, worsts

    def get_info(self):
        rotten_y = np.asarray([float(movie[-2][:-1]) / 100 for movie in self.embedding_model.movies if movie[-2]])
        rotten_X = np.asarray(
            [self.embedding_model._get_normalized_movies()[self.embedding_model.movie_to_idx[movie[0]]] for movie in
             self.embedding_model.movies if movie[-2]])
        TRAINING_CUT_OFF = int(len(rotten_X) * 0.8)
        regr = LinearRegression()
        regr.fit(rotten_X[:TRAINING_CUT_OFF], rotten_y[:TRAINING_CUT_OFF])
        error = (regr.predict(rotten_X[TRAINING_CUT_OFF:]) - rotten_y[TRAINING_CUT_OFF:])
        print('mean square error %2.2f' % np.mean(error ** 2))
        error = (np.mean(rotten_y[:TRAINING_CUT_OFF]) - rotten_y[TRAINING_CUT_OFF:])
        print('mean square error %2.2f' % np.mean(error ** 2))


def get_recommend_movies(model, best, worst):
    m1 = EstimatedMovie(model, svm.SVC, best, worst, kernel='linear')
    m1.fit_model()
    return m1.get_estimated_movie_rating(10)


def fit_embedding_model(embedding_model_class, embedding_size, epochs, positive_samples_per_batch, negative_ratio):
    embedding_model = embedding_model_class(all_movies, embedding_size)
    fit_result = embedding_model.fit_model(epochs, positive_samples_per_batch, negative_ratio)
    return embedding_model, fit_result


def add_fit_my_model(embedding_model, epochs, positive_samples_per_batch, negative_ratio):
    fit_result = embedding_model.fit_model(epochs, positive_samples_per_batch, negative_ratio)
    return embedding_model, fit_result
