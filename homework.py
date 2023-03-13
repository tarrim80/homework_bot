import logging
import sys
import time
from http import HTTPStatus

import requests
import telegram

import settings
from exceptions import BotAPIException, BotException, BotJSONException

PRACTICUM_TOKEN = settings.PRACTICUM_TOKEN
TELEGRAM_TOKEN = settings.TELEGRAM_TOKEN
TELEGRAM_CHAT_ID = settings.TELEGRAM_CHAT_ID
RETRY_PERIOD = settings.RETRY_PERIOD
ENDPOINT = settings.ENDPOINT
HEADERS = settings.HEADERS
HOMEWORK_VERDICTS = settings.HOMEWORK_VERDICTS


logging.basicConfig(
    level=logging.DEBUG,
    filename='bot_all.log',
    filemode='w',
    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
    encoding='utf8'
)

logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s'
)
stream_handler = logging.StreamHandler(stream=sys.stdout)
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(tokens)


def send_message(bot: telegram.Bot, message: str):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено')
    except telegram.error.TelegramError as error:
        error_msg = f'Ошибка отправки сообщения: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)
    except BotException as error:
        error_msg = f'Сбой работы программы: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)


def get_api_answer(timestamp: int):
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        response = homework_statuses = requests.get(
            url=settings.ENDPOINT,
            headers=settings.HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        error_msg = f'Не получен ответ API-сервиса. Ошибка: {error}'
        logger.error(error_msg)

    if response.status_code != HTTPStatus.OK:
        error_msg = (
            f'Отрицательный ответ API-сервиса: {homework_statuses.status_code}'
        )
        logger.error(error_msg)
        raise BotAPIException(error_msg)

    try:
        homework_statuses = homework_statuses.json()
        logger.info('Получен ответ API-сервиса')
        return homework_statuses
    except BotJSONException as error:
        error_msg = f'Не распознан json. Ошибка: {error}'
        logger.error(error_msg)
        raise BotJSONException(error_msg)
    except BotException as error:
        error_msg = f'Неизвестный сбой. Ошибка: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    try:
        if not isinstance(response, dict):
            error_msg = 'Словарь не получен'
            logger.error(error_msg)
            raise TypeError(error_msg)
        elif 'homeworks' not in response.keys():
            error_msg = 'Не найдены домашние работы'
            logger.error(error_msg)
            raise KeyError(error_msg)
        elif not isinstance(response['homeworks'], list):
            error_msg = 'Список не получен'
            logger.error(error_msg)
            raise TypeError(error_msg)
    except BotException as error:
        logger.error(f'Ошибка проверки ответа API: {error}')
    else:
        logger.debug('ответ API соответствует документации')
        try:
            return response['homeworks'][0]
        except IndexError as error:
            error_msg = f'Ошибка индекса домашней работы: {error}'
            logger.error(error_msg)
        except BotException as error:
            error_msg = f'Сбой работы программы: {error}'
            logger.error(error_msg)


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус."""
    try:
        homework_name = homework['homework_name']
        status = homework.get('status')
        verdict = HOMEWORK_VERDICTS.get(status)
        if verdict is None:
            error_msg = f'Неожиданный статус: {status}'
            logger.error(error_msg)
            raise BotException(error_msg)
    except (KeyError, TypeError) as error:
        error_msg = f'Ошибка определения статуса: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)
    except BotException as error:
        error_msg = f'Сбой работы программы: {error}'
        logger.error(error_msg)
        raise BotException(error_msg)
    else:
        logger.debug(f'Статус работы "{homework_name}": {verdict}')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_msg = 'Отсутствие обязательных переменных окружения!'
        logger.critical(error_msg)
        sys.exit(error_msg)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if settings.BOT_DEBUG:
        timestamp = 1676224800
    else:
        timestamp = int(time.time())
    logger.debug('Начало работы')
    prev_status = ''
    prev_error = ''
    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            homework = check_response(response=response)
            status = parse_status(homework=homework)
            if status != prev_status:
                try:
                    send_message(bot, status)
                except BotException as error:
                    error_msg = f'Сбой в работе программы: {error}'
                    logger.error(error_msg)
                else:
                    prev_status = status
                    timestamp = response.get('current_date', timestamp)
            else:
                logger.debug('Статус проверки работы не изменился')

        except BotException as error:
            error_msg = f'Сбой в работе программы: {error}'
            if error_msg != prev_error:
                send_message(bot, error_msg)
                prev_error = error_msg
            logger.error(error_msg)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
