import random
import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message
import asyncpg
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Конфигурация базы данных PostgreSQL
DATABASE_URL = "postgresql://user:password@db:5432/mydatabase"


# Состояния для FSM
class AddParticipant(StatesGroup):
    waiting_for_username = State()


# Инициализация бота и диспетчера с хранилищем состояний
bot = Bot(token="7172997360:AAEZXp41IT13Yb2hkiGHaTXevwymW6_ggjg")
dp = Dispatcher(storage=MemoryStorage())


# Функция для чтения фраз из файла
def load_phrases(filename: str):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)


# Функция для чтения участников из файла
def load_participants(filename: str):
    with open(filename, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]


# Функция для добавления нового участника в файл
def add_participant(filename: str, username: str):
    with open(filename, 'a', encoding='utf-8') as file:
        file.write(f"{username}\n")


# Функция выбора победителя и отправки сообщений
async def start_game(message: Message, bot: Bot, conn):
    chat_id = message.chat.id

    # Загрузка участников и фраз из файлов
    participants = load_participants('participants.txt')
    phrases = load_phrases('phrases.json')

    if not participants:
        await message.answer("Список участников пустой.")
        return

    winner = random.choice(participants)

    # Запись победителя в базу данных
    await conn.execute('''
        INSERT INTO winners(chat_id, winner)
        VALUES($1, $2)
    ''', chat_id, winner)

    # Отправка сообщений с интервалом
    for phrase_list in phrases:
        phrase = random.choice(phrase_list)
        await bot.send_message(chat_id=chat_id, text=phrase)
        await asyncio.sleep(1)

    await message.answer(f"{random.choice(load_phrases('final.txt'))} @{winner}!")


# Функция для вывода списка победителей
async def list_winners(message: Message, conn):
    chat_id = message.chat.id

    # Группируем победителей по имени и считаем количество побед для каждого
    winners = await conn.fetch('''
        SELECT winner, COUNT(*) as wins 
        FROM winners 
        WHERE chat_id = $1 
        GROUP BY winner 
        ORDER BY wins DESC, winner ASC
    ''', chat_id)

    if winners:
        # Форматируем вывод в виде турнирной таблицы
        winners_list = "\n".join([f"{record['winner']}: {record['wins']} побед(ы)" for record in winners])
        await message.answer(f"Турнирная таблица:\n{winners_list}")
    else:
        await message.answer("Победителей пока нет.")


# Функция для отображения списка участников
async def list_participants(message: Message):
    participants = load_participants('participants.txt')

    if participants:
        participants_list = "\n".join([f"@{participant}" for participant in participants])
        await message.answer(f"Список участников:\n{participants_list}")
    else:
        await message.answer("Участников пока нет.")


# Хэндлер для команды /add
@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await message.answer("Введите имя участника в формате @username:")
    await state.set_state(AddParticipant.waiting_for_username)


# Хэндлер для обработки введенного имени пользователя
@dp.message(AddParticipant.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    username = message.text.strip()

    if username.startswith("@") and len(username) > 1:
        add_participant('participants.txt', username[1:])
        await message.answer(f"Участник {username} добавлен в игру!")
        await state.clear()
    else:
        await message.answer("Неверный формат. Имя пользователя должно начинаться с @. Попробуйте снова.")
        await state.clear()


# Регистрируем обработчик команды /game
@dp.message(Command("game"))
async def cmd_game(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    await start_game(message, bot, conn)
    await conn.close()


# Регистрируем обработчик команды /winners
@dp.message(Command("winners"))
async def cmd_winners(message: Message):
    conn = await asyncpg.connect(DATABASE_URL)
    await list_winners(message, conn)
    await conn.close()


# Регистрируем обработчик команды /participants
@dp.message(Command("participants"))
async def cmd_participants(message: Message):
    await list_participants(message)


# Создание таблицы в базе данных
async def create_table():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS winners(
            id SERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            winner TEXT NOT NULL
        )
    ''')
    await conn.close()


# Запуск процесса поллинга новых апдейтов
async def main():
    await create_table()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
