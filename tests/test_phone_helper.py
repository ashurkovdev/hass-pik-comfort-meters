"""Тесты для phone_helper модуля."""

import pytest
from custom_components.pik_comfort_meters.phone_helper import (
    format_phone,
    parse_formatted_phone,
    validate_phone,
    PHONE_FORMAT,
    _extract_digits,
    _is_valid_phone_digits,
    _digits_to_formatted,
)


# Тесты вспомогательных функций
class TestHelperFunctions:
    def test_extract_digits_basic(self):
        assert _extract_digits("79001234567") == "79001234567"
    
    def test_extract_digits_with_spaces(self):
        assert _extract_digits("7 900 123 45 67") == "79001234567"
    
    def test_extract_digits_formatted(self):
        assert _extract_digits("+7(900)123-45-67") == "79001234567"
    
    def test_extract_digits_with_plus(self):
        assert _extract_digits("+79001234567") == "79001234567"
    
    def test_is_valid_phone_digits_valid(self):
        assert _is_valid_phone_digits("70000000000") is True
        assert _is_valid_phone_digits("79001234567") is True
    
    def test_is_valid_phone_digits_invalid(self):
        assert _is_valid_phone_digits("89001234567") is False
        assert _is_valid_phone_digits("7900123456") is False
        assert _is_valid_phone_digits("790012345678") is False
        assert _is_valid_phone_digits("invalid") is False
    
    def test_digits_to_formatted(self):
        result = _digits_to_formatted("79001234567")
        assert result == "+7(900)123-45-67"


# Тесты format_phone
class TestFormatPhone:
    def test_format_already_formatted(self):
        result = format_phone("+7(900)123-45-67")
        assert result == "+7(900)123-45-67"
    
    def test_format_digits(self):
        result = format_phone("79001234567")
        assert result == "+7(900)123-45-67"
    
    def test_format_with_spaces(self):
        result = format_phone("7 900 123 45 67")
        assert result == "+7(900)123-45-67"
    
    def test_format_with_plus(self):
        result = format_phone("+79001234567")
        assert result == "+7(900)123-45-67"
    
    def test_format_default_zeros(self):
        result = format_phone("70000000000")
        assert result == "+7(000)000-00-00"
    
    def test_format_invalid_length(self):
        with pytest.raises(ValueError, match="Неверный формат номера телефона"):
            format_phone("9001234567")
    
    def test_format_wrong_country(self):
        with pytest.raises(ValueError, match="Неверный формат номера телефона"):
            format_phone("89001234567")


# Тесты parse_formatted_phone
class TestParseFormattedPhone:
    def test_parse_formatted(self):
        result = parse_formatted_phone("+7(900)123-45-67")
        assert result == "79001234567"
    
    def test_parse_digits(self):
        result = parse_formatted_phone("79001234567")
        assert result == "79001234567"
    
    def test_parse_with_plus(self):
        result = parse_formatted_phone("+79001234567")
        assert result == "79001234567"
    
    def test_parse_invalid(self):
        with pytest.raises(ValueError, match="Неверный формат номера телефона"):
            parse_formatted_phone("89001234567")


# Тесты validate_phone
class TestValidatePhone:
    def test_validate_formatted(self):
        formatted, digits = validate_phone("+7(900)123-45-67")
        assert formatted == "+7(900)123-45-67"
        assert digits == "79001234567"
    
    def test_validate_digits(self):
        formatted, digits = validate_phone("79001234567")
        assert formatted == "+7(900)123-45-67"
        assert digits == "79001234567"
    
    def test_validate_default_zeros(self):
        formatted, digits = validate_phone("70000000000")
        assert formatted == "+7(000)000-00-00"
        assert digits == "70000000000"
    
    def test_validate_invalid(self):
        with pytest.raises(ValueError, match="Неверный формат номера телефона"):
            validate_phone("89001234567")
    
    def test_validate_invalid_length(self):
        with pytest.raises(ValueError, match="Неверный формат номера телефона"):
            validate_phone("9001234567")


# Тесты конвертации форматированного номера в цифровой для API
class TestAPINumberConversion:
    def test_roundtrip(self):
        """Проверка что можно сконвертировать в оба формата и обратно."""
        original_digits = "79001234567"
        
        # Получаем отформатированный номер
        formatted, _ = validate_phone(original_digits)
        assert formatted == "+7(900)123-45-67"
        
        # Из форматированного получаем цифровой
        result_digits = parse_formatted_phone(formatted)
        assert result_digits == original_digits