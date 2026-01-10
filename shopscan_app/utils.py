# utils.py
from django.utils import timezone
from .models import ShopSubscription
import os

def get_active_subscription(shop):
    return ShopSubscription.objects.filter(
        shop=shop,
        is_active=True,
        end_date__gt=timezone.now()
    ).first()


import requests
from requests.auth import HTTPBasicAuth

DARAJA_CONSUMER_KEY = os.environ.get("DARAJA_CONSUMER_KEY")
DARAJA_CONSUMER_SECRET = os.environ.get("DARAJA_CONSUMER_SECRET")
OAUTH_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

def get_access_token():
    response = requests.get(OAUTH_URL, auth=HTTPBasicAuth(DARAJA_CONSUMER_KEY, DARAJA_CONSUMER_SECRET))
    if response.status_code == 200:
        access_token = response.json()['access_token']
        print("TOKEN RESPONSE:", response.text)
        return access_token
    else:
        return None


# phone number normalize
def normalize_phone(phone):
    phone = phone.strip().replace(" ", "").replace("+", "")

    if phone.startswith("2547"):
        return "0" + phone[3:]   # 254712345678 -> 0712345678

    if phone.startswith("7"):
        return "0" + phone      # 712345678 -> 0712345678

    if phone.startswith("07"):
        return phone           # already correct

    raise ValueError("Invalid phone number format")