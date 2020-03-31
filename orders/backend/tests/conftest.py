import pytest
from django.core.management import call_command
from pathlib import Path

CURRENT_PATH = Path.cwd()

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    fixture_file = str(CURRENT_PATH) + r'/backend/tests/fixtures.json'
    print(fixture_file)
    with django_db_blocker.unblock():
        call_command('loaddata', fixture_file)