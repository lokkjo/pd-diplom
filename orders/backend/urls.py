from django.urls import path

from .views import PartnerUpdate

app_name = 'backend'

urlpatterns = [
    path('partner/update', PartnerUpdate.as_view(), name='partner-update')
]