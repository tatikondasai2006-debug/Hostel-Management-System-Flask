"""Unit tests for form validators and URL safety helpers."""

import pytest
from wtforms.validators import ValidationError

from app.auth.forms import validate_password_strength


class _Field:
    def __init__(self, data):
        self.data = data


def test_password_too_short_rejected():
    with pytest.raises(ValidationError):
        validate_password_strength(None, _Field("ab1"))


def test_password_without_digit_rejected():
    with pytest.raises(ValidationError):
        validate_password_strength(None, _Field("abcdefgh"))


def test_password_without_letter_rejected():
    with pytest.raises(ValidationError):
        validate_password_strength(None, _Field("12345678"))


def test_password_with_letter_and_digit_accepted():
    validate_password_strength(None, _Field("passw0rd"))
