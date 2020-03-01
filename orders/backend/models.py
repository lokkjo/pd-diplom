from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator

from django.db import models

from django.utils.translation import gettext_lazy as _
from django_rest_passwordreset.tokens import get_token_generator

# Constant data to use in models

STATE_CHOICES = (
    ('basket', 'Статус корзины'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),
)


# User and UserManager models

class UserManager(BaseUserManager):
    """
    Define a model manager for User model with no username field
    from www.fomfus.com/articles/how-to-use-email-as-username-for-django-authentication-removing-the-username
    """
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        База для создания и сохранения Пользователя (User)
        принимает почту и пароль
        """
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """
        Создаёт и сохраняет простого пользователя
        принимает почту и пароль
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self.create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """
        Создаёт и сохраняет пользователя-администратора (superuser)
        принимает почту и пароль
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        # extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        # if extra_fields.get('is_active') is not True:
        #     raise ValueError('Superuser must have is_active=True')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Модель пользователя (User)
    """
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    email = models.EmailField(_('почта'), unique=True)
    company = models.CharField(max_length=32, blank=True,
                               verbose_name='компания')
    position = models.CharField(max_length=32, blank=True,
                                verbose_name='должность')
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(_('username'), max_length=150,
                                help_text=_('Required 150 characters or less. '
                                            'Letters, digits and @/./+/-/_ only.'),
                                validators=[username_validator],
                                error_messages={'unique': _(
                                    'A user with that username already exists.'),
                                }, )
    is_active = models.BooleanField(_('active'), default=False, help_text=(
        'Designates whether this user should be treated as active.'
        'Unselect this instead of deleting account.'), )
    type = models.CharField(choices=USER_TYPE_CHOICES, max_length=5,
                            default='buyer', verbose_name='тип пользователя')

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'список пользователей'
        ordering = ('email',)


# Shop backend models

class Shop(models.Model):
    name = models.CharField(max_length=32, verbose_name='название')
    url = models.URLField(null=True, blank=True, verbose_name='ссылка')
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True,
                                blank=True, verbose_name='пользователь')
    state = models.BooleanField(default=True,
                                verbose_name='статус получения заказов')

    class Meta:
        verbose_name = 'магазин'
        verbose_name_plural = 'список магазинов'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=32, verbose_name='название')
    shops = models.ManyToManyField(Shop, blank=True, verbose_name='магазины',
                                   related_name='categories')

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'список категорий'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=64, verbose_name='название')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, blank=True,
                                 verbose_name='категория',
                                 related_name='products')

    class Meta:
        verbose_name = 'продукт'
        verbose_name_plural = 'список продуктов'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    model = models.CharField(max_length=64, blank=True, verbose_name='модель')
    external_id = models.PositiveIntegerField(verbose_name='внешний ID')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=True,
                                verbose_name='продукт',
                                related_name='product_infos')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, blank=True,
                             verbose_name='магазин',
                             related_name='product_infos')
    quantity = models.PositiveIntegerField(verbose_name='количество')
    price = models.PositiveIntegerField(verbose_name='цена')
    price_rrc = models.PositiveIntegerField(verbose_name='рекомендуемая '
                                                         'розничная цена')

    class Meta:
        verbose_name = 'информация о продукте'
        verbose_name_plural = 'свод информации о продуктах'
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop', 'external_id'],
                                    name='unique_product_info'), ]

    def __str__(self):
        return f'{self.product} {_("from")} {self.shop}'


class Parameter(models.Model):
    name = models.CharField(max_length=32, verbose_name='название')

    class Meta:
        verbose_name = 'имя параметра'
        verbose_name_plural = 'список имён параметров'
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE,
                                     blank=True,
                                     verbose_name='информация о продукте',
                                     related_name='product_parameters')
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE,
                                  blank=True, verbose_name='параметр',
                                  related_name='product_parameters')
    value = models.CharField(max_length=128, verbose_name='значение')

    class Meta:
        verbose_name = 'параметр'
        verbose_name_plural = 'список параметров'
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'],
                                    name='unique_product_parameter'), ]


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True,
                             verbose_name='пользователь', related_name='orders')
    dt = models.DateTimeField(auto_now_add=True, verbose_name='дата создания')
    state = models.CharField(max_length=16, choices=STATE_CHOICES,
                             verbose_name='статус')
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE,
                                blank=True, null=True,
                                verbose_name='контактные данные')

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'список заказов'
        ordering = ('-dt',)

    def __str__(self):
        return str(self.dt)

    # @property
    # def sum(self):
    #     """
    #     Общее количество всех позиций в заказе?
    #     """
    #     return self.ordered_items.aggregate(total=Sum('quantity'))['total'])



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, blank=True,
                              verbose_name='заказ',
                              related_name='ordered_items')
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE,
                                     blank=True,
                                     verbose_name='информация о продукте',
                                     related_name='ordered_items')
                                        # см. Order.sum()
    quantity = models.PositiveIntegerField(verbose_name='количество')

    class Meta:
        verbose_name = 'заказанная позиция'
        verbose_name_plural = 'список заказанных позиций'
        constraints = [
            models.UniqueConstraint(fields=['order_id', 'product_info'],
                                    name='unique_order_item'), ]


class Contact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True,
                             verbose_name='пользователь',
                             related_name='contacts')
    city = models.CharField(max_length=32, verbose_name='город')
    street = models.CharField(max_length=64, verbose_name='улица')
    house = models.CharField(max_length=16, blank=True, verbose_name='дом')
    building = models.CharField(max_length=16, blank=True,
                                verbose_name='строение')
    apartment = models.CharField(max_length=16, blank=True,
                                 verbose_name='квартира')
    phone = models.CharField(max_length=32, verbose_name='телефон')

    class Meta:
        verbose_name = 'контактные данные пользователя'
        verbose_name_plural = 'контактные данные пользователя'

    def __str__(self):
        return f'{self.city}, {self.street} {self.house} тел. {self.phone}'


class ConfirmEmailToken(models.Model):
    class Meta:
        verbose_name = 'Токен подтверждения почты'
        verbose_name_plural = 'Токены подтверждения почты'

    @staticmethod
    def generate_key():
        """
        использует os.urandom и binascii.hexlify
        генерирует псевдо-рандомную последовательность символов
        """
        return get_token_generator().generate_token()

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             verbose_name=_('пользователь, связанный '
                                            'с данным токеном смены пароля'),
                             related_name='confirm_email_tokens')
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name=_('Когда этот токен '
                                                     'был создан'))

    # Ключевое поле, но не основной ключ модели
    key = models.CharField(_('Key'), max_length=64, db_index=True, unique=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(ConfirmEmailToken, self).save(*args, **kwargs)

    def __str__(self):
        return f'Токен смены пароля для пользователя {self.user}'
