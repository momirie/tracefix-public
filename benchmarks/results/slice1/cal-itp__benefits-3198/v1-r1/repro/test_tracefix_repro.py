import pytest
from django.contrib import admin
from django.contrib.admin.utils import label_for_field
from django.test import RequestFactory

from benefits.core import models
from benefits.core.admin.transit import TransitAgencyAdmin


class _User:
    is_superuser = False


def test_readonly_fields_exist_on_model_for_non_superuser():
    model_admin = TransitAgencyAdmin(models.TransitAgency, admin.site)
    request = RequestFactory().get("/")
    request.user = _User()

    readonly = model_admin.get_readonly_fields(request)

    assert readonly
    for name in readonly:
        # raises AttributeError when the field cannot be looked up
        label_for_field(name, models.TransitAgency, model_admin)
