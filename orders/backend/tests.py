from django.test import TestCase

from django.utils.http import urlencode
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Shop
from ..backend import views

class ShopViewTests(APITestCase):
    def get_shops(self, name):
        url = reverse(views.ShopView.name)
        data = {'name': name}
        response = self.client.get(url, data, format='json')
        return response
