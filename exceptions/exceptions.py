from requests.exceptions import InvalidJSONError, RequestException


class BotException(Exception):
    """Неучтённые ошибки работы бота"""

    def __init__(self, *args: object) -> None:
        self.message = args[0] if args else 'Сбой работы программы'


class BotAPIException(RequestException):
    """Ошибки связи с API-сервисом"""

    def __init__(self, *args: object) -> None:
        self.message = args[0] if args else 'Ошибка связи с API-сервисом'


class BotJSONException(InvalidJSONError):
    """Ошибка распознавания json"""
    ...
