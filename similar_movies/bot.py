import json
import locale

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.utils.markdown import hbold
from datetime import datetime, timedelta

from similar_movies.recommend_films import get_similar_films
import bd

TOKEN = "5111173937:AAHfb2UN0mnRhBLJ4m7Xk7r7DYu44uQH2LQ"
NAME = "Test_telegram_bot"

locale.setlocale(locale.LC_ALL, "ru_RU.utf8")

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

embedding_model_names = {"1": "На основе всех ссылок",
                         "2": "На основе всех ссылок (исключая дубли)",
                         "3": "На основе ссылок категорий",
                         "4": "На основе ссылок на фильмы"}


class MessageStates(StatesGroup):
    start_action = State()
    similar_movie = State()
    similar_link = State()
    recommend_movie_best = State()
    recommend_movie_worst = State()
    embedding_size = State()


def get_dates_keyboard():
    keyboard = types.ReplyKeyboardMarkup()
    start_date = datetime.today() - timedelta(days=3)
    buttons = [types.KeyboardButton((start_date + timedelta(days=i)).strftime('%d.%m.%Y')) for i in range(7)]
    for button in buttons:
        keyboard.add(button)
    return keyboard


# Отвечает за запуск бота
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    hello_text = """
    Добро пожаловать. Данный бот позволяет обучить модель для рекомендации фильмов по ссылкам из википедии.\n
    Для начала выберите, что вы хотите сделать:
    """
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Работа с обученной моделью", callback_data="load_model"))
    keyboard.add(types.InlineKeyboardButton("Обучить свою модель", callback_data="create_model"))
    await MessageStates.start_action.set()
    await bot.send_message(message.from_user.id, hello_text, reply_markup=keyboard)


# Вывод списка доступных моделей
@dp.callback_query_handler(lambda c: c.data == 'load_model', state=MessageStates.start_action)
async def load_model(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = types.InlineKeyboardMarkup()
    user_id = callback_query.from_user.id
    user_models = await bd.get_user_models(user_id)
    for model in user_models:
        keyboard.add(types.InlineKeyboardButton(str(model), callback_data=f'get_model_{model.id}'))
    keyboard.add(types.InlineKeyboardButton('Выход', callback_data='exit'))
    await callback_query.message.edit_text('Выберите модель, с которой хотите работать:',
                                           reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith('get_model_'), state=MessageStates.start_action)
async def get_model(callback_query: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as state_data:
        state_data['model_id'] = callback_query.data.split("_")[-1]
    await callback_query.message.delete()

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Получить похожие фильмы", callback_data="similar_movies"))
    keyboard.add(types.InlineKeyboardButton("Получить похожие ссылки", callback_data="similar_links"))
    keyboard.add(types.InlineKeyboardButton("Получить рекомендации", callback_data="recommend_movies"))
    keyboard.add(types.InlineKeyboardButton('Выход', callback_data='exit'))
    await callback_query.message.answer(text='Выберите действие:',
                                        reply_markup=keyboard)


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
        similar_films = "\n".join(get_similar_films(model, films.name))
        await message.answer(f"Похожие фильмы: \n{similar_films}")
    else:
        similar_films = "\n ".join([film.name for film in films])
        await message.answer("Не найден фильм с таким названием, попробуйте ещё раз.\n"
                             f"Список похожих фильмов: {similar_films}")


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
        similar_links = "\n".join(get_similar_films(model, links.name))
        await message.answer(f"Похожие ссылки: \n{similar_links}")
    else:
        similar_links = "\n ".join([link.name for link in links])
        await message.answer("Не найдена ссылка с таким названием, попробуйте ещё раз.\n"
                             f"Список похожих ссылок: {similar_links}")


@dp.callback_query_handler(lambda c: c.data == 'recommend_movies', state=MessageStates.start_action)
async def recommend_movie_best(callback_query: types.CallbackQuery, state: FSMContext):
    await MessageStates.recommend_movie_best.set()
    await callback_query.message.delete()
    await callback_query.message.answer('Введите лучшие фильмы (через запятую).\n'
                                        'Или нажмите на кнопку "По умолчанию", чтобы применить: ')
    # todo add films
    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(state=MessageStates.recommend_movie_best)
async def get_recommend_best(message: types.Message, state: FSMContext):
    recommend_movie_best = message.text.split(", ")
    if len(recommend_movie_best) > 0:
        async with state.proxy() as state_data:
            state_data['best'] = recommend_movie_best
        await MessageStates.recommend_movie_worst.set()
        # todo add films
        await message.answer('Введите худшие фильмы (через запятую).\n'
                             'Или нажмите на кнопку "По умолчанию", чтобы применить: ')
    else:
        # todo add films
        await message.answer('Введите лучшие фильмы (через запятую).\n'
                             'Или нажмите на кнопку "По умолчанию", чтобы применить: ')


@dp.message_handler(state=MessageStates.recommend_movie_worst)
async def get_recommend_worst(message: types.Message, state: FSMContext):
    recommend_movie_worst = message.text.split(", ")
    if len(recommend_movie_worst) > 0:
        async with state.proxy() as state_data:
            recommend_movie_best = state_data['best']
        best, worst = get_recommend_movies(recommend_movie_best, recommend_movie_worst)
        await message.answer(f'Лучшие фильмы: {best}\n'
                             f'Худшие фильмы: {worst}')
    else:
        # todo add films
        await message.answer('Введите худшие фильмы (через запятую).\n'
                             'Или нажмите на кнопку "По умолчанию", чтобы применить: ')


@dp.callback_query_handler(lambda c: c.data == 'create_model', state=MessageStates.start_action)
async def load_model(callback_query: types.CallbackQuery, state: FSMContext):
    keyboard = types.InlineKeyboardMarkup()
    for model_id, model_name in embedding_model_names.items():
        keyboard.add(types.InlineKeyboardButton(model_name, callback_data=f'new_model_{model_id}'))
    keyboard.add(types.InlineKeyboardButton('Выход', callback_data='exit'))
    await callback_query.message.edit_text('Выберите какую модель хотите обучить',
                                           reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith('get_model_'), state=MessageStates.start_action)
async def get_model(callback_query: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as state_data:
        state_data['new_id'] = callback_query.data.split("_")[-1]
    await callback_query.message.delete()

    # todo add size
    await callback_query.message.answer('Укажите embedding_size.\n'
                                        'Или нажмите на кнопку "По умолчанию", чтобы применить: ')

# todo доделать.
@dp.message_handler(state=MessageStates.similar_movie)
async def get_similar_film(message: types.Message, state: FSMContext):
    films, find = await bd.find_similar_film(message.text)
    if find:
        async with state.proxy() as state_data:
            model_id = state_data['model_id']
        model = await bd.get_model(model_id)
        similar_films = "\n".join(get_similar_films(model, films.name))
        await message.answer(f"Похожие фильмы: \n{similar_films}")
    else:
        similar_films = "\n ".join([film.name for film in films])
        await message.answer("Не найден фильм с таким названием, попробуйте ещё раз.\n"
                             f"Список похожих фильмов: {similar_films}")
#
#
#
# @dp.callback_query_handler(lambda c: c.data.startswith('get_flight_info_'), state=MessageStates.value)
# async def flight_info_get_date(callback_query: types.CallbackQuery, state: FSMContext):
#     async with state.proxy() as state_data:
#         state_data['flight_name'] = callback_query.data.split("_")[-1]
#     await MessageStates.date.set()
#     await callback_query.message.delete()
#     await callback_query.message.answer(text='Выберите дату, за которую хотите получить информацию или введите свою',
#                                         reply_markup=get_dates_keyboard())
#
#
# @dp.message_handler(state=MessageStates.date)
# async def flight_info_get_date(message: types.Message, state: FSMContext):
#     try:
#         dep_date = datetime.strptime(message.text, "%d.%m.%Y")
#         async with state.proxy() as state_data:
#             flight_name = state_data.get('flight_name')
#         flight = await bd.get_flight(flight_name, dep_date)
#
#         await MessageStates.action.set()
#         keyboard = types.InlineKeyboardMarkup()
#         keyboard.add(types.InlineKeyboardButton("Посмотреть сообщения", callback_data=f"read_messages_{flight.id}"))
#         keyboard.add(types.InlineKeyboardButton("Добавить сообщение", callback_data=f"add_message_{flight.id}"))
#         await message.answer("Выберите, что хотите сделать:", reply_markup=keyboard)
#
#     except Exception as e:
#         print(e)
#         await message.answer(text="Пожалуйста, введите корректную дату!")
#
#
# @dp.callback_query_handler(lambda c: c.data.startswith('read_messages_'), state=MessageStates.action)
# async def flight_info_read_messages(callback_query: types.CallbackQuery, state: FSMContext):
#     await state.reset_state()
#     flight_id = callback_query.data.split("_")[-1]
#     text = "<b>Лог сообщений:</b>"
#     for msg in await bd.get_flight_messages(flight_id):
#         text += f"\n<i>{msg.time_create.strftime('%H:%M:%S %d.%m.%Y')}</i>\n<b>{msg.user.username}</b>: {msg.message}\n"
#     await callback_query.message.answer(text=text)
#
#
# @dp.callback_query_handler(lambda c: c.data.startswith('add_message_'), state=MessageStates.action)
# async def flight_info_add_message(callback_query: types.CallbackQuery, state: FSMContext):
#     async with state.proxy() as state_data:
#         state_data['flight_id'] = callback_query.data.split("_")[-1]
#     text = "Введите сообщение:"
#     await MessageStates.add_msg.set()
#     await callback_query.message.answer(text=text)
#
#
# @dp.message_handler(state=MessageStates.add_msg)
# async def flight_info_add_msg_by_flight(message: types.Message, state: FSMContext):
#     async with state.proxy() as state_data:
#         flight_id = state_data.get('flight_id')
#     await bd.user_add_message(message.from_user.username, flight_id, message.text)
#     await state.reset_state()
#     await message.answer("Успешно!")


async def shutdown(dp: Dispatcher):
    await dp.storage.close()
    await dp.storage.wait_closed()


def main():
    executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)
