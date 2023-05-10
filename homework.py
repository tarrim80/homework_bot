import logging
import sys
import time
from datetime import datetime as dt
from http import HTTPStatus

import requests
import telegram
from requests.exceptions import InvalidJSONError

import settings
from exceptions import BotAPIException, BotException, BotJSONException

# === Для прохождения тестов === #
PRACTICUM_TOKEN = settings.PRACTICUM_TOKEN
TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
TELEGRAM_CHAT_ID = settings.TELEGRAM_CHAT_ID
RETRY_PERIOD = settings.RETRY_PERIOD
ENDPOINT = settings.ENDPOINT
HEADERS = settings.HEADERS
HOMEWORK_VERDICTS = settings.HOMEWORK_VERDICTS
# === === === === === === === === #

logging.basicConfig(
    level=logging.DEBUG,
    filename='bot_all.log',
    filemode='w',
    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
    encoding='utf8'
)


def init_logger(
    name: str = __name__,
    handler: logging.Handler = logging.StreamHandler(stream=sys.stdout),
    level: int = logging.DEBUG,
    format: str = '%(asctime)s, %(name)s, %(levelname)s, %(message)s'
) -> logging.Logger:
    """Инициализация экземпляра логгера."""
    logger = logging.getLogger(name)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format))
    logger.addHandler(handler)
    return logger


logger = init_logger(format='%(asctime)s, %(levelname)s, %(message)s')


def check_tokens() -> bool:
    """Проверка доступности переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено')
    except telegram.error.TelegramError as error:
        error_msg = f'Ошибка отправки сообщения: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)
    except Exception as error:
        error_msg = f'Сбой работы программы: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)


def get_api_answer(timestamp: int) -> dict:
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            url=settings.ENDPOINT,
            headers=settings.HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        error_msg = f'Не получен ответ API-сервиса. Ошибка: {error}'
        logger.error(error_msg)

    if response.status_code != HTTPStatus.OK:
        error_msg = (
            f'Отрицательный ответ API-сервиса: {response.status_code}'
        )
        logger.error(error_msg)
        raise BotAPIException(error_msg)

    try:
        homework_statuses = response.json()
        logger.info('Получен ответ API-сервиса')
        return homework_statuses
    except InvalidJSONError as error:
        error_msg = f'Не распознан json. Ошибка: {error}'
        logger.error(error_msg)
        raise BotJSONException(error_msg)
    except Exception as error:
        error_msg = f'Неизвестный сбой. Ошибка: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)


def check_response(response: dict) -> dict:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        error_msg = 'Словарь не получен'
        logger.error(error_msg)
        raise TypeError(error_msg)
    if 'homeworks' not in response:
        error_msg = 'Не найдены домашние работы'
        logger.error(error_msg)
        raise KeyError(error_msg)
    if not isinstance(response['homeworks'], list):
        error_msg = 'Список не получен'
        logger.error(error_msg)
        raise TypeError(error_msg)
    logger.debug('ответ API соответствует документации')

    return response['homeworks']

    # try:
    #     return response['homeworks'][0]
    # except IndexError as error:
    #     if error == 'list index out of range':
    #         error_msg = 'Новых домашних заданий нет'
    #     else:
    #         error_msg = f'Ошибка индекса домашней работы: {error}'
    #     logger.error(error_msg)
    #     raise BotException(error_msg)
    # except Exception as error:
    #     error_msg = f'Сбой работы программы: {error}'
    #     logger.error(error_msg)
    #     raise BotException(error_msg)


def parse_status(homework: dict) -> str:
    """Извлекает из информации о конкретной домашней работе статус."""
    try:
        homework_name = homework['homework_name']
    except KeyError as error:
        error_msg = f'Ошибка определения статуса: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)
    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        error_msg = f'Неожиданный статус: {status}'
        logger.error(error_msg)
        raise BotException(error_msg)
    logger.debug(f'Статус работы "{homework_name}": {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        error_msg = 'Отсутствие обязательных переменных окружения!'
        logger.critical(error_msg)
        sys.exit(error_msg)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if settings.BOT_DEBUG:
        timestamp = int(
            dt.strptime(
                '08.03.2023', '%d.%m.%Y'  # Старт проверок при отладке
            ).timestamp()
        )
    else:
        timestamp = int(time.time())
    logger.debug('Начало работы')
    prev_status = ''
    prev_error = ''
    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            homework = check_response(response=response)
            if len(homework) == 0:
                status = 'Новых выполненных домашних работ нет'
            else:
                status = parse_status(homework=homework[0])
            if status != prev_status:
                send_message(bot, status)
                prev_status = status
                timestamp = response.get('current_date', timestamp)
            else:
                logger.debug('Статус проверки работы не изменился')

        except Exception as error:
            error_msg = f'Сбой в работе программы: {error}'
            if error_msg != prev_error:
                send_message(bot, error_msg)
                prev_error = error_msg
            logger.error(error_msg)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
