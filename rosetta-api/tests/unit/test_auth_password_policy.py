"""New passwords: 8 characters to 72 bytes, and none of the common passwords bundled in
schemas/common_passwords.txt (compared case-insensitively), at registration and password change."""
import pytest
from pydantic import ValidationError

from schemas.auth import PasswordChange, UserCreate, check_new_password


@pytest.mark.parametrize("password", ["12345678", "Password1", "IloveYOU1", "qwertyuiop"])
def test_common_passwords_are_refused(password):
    with pytest.raises(ValueError, match="most common passwords"):
        check_new_password(password)
    with pytest.raises(ValidationError):
        UserCreate(email="a@example.org", password=password)
    with pytest.raises(ValidationError):
        PasswordChange(current_password="anything-1", new_password=password)


@pytest.mark.parametrize("password", ["correct horse battery", "testpass123", "\u00e9t\u00e9-2026-ok"])
def test_other_passwords_are_accepted(password):
    assert check_new_password(password) == password
