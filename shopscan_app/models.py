from django.db import models
from django.utils import timezone

# Plan model
class Plan(models.Model):
    PLAN_CHOICES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]
    PLAN_NAMES = [
        ("basic", "Basic"),
        ("premium", "Premium")
    ]

    plan_name = models.CharField(max_length=50, choices=PLAN_NAMES)
    plan_type = models.CharField(max_length=10, choices=PLAN_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.plan_name} ({self.plan_type})" 

# shop model
class Shop(models.Model):
    shop_name = models.CharField(max_length=100)
    date_joined = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.shop_name} {self.date_joined}"

# shop subscription model
class ShopSubscription(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan,on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.shop.shop_name} → {self.plan.plan_name}"


# shopkeeper model
class ShopKeeper(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="shopkeeper")
    shopkeeper_name = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    firebase_uid = models.CharField(max_length=256)
    phone_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    profile_image = models.URLField(blank=True, null=True)
    expo_token = models.CharField(max_length=100)
    date_joined = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.shop.shop_name} {shopkeeper_name} {date_joined}"

# product model
class Product(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="product")
    product_name = models.CharField(max_length=100)
    barcode_number = models.CharField(max_length=15)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    date_added = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.shop.shop_name} {self.product_name} {self.price} {self.quantity}"

# payment model
class Payment(models.Model):
    PAYMENT_METHODS = [
        ("mpesa", "Mpesa"),
        ("card", "Card"),
    ]
    STATUS = [
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("pending", "Pending"),
    ]
    shopkeeper = models.ForeignKey(ShopKeeper, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_status = models.CharField(max_length=10, choices=STATUS)
    paid_at = models.DateTimeField(default=timezone.now)


# notification model
class Notification(models.Model):
    shopkeeper = models.ForeignKey(ShopKeeper, on_delete=models.CASCADE, related_name="notifications")
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.shopkeeper.shopkeeper_name}"
