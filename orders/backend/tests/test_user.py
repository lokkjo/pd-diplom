import uuid
import json
import time
import pytest
from django.urls import reverse
from pathlib import Path

from ..models import User

CURRENT_PATH = Path.cwd()

# APIClient for testing

@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()

# data fixtures

@pytest.fixture
def test_password():
    return 'strong_password'

@pytest.fixture
def test_contacts():
    test_contacts_dict = {
        'city': 'Москва', 'street': 'Школьная ул.', 'phone': '495 494 4932'
    }
    return test_contacts_dict

@pytest.fixture
def test_basket():
    test_basket_dict = {
        "items": "[{\"quantity\": 1, \"product_info\": 6},{\"quantity\": 1, \"product_info\": 3}]"
    }
    return test_basket_dict

@pytest.fixture
def test_order():
    test_order_dict = {
        'id': '1', 'contact': '1'
    }
    return test_order_dict

@pytest.fixture
def test_import():
    test_import_dict = {
        'url': 'https://raw.githubusercontent.com/lokkjo/pd-diplom/master/data/shop3.yaml'
    }
    return test_import_dict

# user fixtures

@pytest.fixture()
def partner_fixture(django_user_model, test_password):
    """
    from djangostars.com/blog/django-pytest-testing/
    """
    def make_user(**kwargs):
        kwargs['password'] = test_password
        if 'email' not in kwargs:
            kwargs['email'] = str(uuid.uuid4())[:6] + '@mailserver.org'
        if 'type' not in kwargs:
            kwargs['type'] = 'shop'
        return django_user_model.objects.create_user(**kwargs)
    return make_user

@pytest.fixture
def api_client_with_credentials(partner_fixture, api_client):
    user = User.objects.get(pk=3)
    user.set_password(test_password)
    # user = partner_fixture()
    api_client.force_authenticate(user=user)
    yield api_client
    api_client.force_authenticate(user=None)

# tests



@pytest.mark.django_db
def test_shop_request(api_client):
    url = reverse('backend:shops')
    response = api_client.get(url)
    assert response.status_code == 200\

@pytest.mark.django_db
def test_category_request(api_client):
    url = reverse('backend:categories')
    response = api_client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_product_info_request(api_client):
    url = reverse('backend:products')
    response = api_client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_post_get_basket_requests(api_client_with_credentials, test_basket):
    url = reverse('backend:basket')
    post_rep = api_client_with_credentials.post(url, test_basket)
    assert post_rep.status_code == 200
    assert post_rep.json()['Status'] == True
    time.sleep(1)
    get_rep = api_client_with_credentials.get(url)
    print('get: ', get_rep.json())
    assert get_rep.status_code == 200

# @pytest.mark.django_db
def test_post_get_contacts_requests(api_client_with_credentials, test_contacts):
    url = reverse('backend:user-contact')
    post_rep = api_client_with_credentials.post(url, test_contacts)
    assert post_rep.status_code == 200
    assert post_rep.json()['Status'] == True
    get_rep = api_client_with_credentials.get(url)
    print(get_rep.json())
    assert get_rep.status_code == 200

# @pytest.mark.django_db
def test_order_requests(api_client_with_credentials,
                        test_basket, test_contacts, test_order):
    basket_url = reverse('backend:basket')
    basket_post = api_client_with_credentials.post(basket_url, test_basket)
    assert basket_post.status_code == 200
    assert basket_post.json()['Status'] == True

    contacts_url = reverse('backend:user-contact')
    contacts_post = api_client_with_credentials.post(contacts_url, test_contacts)
    assert contacts_post.status_code == 200
    assert contacts_post.json()['Status'] == True

    order_url = reverse('backend:order')
    order_post = api_client_with_credentials.post(order_url, test_order)
    assert order_post.status_code == 200
    assert order_post.json()['Status'] == True

    order_get = api_client_with_credentials.get(order_url)
    assert order_get.status_code == 200
    assert order_get.json()[0]['id'] == 1
    assert len(order_get.json()[0]['ordered_items']) > 0


# celery tests
from celery.contrib.pytest import  celery_session_app, celery_session_worker
from ..tasks import mul, do_import_task


@pytest.mark.usefixtures('celery_session_app')
@pytest.mark.usefixtures('celery_session_worker')
def celery_mul_test():
    assert mul.delay(4,4).get(timeout=10) == 16

@pytest.mark.django_db
@pytest.mark.usefixtures('celery_session_app')
@pytest.mark.usefixtures('celery_session_worker')
def test_partner_update_request(api_client_with_credentials, test_import):
    url = reverse('backend:partner-update')
    response = api_client_with_credentials.post(url, test_import)
    print()
    assert response.status_code == 200
    assert response.json()['Status'] == True