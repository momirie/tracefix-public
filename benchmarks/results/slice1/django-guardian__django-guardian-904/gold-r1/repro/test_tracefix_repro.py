from django.contrib.auth import get_user_model
from django.test import TestCase

from guardian.core import ObjectPermissionChecker


class PrefetchEmptyListTest(TestCase):
    def test_prefetch_perms_empty_list(self):
        User = get_user_model()
        user = User.objects.create(username="emptyprefetchuser")
        checker = ObjectPermissionChecker(user)
        result = checker.prefetch_perms([])
        assert result is True
