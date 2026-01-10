from rest_framework import serializers
from .models import ShopKeeper, Notification, Plan, ShopSubscription

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'created_at', 'is_read']


# plan serializer
class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"

# shop subscription serializer
class ShopSubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer()

    class Meta:
        model = ShopSubscription
        fields = "__all__"
