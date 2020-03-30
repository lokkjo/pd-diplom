from django.shortcuts import render
from django.http import JsonResponse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from django.db.models import Q, Sum, F

from celery import current_app

from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.renderers import TemplateHTMLRenderer

from requests import get
from ujson import loads as load_json
from yaml import load as load_yaml, Loader
from distutils.util import strtobool

from .models import Shop, Category, Product, ProductInfo, Parameter, \
    ProductParameter, Order, OrderItem, Contact, ConfirmEmailToken
from .serializers import UserSerializer, CategorySerializer, ShopSerializer, \
    ProductInfoSerializer, OrderItemSerializer, OrderSerializer, \
    ContactSerializer
from .signals import new_user_registered, new_order

from .tasks import send_new_user_email_task, send_new_order_email_task, \
    do_import_task

# Наиболее часто повторяющиеся статусы ошибок

NO_AUTH_STATUS = {'Status': False, 'Error': 'Необходимо авторизоваться'}
LACK_OF_ARGS_STATUS = {'Status': False,
                       'Errors': 'Не указаны все необходимые аргументы'}
SHOP_ONLY_STATUS = {'Status': False, 'Error': 'Только для магазинов'}
ORDER_ERROR_STATUS = {'Status': False, 'Error': 'Ошибка обработки заказа'}

# Views для работы с поставщиками

class PartnerUpdate(APIView):
    """
    Класс для обновления прайслиста от поставщика
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        if request.user.type != 'shop':
            return JsonResponse(SHOP_ONLY_STATUS, status=403)

        url = request.data.get('url')
        if url:
            task = do_import_task.delay(url)

            return JsonResponse({'Status': True})

        return JsonResponse(LACK_OF_ARGS_STATUS)


class PartnerState(APIView):
    """
    Работа со статусом поставщика
    """

    # получаем статус
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        if request.user.type != 'shop':
            return JsonResponse(SHOP_ONLY_STATUS, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # изменяем статус
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        if request.user.type != 'shop':
            return JsonResponse(SHOP_ONLY_STATUS, status=403)

        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(
                    state=strtobool(state))
                return JsonResponse({'Status': True})
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})


class PartnerOrders(APIView):
    """
    Работа с заказами от поставщика
    """
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        if request.user.type != 'shop':
            return JsonResponse(SHOP_ONLY_STATUS, status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id
        ).exclude(
            state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related(
            'contact'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity')
                          * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


# Views для работы с пользователями


class RegisterAccount(APIView):
    """
    Регистрация аккаунтов пользователей
    """

    def post(self, request, *args, **kwargs):
        if {'first_name', 'last_name', 'email',
            'password', 'company', 'position'}.issubset(request.data):
            errors = {}
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                for item in password_error:
                    error_array.append(item)
                # error_array = [item for item in password_error]
                return JsonResponse(
                    {'Status': False, 'Errors': {'password': error_array}})
            else:
                # request.data._mutable = True
                request.data.update({})
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()

                    task = send_new_user_email_task.delay(user.id)
                    # new_user_registered.send(sender=self.__class__,
                    #                          user_id=user.id)

                    return JsonResponse({'Status': True})
                else:
                    print('user errors: ', user_serializer.errors)
                    return JsonResponse(
                        {'Status': False, 'Errors': user_serializer.errors})
        return JsonResponse(LACK_OF_ARGS_STATUS)


class ConfirmAccount(APIView):
    """
    Подтверждение почтового адреса
    """
    def post(self, request, *args, **kwargs):
        if {'email', 'token'}.issubset(request.data):
            token = ConfirmEmailToken.objects.filter(
                user__email=request.data['email'],
                key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse(
                    {'Status': False, 'Errors': 'Неправильный токен или email'})

        return JsonResponse(LACK_OF_ARGS_STATUS)


class AccountDetails(APIView):
    """
    Класс для работы с данными пользователей
    """

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        if 'password' in request.data:
            errors = {}
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = [item for item in password_error]
                return JsonResponse({'Status': False,
                                     'Errors': {'password': error_array}})
            else:
                request.user.set_password(request.data['password'])

        user_serializer = UserSerializer(request.user, data=request.data,
                                         partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse(
                {'Status': False, 'Errors': user_serializer.errors})


class LoginAccount(APIView):
    def post(self, request, *args, **kwargs):

        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'],
                                password=request.data['password'])

            if user is not None:
                token, _ = Token.objects.get_or_create(user=user)
                return JsonResponse({'Status': True, 'Token': token.key})

            return JsonResponse(
                {'Status': False, 'Errors': 'Неудачная авторизация'})

        return JsonResponse(LACK_OF_ARGS_STATUS)


# Views для работы с магазинами и заказами

class CategoryView(ListAPIView):
    """
    Просмотр категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Просмотр списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
    Поиск товаров
    """

    def get(self, request, *args, **kwargs):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)
        if category_id:
            query = query & Q(product__category_id=category_id)

        queryset = ProductInfo.objects.filter(query).select_related('shop',
            'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data)


class BasketView(APIView):
    """
    Обработка корзины пользователя
    """
    # получаем корзину
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        basket = Order.objects.filter(
            user_id=request.user.id, state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity')
                          * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # вносим изменения в корзину
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        items_string = request.data.get('items')
        print('items string: ', items_string)
        if items_string:
            try:
                order_item_dict = load_json(items_string)

            except ValueError as e:
                return JsonResponse(
                    {'Status': False, 'Errors': f'Неверный формат запроса: {e}'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id,
                    state='basket')
                objects_created = 0

                for order_item in order_item_dict:

                    order_item.update({'order': basket.id})

                    print('order_item: ', order_item)

                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse(
                                {'Status': False, 'Errors': 'IntegrityError:'
                                                            + str(error)})
                        else:
                            objects_created += 1
                    else:
                        return JsonResponse(
                            {'Status': False, 'Errors': 'validation_stage:'
                                                        + serializer.errors})
                return JsonResponse(
                    {'Status': True, 'Создано объектов': objects_created})
        return JsonResponse(LACK_OF_ARGS_STATUS)

    # Удаляем позицию из корзины
    def delete(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        items_string = request.data.get('items')
        if items_string:
            items_list = items_string.split(',')
            basket, _ = Order.objects.get_or_create(user_id=request.user.id,
                                                    state='basket')
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True
            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse(
                    {'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse(LACK_OF_ARGS_STATUS)

    # Изменяем количество единиц товара в позиции
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        items_string = request.data.get('items')
        if items_string:
            try:
                items_dict = load_json(items_string)
                print(items_dict)
            except ValueError:
                return JsonResponse(
                    {'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state='basket'
                )
                objects_updated = 0
                for order_item in items_dict:
                    print('item:', order_item)
                    if (type(order_item['product_info']) == int
                            and type(order_item['quantity']) == int):
                        OrderItem.objects.filter(
                            order_id=basket.id,
                            product_info=order_item['product_info']
                        ).update(
                            quantity=order_item['quantity']
                        )
                        objects_updated += 1

                return JsonResponse(
                    {'Status': True, 'Обновлено объектов': objects_updated})
        return JsonResponse(LACK_OF_ARGS_STATUS)


# Views для работы с контактами


class ContactView(APIView):
    """
    Работа с контактами покупателей
    """
    # получаем контакты
    # renderer_classes = [TemplateHTMLRenderer]
    # template_name = 'backends/contact.html'
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        contact = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    # добавляем контакт
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        if {'city', 'street', 'phone'}.issubset(request.data):
            # request.data._mutable = True
            request.data.update({'user': request.user.id})
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse(
                    {'Status': False, 'Errors': serializer.errors})
        return JsonResponse(LACK_OF_ARGS_STATUS)

    # удаляем контакт
    def delete(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)
        contact_string = request.data.get('items')
        if contact_string:
            contact_list = contact_string.split(',')
            query = Q()
            contacts_deleted = False
            for contact_id in contact_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    contacts_deleted = True

            if contacts_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse(
                    {'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse(LACK_OF_ARGS_STATUS)

    # изменяем контакт
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'],
                    user_id=request.user.id).first()
                # print(contact)
                if contact:
                    serializer = ContactSerializer(contact, data=request.data,
                                                   partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True})
                    else:
                        return JsonResponse(
                            {'Status': False, 'Errors': serializer.errors})
        return JsonResponse(LACK_OF_ARGS_STATUS)


# Views для работы с заказами

class OrderView(APIView):
    """
    Работаем с заказами пользователя
    """

    # получаем заказ
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        order = Order.objects.filter(user_id=request.user.id).exclude(
            state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related(
            'contact'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity')
                          * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """
        На вход - json с данными:
        'id' - id заказа,
        'contact' - контактные данные пользователя
        """
        if not request.user.is_authenticated:
            return JsonResponse(NO_AUTH_STATUS, status=401)

        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit() or type(request.data['id']) == int:
                try:
                    is_updated = Order.objects.filter(user_id=request.user.id,
                        id=request.data['id']).update(
                        contact_id=request.data['contact'], state='new')
                except IntegrityError as error:
                    return JsonResponse(
                        {'Status': False, 'Errors': f'Неверные аргументы: {error}'})
                else:
                    if is_updated:

                        task = send_new_order_email_task.delay(request.user.id)
                        # new_order.send(sender=self.__class__,
                        #                user_id=request.user.id)

                        return JsonResponse({'Status': True})
                    return JsonResponse(ORDER_ERROR_STATUS)

