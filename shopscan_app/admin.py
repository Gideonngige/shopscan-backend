from django.contrib import admin
from .models import Plan, Shop, ShopSubscription, ShopKeeper, Product, Payment, Notification
# Register your models here.

admin.site.register(Plan)
admin.site.register(Shop)
admin.site.register(ShopSubscription)
admin.site.register(ShopKeeper)
admin.site.register(Product)
admin.site.register(Payment)
admin.site.register(Notification)
