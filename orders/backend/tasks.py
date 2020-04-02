# TODO: Отказ от django signals с дальнейшей интеграцией
#  в проект Celery для асинхронных задач

from celery.task import task
from celery.utils.log import get_task_logger

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import User

from django.http import JsonResponse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from requests import get
from yaml import load as load_yaml, Loader

from .models import Shop, Category, Product, ProductInfo, Parameter, \
    ProductParameter, ConfirmEmailToken


logger = get_task_logger(__name__)

@task(name="send_new_user_email")
def send_new_user_email_task(user_id, **kwargs):
    """
    Отправляем письмо с подтверждением почтового ящика
    """
    token, _ = ConfirmEmailToken.objects.get_or_create(user_id=user_id)
    msg = EmailMultiAlternatives(
        # Заголовок письма
        f'Токен для подтверждения почты {token.user.email}',
        # Сообщение
        token.key,
        # От:
        settings.EMAIL_HOST_USER,
        # Кому:
        [token.user.email]
    )
    msg.send()

@task(name="send_password_reset_token_email")
def send_password_reset_token_email_task(sender, instance,
                                         reset_password_token, **kwargs):
    """
    Когда токен для сброса пароля создан, нужно послать письмо пользователю
    :param sender: Зависит от класса-источника сигнала
    :param instance: Зависит от инстанса-источника сигнала
    :param reset_password_token: объект модели Token
    """
    msg = EmailMultiAlternatives(
        # title
        f'Токен сброса пароля для пользователя {reset_password_token.user}'
        # message
        f'Токен: "{reset_password_token.key}"',
        # from
        settings.EMAIL_HOST_USER,
        # to
        [reset_password_token.user.email]
    )
    msg.send()

@task(name="send_new_order_email")
def send_new_order_email_task(user_id, **kwargs):
    """
    Отправляем письмо об изменении статуса заказа
    """
    user =User.objects.get(id=user_id)
    msg = EmailMultiAlternatives(
        # Заголовок
        f'Обновление статуса заказа',
        # Сообщение
        f'Заказ сформирован',
        # От:
        settings.EMAIL_HOST_USER,
        # Кому:
        [user.email]
    )
    msg.send()

@task(name="do_import")
def do_import_task(partner, url):
    # url = request.data.get('url')
    if url:
        validate_url = URLValidator()
        try:
            validate_url(url)  # print("Url is valid")
        except ValidationError as e:
            return {'Status': False, 'Error': str(e)}
        else:
            stream = get(url).content

        data = load_yaml(stream, Loader=Loader)
        try:
            shop, _ = Shop.objects.get_or_create(name=data['shop'],
                                             user_id=partner)
        except IntegrityError as e:
            return {'Status': False, 'Error': str(e)}

        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(
                id=category['id'], name=category['name'])
            category_object.shops.add(shop.id)
            category_object.save()

        ProductInfo.objects.filter(shop_id=shop.id).delete()
        for item in data['goods']:
            product, _ = Product.objects.get_or_create(
                name=item['name'], category_id=item['category']
            )
            product_info = ProductInfo.objects.create(
                product_id=product.id, external_id=item['id'],
                model=item['model'], price=item['price'],
                price_rrc=item['price_rrc'], quantity=item['quantity'],
                shop_id=shop.id
            )
            for name, value in item['parameters'].items():
                parameter_object, _ = Parameter.objects.get_or_create(
                    name=name
                )
                ProductParameter.objects.create(
                    product_info_id=product_info.id,
                    parameter_id=parameter_object.id, value=value
                )
        return {'Status': True}
    return {'Status': False, 'Errors': 'url is false'}

@task(name='mul')
def mul(x, y):
    """
    Simple task for testing
    """
    return x * y