from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from .models import ConfirmEmailToken, User

new_user_registered = Signal(providing_args=['user_id'],)

new_order = Signal(providing_args=['user_id'],)

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance,
                                 reset_password_token, **kwargs):
    """
    Когда токен для сброса пароля создан, нужно послать письмо пользователю
    :param sender: Зависит от класса-источника сигнала
    :param instance: Зависит от инстанса-источника сигнала
    :param reset_password_token: объект модели Token
    """
    msg = EmailMultiAlternatives(
        # Заголовок письма
        f'Токен для сброса пароля пользователя {reset_password_token.user}',
        # Сообщение
        reset_password_token.key,
        # От:
        settings.EMAIL_HOST_USER,
        # Кому:
        [reset_password_token.user.email]
    )
    msg.send()


@receiver(new_user_registered)
def new_user_registered_signal(user_id, **kwargs):
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


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
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