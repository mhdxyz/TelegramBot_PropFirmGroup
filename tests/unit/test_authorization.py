from __future__ import annotations

import pytest

from app.core.exceptions import UnauthorizedError
from app.security.authorization import Authorizer


def test_empty_allow_list_permits_everyone():
    authorizer = Authorizer(allowed_user_ids=frozenset(), admin_user_ids=frozenset())

    assert authorizer.is_allowed(12345) is True
    authorizer.require_allowed(12345)  # should not raise


def test_non_empty_allow_list_restricts_access():
    authorizer = Authorizer(allowed_user_ids=frozenset({1, 2}), admin_user_ids=frozenset())

    assert authorizer.is_allowed(1) is True
    assert authorizer.is_allowed(999) is False
    with pytest.raises(UnauthorizedError):
        authorizer.require_allowed(999)


def test_admin_check_is_independent_of_allow_list():
    authorizer = Authorizer(allowed_user_ids=frozenset(), admin_user_ids=frozenset({7}))

    assert authorizer.is_admin(7) is True
    assert authorizer.is_admin(8) is False
    with pytest.raises(UnauthorizedError):
        authorizer.require_admin(8)
