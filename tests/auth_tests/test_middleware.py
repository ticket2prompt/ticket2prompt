"""Tests for auth middleware."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from auth.middleware import get_current_user, require_org_admin, require_project_access
from auth.models import CurrentUser


class TestRequireOrgAdmin:
    def test_admin_passes(self):
        user = CurrentUser(
            user_id="u1", email="admin@test.com", display_name="Admin",
            org_id="org1", role="org_admin"
        )
        result = require_org_admin(user)
        assert result == user

    def test_member_rejected(self):
        user = CurrentUser(
            user_id="u1", email="member@test.com", display_name="Member",
            org_id="org1", role="member"
        )
        with pytest.raises(HTTPException) as exc_info:
            require_org_admin(user)
        assert exc_info.value.status_code == 403
