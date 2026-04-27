"""Helper для форматирования и валидации номера телефона."""

import re

PHONE_FORMAT = "+7(000)000-00-00"
PHONE_REGEX = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")


def _extract_digits(phone: str) -> str:
    """Извлекает все цифры из строки."""
    return re.sub(r"\D", "", phone)


def _is_valid_phone_digits(digits: str) -> bool:
    """Проверяет, что номер содержит 11 цифр и начинается с 7."""
    return len(digits) == 11 and digits.startswith("7")


def _digits_to_formatted(digits: str) -> str:
    """Преобразует цифры в форматированный вид +7(XXX)XXX-XX-XX."""
    return f"+{digits[0]}({digits[1:4]}){digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def format_phone(phone: str) -> str:
    """
    Форматирует номер в формат +7(000)000-00-00.
    
    Принимает номер в формате +7(XXX)XXX-XX-XX или 7XXXXXXXXXX.
    Возвращает всегда в формате +7(XXX)XXX-XX-XX.
    
    Args:
        phone: Номер в формате +7(XXX)XXX-XX-XX или 7XXXXXXXXXX
        
    Returns:
        Отформатированный номер в формате +7(XXX)XXX-XX-XX
        
    Raises:
        ValueError: Если номер не соответствует формату
    """
    digits = _extract_digits(phone)
    
    if _is_valid_phone_digits(digits):
        return _digits_to_formatted(digits)
    
    raise ValueError(
        f"Неверный формат номера телефона. Ожидается формат: {PHONE_FORMAT}"
    )


def parse_formatted_phone(phone: str) -> str:
    """
    Извлекает цифровое значение из номер телефона.
    
    Args:
        phone: Номер в формате +7(XXX)XXX-XX-XX или 7XXXXXXXXXX
        
    Returns:
        Цифровой номер (например 70000000000)
    """
    digits = _extract_digits(phone)
    
    if _is_valid_phone_digits(digits):
        return digits
    
    raise ValueError(
        f"Неверный формат номера телефона. Ожидается формат: {PHONE_FORMAT}"
    )


def validate_phone(phone: str) -> tuple[str, str]:
    """
    Валидирует номер и возвращает оба значения (форматированный и цифровой).
    
    Args:
        phone: Номер в формате +7(XXX)XXX-XX-XX или 7XXXXXXXXXX
        
    Returns:
        Кортеж (formatted_phone, digits_phone)
        
    Raises:
        ValueError: Если номер не соответствует формату
    """
    digits = _extract_digits(phone)
    
    if not _is_valid_phone_digits(digits):
        raise ValueError(
            f"Неверный формат номера телефона. Ожидается формат: {PHONE_FORMAT}"
        )
    
    return (_digits_to_formatted(digits), digits)
