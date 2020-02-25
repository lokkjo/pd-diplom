from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from .models import User, Shop, Category, Product, ProductInfo,\
    ProductParameter, Order, OrderItem, Contact, ConfirmEmailToken

class ContactInline(admin.TabularInline):
    model = Contact
    max_num = 1


class ProductInline(admin.TabularInline):
    model = Product
    extra = 1


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 2


class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 1


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions'),
                            'classes': ('collapse',)}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name',
                                      'company', 'position'),
                           'classes': ('collapse',)}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined'),
                             'classes': ('collapse',)})
    )
    list_display = ('email', 'first_name', 'last_name', 'type',
                    'is_staff', 'is_active')
    ordering = ('email',)
    inlines = [
        ContactInline,
    ]

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    model=Shop
    fieldsets = (
        (None, {'fields': ('name', 'state')}),
        (_('Additional Info'), {'fields': ('url', 'user'),
                             'classes': ('collapse',)}),
    )
    list_display = ('name', 'state', 'url')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    model = Category
    inlines = [ProductInline]


@admin.register(Order)
class Order(admin.ModelAdmin):
    model = Order
    fields = ('user', 'state', 'contact')
    list_display = ('user', 'dt', 'state')
    ordering = ('dt',)
    inlines = [
        OrderItemInline,
    ]



@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    model = ProductInfo
    fieldsets = (
        (None, {'fields': ('product', 'model', 'external_id', 'quantity')}),
        (_('Цены'), {'fields': ('price', 'price_rrc')}),
    )
    list_display = ('product', 'external_id', 'price', 'price_rrc', 'quantity')
    ordering = ('external_id',)
    inlines = [ProductParameterInline]