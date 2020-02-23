from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Shop
# Register your models here.

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'groups', 'user_permissions')}),
        ('Personal Info', {'fields': ('first_name', 'last_name',
                                      'company', 'position'),
                           'classes': ('collapse',)}),
        ('Important dates', {'fields': ('last_login', 'date_joined'),
                             'classes': ('collapse',)})
    )
    list_display = ('email', 'first_name', 'last_name', 'type',
                    'is_staff', 'is_active')
    ordering = ('email',)

    # name = models.CharField(max_length=32, verbose_name='название')
    # url = models.URLField(null=True, blank=True, verbose_name='ссылка')
    # user = models.OneToOneField(User, on_delete=models.CASCADE, null=True,
    #                             blank=True, verbose_name='пользователь')
    # state = models.BooleanField(default=True,
    #                             verbose_name='статус получения заказов')


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    model=Shop
    fieldsets = (
        (None, {'fields': ('name', 'state')}),
        ('Additional Info', {'fields': ('url', 'user'),
                             'classes': ('collapse',)}),
    )
    list_display = ('name', 'state', 'url')


