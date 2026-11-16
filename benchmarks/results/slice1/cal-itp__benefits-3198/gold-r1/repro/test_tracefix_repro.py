import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from benefits.core import models
from benefits.core.admin.transit import TransitAgencyAdmin


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


class _User:
    is_superuser = False
    is_staff = True


def test_staff_readonly_and_exclude_reference_existing_fields():
    admin_obj = TransitAgencyAdmin(models.TransitAgency, AdminSite())
    request = _request(_User())

    field_names = {f.name for f in models.TransitAgency._meta.get_fields()}

    readonly = admin_obj.get_readonly_fields(request)
    exclude = admin_obj.get_exclude(request) or []

    for name in list(readonly) + list(exclude):
        assert name in field_names or hasattr(admin_obj, name) or hasattr(models.TransitAgency, name), name
