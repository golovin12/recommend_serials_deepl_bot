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
            self._batchifier(positive_samples=positive_samples_per_batch, negative_ratio=10),
            epochs=epochs,
            steps_per_epoch=len(self.pairs) // positive_samples_per_batch,
            verbose=2
        )

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
            result.append(f"{self.movies[c][0]} {round(dists[c], 3)}")
        return result

    def similar_links(self, link):
        normalized_links = self._get_normalized_links()
        dists = np.dot(normalized_links, normalized_links[self.link_to_idx[link]])
        closest = np.argsort(dists)[-10:]
        result = []
        for c in reversed(closest):
            result.append(f"{self.top_links[c]} {round(dists[c], 3)}")
        return result

    def save(self, model_path):
        self.get_model().save(model_path)


def _get_emb_mod(model):
    emb_mod = AllLinksEmbedding(all_movies)
    emb_mod.model = keras.models.load_model(model.path)
    return emb_mod


def get_similar_films(model, film):
    embedding_model = usages_models.setdefault(model.id, _get_emb_mod(model))
    return embedding_model.similar_movies(film)


# model_all_links = AllLinksEmbedding(all_movies)
#
# model_all_links.fit_model(4, 512)
#
# model_all_links.similar_links('Harry Potter (film series)')
#
# model_all_links.similar_movies('Harry Potter (film series)')
