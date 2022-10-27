import locale

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from datetime import datetime, timedelta

from similar_movies.recommend_films import (
    get_similar_films, get_recommend_movies, get_similar_links, AllLinksEmbedding, UnicLinksEmbedding, FilmEmbedding,
    CategoryEmbedding, fit_embedding_model, add_fit_my_model
)
import bd
import config

TOKEN = config.TOKEN

locale.setlocale(locale.LC_ALL, "ru_RU.utf8")

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

embedding_model_names = {"1": ("На основе всех ссылок", AllLinksEmbedding),
                         "2": ("На основе всех ссылок (исключая дубли)", UnicLinksEmbedding),
                         "3": ("На основе ссылок категорий", CategoryEmbedding),
                         "4": ("На основе ссылок на фильмы", FilmEmbedding)}

best_films = ['Star Wars: The Force Awakens', 'The Martian (film)', 'Tangerine (film)', 'Straight Outta Compton (film)',
              'Brooklyn (film)', 'Carol (film)', 'Spotlight (film)']
worst_films = ['American Ultra', 'The Cobbler (2014 film)', 'Entourage (film)', 'Fantastic Four (2015 film)',
               'Get Hard', 'Hot Pursuit (2015 film)', 'Mortdecai (film)', 'Serena (2014 film)', 'Vacation (2015 film)']


class MessageStates(StatesGroup):
    start_action = State()
    similar_movie = State()
    similar_link = State()
    recommend_movie_best = State()
    recommend_movie_worst = State()
    embedding_size = State()
    fit_values = State()
    fit_my_model = State()


def get_dates_keyboard():
    keyboard = types.ReplyKeyboardMarkup()
    start_date = datetime.today() - timedelta(days=3)
    buttons = [types.KeyboardButton((start_date + timedelta(days=i)).strftime('%d.%m.%Y')) for i in range(7)]
    for button in buttons:
        keyboard.add(button)
    return keyboard


# Отвечает за запуск бота
@dp.message_handler(commands=['start'], state='*')
async def start_command(message: types.Message, state: FSMContext):
    hello_text = """
    Добро пожаловать. Данный бот позволяет обучить модель для рекомендации фильмов по ссылкам из википедии.\n
    Для начала выберите, что вы хотите сделать:
    """
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Работа с обученной моделью", callback_data="load_model"))
    keyboard.add(types.InlineKeyboardButton("Создать новую модель", callback_data="create_model"))
    await MessageStates.start_action.set()
    await bot.send_message(message.from_user.id, hello_text, reply_markup=keyboard)


# Вывод списка доступных моделей
@dp.callback_query_handler(lambda c: c.data == 'load_model', state=MessageStates.start_action)
async def load_model(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = types.InlineKeyboardMarkup()
    user_id = str(callback_query.from_user.id)
    user_models = await bd.get_user_models(user_id)
    for model in user_models:
        model_name = f'{model.get("name", "")} (Эпохи: {model.get("epochs")})'
        model_id = "default" if model.get("name", "") == "default" else user_id
        keyboard.add(types.InlineKeyboardButton(str(model_name), callback_data=f'get_model_{model_id}'))
    await callback_query.message.edit_text('Выберите модель, с которой хотите работать:', reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith('get_model_'), state=MessageStates.start_action)
async def get_model(callback_query: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as state_data:
        model_id = callback_query.data.split("_")[-1]
        state_data['model_id'] = model_id
    await callback_query.message.delete()

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Получить похожие фильмы", callback_data="similar_movies"))
    keyboard.add(types.InlineKeyboardButton("Получить похожие ссылки", callback_data="similar_links"))
    keyboard.add(types.InlineKeyboardButton("Получить рекомендации", callback_data="recommend_movies"))
    if model_id != "default":
        keyboard.add(types.InlineKeyboardButton("Дообучить модель", callback_data="fit_my_model"))
    await callback_query.message.answer(text='Выберите действие:', reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == 'similar_movies', state=MessageStates.start_action)
async def similar_movies(callback_query: types.CallbackQuery, state: FSMContext):
    await MessageStates.similar_movie.set()
    await callback_query.message.delete()
    await callback_query.message.answer('Введите название фильма:')
    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(state=MessageStates.similar_movie)
async def get_similar_film(message: types.Message, state: FSMContext):
    films, find = await bd.find_similar_film(message.text)
    if find:
        async with state.proxy() as state_data:
            model_id = state_data['model_id']
        model = await bd.get_model(model_id)
        model = model["model"]
        similar_films = "\n* ".join(get_similar_films(model, films.name))
        await message.answer(f"Похожие фильмы: \n{similar_films}")
    else:
        similar_films = "\n* ".join([film.name for film in films])
        await message.answer("Не найден фильм с таким названием, попробуйте ещё раз.\n"
                             f"Список похожих фильмов: \n{similar_films}")


@dp.callback_query_handler(lambda c: c.data == 'similar_links', state=MessageStates.start_action)
async def similar_links(callback_query: types.CallbackQuery, state: FSMContext):
    await MessageStates.similar_link.set()
    await callback_query.message.delete()
    await callback_query.message.answer('Введите название ссылки:')
    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(state=MessageStates.similar_link)
async def get_similar_link(message: types.Message, state: FSMContext):
    links, find = await bd.find_similar_link(message.text)
    if find:
        async with state.proxy() as state_data:
            model_id = state_data['model_id']
        model = await bd.get_model(model_id)
        model = model.get("model")
        similar_links = "\n* ".join(get_similar_links(model, links.name))
        await message.answer(f"Похожие ссылки: \n{similar_links}")
    else:
        similar_links = "\n* ".join([link.name for link in links])
        await message.answer("Не найдена ссылка с таким названием, попробуйте ещё раз.\n"
                             f"Список похожих ссылок: \n{similar_links}")


@dp.callback_query_handler(lambda c: c.data == 'recommend_movies', state=MessageStates.start_action)
async def recommend_movie_best(callback_query: types.CallbackQuery, state: FSMContext):
    await MessageStates.recommend_movie_best.set()
    await callback_query.message.delete()
    keyboard = types.ReplyKeyboardMarkup()
    keyboard.add(types.KeyboardButton("По умолчанию"))
    await callback_query.message.answer('Введите лучшие фильмы (через запятую).\n'
                                        'Или нажмите на кнопку "По умолчанию", чтобы применить: \n\n'
                                        f'{", ".join(best_films)}',
                                        reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(state=MessageStates.recommend_movie_best)
async def get_recommend_best(message: types.Message, state: FSMContext):
    if message.text == "По умолчанию":
        recommend_movie_best = best_films
    else:
        recommend_movie_best = message.text.split(", ")

    keyboard = types.ReplyKeyboardMarkup()
    keyboard.add(types.KeyboardButton("По умолчанию"))
    if len(recommend_movie_best) > 0:
        async with state.proxy() as state_data:
            state_data['best'] = recommend_movie_best
        await MessageStates.recommend_movie_worst.set()
        await message.answer('Введите худшие фильмы (через запятую).\n'
                             'Или нажмите на кнопку "По умолчанию", чтобы применить: \n\n'
                             f'{", ".join(worst_films)}', reply_markup=keyboard)
    else:
        await message.answer('Введите лучшие фильмы (через запятую).\n'
                             'Или нажмите на кнопку "По умолчанию", чтобы применить: \n\n'
                             f'{", ".join(best_films)}', reply_markup=keyboard)


@dp.message_handler(state=MessageStates.recommend_movie_worst)
async def get_recommend_worst(message: types.Message, state: FSMContext):
    if message.text == "По умолчанию":
        recommend_movie_worst = worst_films
    else:
        recommend_movie_worst = message.text.split(", ")
    if len(recommend_movie_worst) > 0:
        try:
            await MessageStates.recommend_movie_best.set()
            async with state.proxy() as state_data:
                recommend_movie_best = state_data['best']
                model_id = state_data['model_id']
            model = await bd.get_model(model_id)
            model = model.get("model")
            best, worst = get_recommend_movies(model, recommend_movie_best, recommend_movie_worst)
            best = "\n* ".join(best)
            worst = "\n* ".join(worst)
            await message.answer(f'Лучшие фильмы: \n{best}\n\n'
                                 f'Худшие фильмы: \n{worst}')
        except Exception as e:
            keyboard = types.ReplyKeyboardMarkup()
            keyboard.add(types.KeyboardButton("По умолчанию"))
            await message.answer(f"Не удалось получить рекомендации: {e}")
            await message.answer('Введите лучшие фильмы (через запятую).\n'
                                 'Или нажмите на кнопку "По умолчанию", чтобы применить: \n\n'
                                 f'{", ".join(best_films)}', reply_markup=keyboard)
    else:
        keyboard = types.ReplyKeyboardMarkup()
        keyboard.add(types.KeyboardButton("По умолчанию"))
        await message.answer('Введите худшие фильмы (через запятую).\n'
                             'Или нажмите на кнопку "По умолчанию", чтобы применить: \n\n'
                             f'{", ".join(worst_films)}', reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == 'create_model', state=MessageStates.start_action)
async def create_model(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = types.InlineKeyboardMarkup()
    for model_id, model_name_class in embedding_model_names.items():
        keyboard.add(types.InlineKeyboardButton(model_name_class[0], callback_data=f'new_model_{model_id}'))
    await callback_query.message.edit_text('Выберите какую модель хотите обучить', reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith('new_model_'), state=MessageStates.start_action)
async def get_model(callback_query: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as state_data:
        state_data['fit_model_id'] = callback_query.data.split("_")[-1]
    await callback_query.message.delete()
    await MessageStates.embedding_size.set()
    keyboard = types.ReplyKeyboardMarkup()
    keyboard.add(types.KeyboardButton("По умолчанию"))
    await callback_query.message.answer('Укажите embedding_size.\n'
                                        'Или нажмите на кнопку "По умолчанию", чтобы применить: 50',
                                        reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(state=MessageStates.embedding_size)
async def get_embedding_size(message: types.Message, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup()
    keyboard.add(types.KeyboardButton("По умолчанию"))
    if message.text == "По умолчанию":
        message.text = "50"

    if message.text.isdigit() and int(message.text) > 0:
        async with state.proxy() as state_data:
            state_data['embedding_size'] = int(message.text)
        await MessageStates.fit_values.set()
        await message.answer("Введите количество эпох обучения, positive_samples_per_batch и negative_ratio\n"
                             "Или нажмите на кнопку 'По умолчанию', чтобы применить: 15, 512, 10",
                             reply_markup=keyboard)
    else:
        await message.answer("Введите целое, положительное число", reply_markup=keyboard)


@dp.message_handler(state=MessageStates.fit_values)
async def fit_model_from_values(message: types.Message, state: FSMContext):
    if message.text == "По умолчанию":
        message.text = "15, 512, 10"
    fit_values = message.text.split(", ")
    if len(fit_values) == 3 and all([bool(item.isdigit() and int(item) > 0) for item in fit_values]):
        async with state.proxy() as state_data:
            fit_model_id = state_data['fit_model_id']
            embedding_size = state_data['embedding_size']
        model_name, model_class = embedding_model_names.get(fit_model_id)
        await message.answer("Подожите, идёт процесс обучения модели")
        result_model, result = fit_embedding_model(model_class, embedding_size, *[int(item) for item in fit_values])
        await bd.save_user_model(str(message.from_user.id), result_model, model_name, int(fit_values[0]))
        await message.answer(f"Результат обучения модели:\n {result}")
        await message.answer("Нажмите /start для продолжения работы с моделью\n"
                             "Или введите значения для переобучения модели")
    else:
        keyboard = types.ReplyKeyboardMarkup()
        keyboard.add(types.KeyboardButton("По умолчанию"))
        await message.answer("Введите целое, положительное число", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == 'fit_my_model', state=MessageStates.start_action)
async def get_similar_film(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = types.ReplyKeyboardMarkup()
    keyboard.add(types.KeyboardButton("По умолчанию"))
    await MessageStates.fit_my_model.set()
    await callback_query.message.answer(
        "Введите количество эпох обучения, positive_samples_per_batch и negative_ratio\n"
        "Или нажмите на кнопку 'По умолчанию', чтобы применить: 15, 512, 10",
        reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(state=MessageStates.fit_my_model)
async def fit_my_model(message: types.Message, state: FSMContext):
    if message.text == "По умолчанию":
        message.text = "15, 512, 10"
    fit_values = message.text.split(", ")
    if len(fit_values) == 3 and all([bool(item.isdigit() and int(item) > 0) for item in fit_values]):
        model = await bd.get_model(str(message.from_user.id))
        model = model['model']
        await message.answer("Подожите, модель дообучивается")
        result_model, result = add_fit_my_model(model, *[int(item) for item in fit_values])
        await bd.fit_user_model(str(message.from_user.id), result_model, int(fit_values[0]))
        await message.answer(f"Результат обучения модели:\n {result}")
        await message.answer("Нажмите /start для продолжения работы с моделью\n"
                             "Или введите значения для дообучения модели")
    else:
        keyboard = types.ReplyKeyboardMarkup()
        keyboard.add(types.KeyboardButton("По умолчанию"))
        await message.answer("Введите целое, положительное число", reply_markup=keyboard)


async def shutdown(dp: Dispatcher):
    await dp.storage.close()
    await dp.storage.wait_closed()


def main():
    executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)


if __name__ == '__main__':
    main()
