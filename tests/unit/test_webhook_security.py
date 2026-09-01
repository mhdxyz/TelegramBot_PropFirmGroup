from __future__ import annotations

from app.webhook.security import is_valid_secret_token


def test_accepts_matching_token():
    assert is_valid_secret_token("correct-secret", "correct-secret") is True


def test_rejects_missing_token():
    assert is_valid_secret_token(None, "correct-secret") is False


def test_rejects_wrong_token():
    assert is_valid_secret_token("wrong-secret", "correct-secret") is False


def test_rejects_empty_token_against_real_secret():
    assert is_valid_secret_token("", "correct-secret") is False
