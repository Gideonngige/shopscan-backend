from django.shortcuts import render
from django.http import HttpResponse, JsonResponse

from rest_framework.decorators import api_view, parser_classes, permission_classes
from django.views.decorators.csrf import csrf_exempt

from .models import ShopKeeper, Shop, Notification, Product, ProductSale, Plan, ShopSubscription, Payment
from rest_framework.parsers import MultiPartParser, FormParser

from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta

from django.db.models import F, Sum, Count, DecimalField, ExpressionWrapper
from django.utils.timesince import timesince

from .utils import get_active_subscription, get_access_token, normalize_phone
import requests

import base64
import datetime


import pyrebase
import firebase_admin
from firebase_admin import credentials, auth
import os, json
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from .serializers import NotificationSerializer, PlanSerializer, ShopSubscriptionSerializer


firebaseConfig = {
  "apiKey": os.environ.get("FIREBASE_API_KEY"),
  "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
  "databaseURL": os.environ.get("FIREBASE_DATABASE_URL"),
  "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
  "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
  "messagingSenderId": os.environ.get("FIREBASE_MESSAGING_SENDER_ID"),
  "appId": os.environ.get("FIREBASE_APP_ID"),
  "measurementId": os.environ.get("FIREBASE_MEASUREMENT_ID")
};

firebase = pyrebase.initialize_app(firebaseConfig)
authe = firebase.auth() 
database = firebase.database()

# Initialize Firebase once (e.g., in settings.py or a startup file)
service_account_info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
# cred = credentials.Certificate("serviceAccountKey.json")
cred = credentials.Certificate(service_account_info)
# firebase_admin.initialize_app(cred)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# verify apis access
def verify_firebase_token(view_func):
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JsonResponse({"error": "Authorization header missing"}, status=401)

        try:
            token = auth_header.split(" ")[1]  # "Bearer <token>"
            decoded = auth.verify_id_token(token)
            request.firebase_uid = decoded["uid"]   # <===== IMPORTANT
        except Exception as e:
            return JsonResponse({"error": "Invalid token", "details": str(e)}, status=401)

        return view_func(request, *args, **kwargs)

    return wrapper

def index(request):
    return HttpResponse("ShopScan Index Page!")


# start of siginin
@api_view(['POST'])
def signin(request):
    email = request.data.get("email")
    password = request.data.get("password")

    try:
        # Try Firebase sign in
        login = authe.sign_in_with_email_and_password(email, password)
        id_token = login["idToken"]

        # Get account info
        info = authe.get_account_info(id_token)
        email_verified = info["users"][0]["emailVerified"]

        if not email_verified:
            # Resend verification email
            authe.send_email_verification(id_token)

            return JsonResponse({
                "message": "Email not verified. Verification link has been sent again."
            }, status=403)

        # Email verified → Continue login
        uid = info["users"][0]["localId"]
        db_user = ShopKeeper.objects.filter(firebase_uid=uid).first()
        # log user action
        # logger.info(f"User sign in: Email: {email}, Name: {db_user.full_name}")

        return JsonResponse({
            "message": "Login successful",
            "access_token": id_token,
            "shopkeeper": {
                "shopkeeper_id": db_user.id,
                "shopkeeper_name": db_user.shopkeeper_name,
                "shopkeeper_email": db_user.email,
                "shop_name": db_user.shop.shop_name,
                "shop_id": db_user.shop.id,
                "phone_number": db_user.phone_number,
                "phone_verified": db_user.phone_verified,
                "profile_image": db_user.profile_image,
                "date_joined": db_user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
            }
        })

    except Exception as e:
        return JsonResponse({"message": "Invalid login", "error": str(e)}, status=401)
# end


# start of signup
@csrf_exempt
@api_view(['POST'])
def signup(request):
    data = request.data
    shopkeeper_name = data.get("shopkeeper_name")
    phone_number = data.get("phone_number")
    email = data.get("email")
    password = data.get("password")

    shop_name = data.get("shop_name")

    if not all([shopkeeper_name, phone_number, email, password, shop_name]):
        return JsonResponse({"message": "Missing fields"}, status=400)

    # check if email already exists in firebase
    try:
        existing_user = authe.get_user_by_email(email)
        return JsonResponse({"message": "Email already exists"}, status=400)
    except:
        pass  # user does not exist, continue

    try:
        # Create user in Firebase
        user = authe.create_user_with_email_and_password(email, password)

        # Send verification email
        authe.send_email_verification(user['idToken'])

        # create shop
        shop = Shop.objects.create(
            shop_name=shop_name
        )

        # Save profile to Django database (NO PASSWORD)
        uid = user["localId"]
        ShopKeeper.objects.create(
            shop=shop,
            firebase_uid=uid,
            shopkeeper_name=shopkeeper_name,
            phone_number=phone_number,
            email=email
        )
        # log user action
        # logger.info(f"User sign up: Email: {email}, Name: {full_name}")

        # set default plan subscribed as basic
        plan = Plan.objects.get(plan_name="basic")
        ShopSubscription.objects.create(
            shop=shop,
            plan=plan,
            end_date=timezone.now() + timedelta(days=plan.duration_days)
        )

        # create welcome notification
        db_user = ShopKeeper.objects.get(firebase_uid=uid)
        Notification.objects.create(
            shopkeeper=db_user,
            message="Welcome to ShopScan! Your account has been created successfully.",
            is_read=False
        )

        return JsonResponse({"message": "Account created. Check your email to verify."}, status=201)

    except Exception as e:
        return JsonResponse({"message": "Signup failed", "error": str(e)}, status=400)
# end


# start of delete account api
@api_view(['DELETE'])
@verify_firebase_token
def delete_account(request):
    firebase_uid = request.firebase_uid

    # 1. Delete from Firebase Auth
    try:
        auth.delete_user(firebase_uid)
        print("Firebase user deleted")
    except Exception as e:
        print("Firebase delete error:", e)

    # 2. Delete from Django database
    shopkeeper = ShopKeeper.objects.filter(firebase_uid=firebase_uid).first()
    if shopkeeper:
        shopkeeper.delete()

    return JsonResponse({"message": "Account deleted successfully"}, status=200)
# end

# request password reset api
@api_view(['POST'])
def request_password_reset(request):
    email = request.data.get("email")

    try:
        authe.send_password_reset_email(email)
        return JsonResponse({"message": "Password reset email sent"})
    except Exception as e:
        return JsonResponse({"message": "Error sending reset email", "error": str(e)}, status=400)
# end

# start of get notifications api
@api_view(['GET'])
def get_notifications(request, shopkeeper_id):
    try:
        shopkeeper = ShopKeeper.objects.get(id=shopkeeper_id)
        notifications = Notification.objects.filter(shopkeeper=shopkeeper, is_read=False).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)

        return Response(serializer.data)
    except ShopKeeper.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

# end of notification api


# add product api
@api_view(['POST'])
def add_product(request):
    if request.method == 'POST':
        try:
            shop_id = request.data.get("shop_id")
            product_name = request.data.get("product_name")
            barcode_number = request.data.get("barcode_number")
            price = request.data.get("price")
            quantity = request.data.get("quantity")
            print("Received data:", shop_id, product_name, barcode_number, price, quantity)

            if not all([shop_id, product_name, barcode_number, price, quantity]):
                return JsonResponse({"message": "All fields are required"}, status=400)
            
            # check shop exists
            shop = Shop.objects.get(id=shop_id)
            if not shop:
                return JsonResponse({"message": "Shop not found"}, status=404)

            product = Product.objects.create(
                shop=shop,
                product_name=product_name,
                barcode_number=barcode_number,
                price=price,
                quantity=quantity,
            )
    
            return JsonResponse({"message": "Product added successfully", "product_id": product.id}, status=201)

        except Exception as e:
            print("Error:", str(e))
            return JsonResponse({"message": "An error occurred", "error": str(e)}, status=500)

# end of add product api

# api to get product for a shop
@api_view(['GET'])
def get_products(request, shop_id):
    try:
        products = Product.objects.filter(shop_id=shop_id)
        product_list = []
        for product in products:
            product_list.append({
                'id': product.id,
                'product_name': product.product_name,
                'price': str(product.price),
                'quantity': product.quantity,
                'barcode_number': product.barcode_number,
                'date_added': product.date_added.strftime("%Y-%m-%d %H:%M:%S"),
            })
        

        return JsonResponse({"products": product_list}, status=200)
    except Exception as e:
        print("Error:", str(e))
        logger.info(f"Error fetching products: {str(e)}")
        return JsonResponse({"message": "An error occurred", "error": str(e)}, status=500)

# end of get products api

# add stock to product api
@csrf_exempt
@api_view(['POST'])
def add_stock(request):
    try:
        shop_id = request.data.get("shop_id")
        product_id = request.data.get("product_id")
        price = request.data.get("price")
        additional_stock = int(request.data.get("additional_stock"))
        shop = Shop.objects.get(id=shop_id)
        product = Product.objects.get(id=product_id, shop=shop)

        if additional_stock < 0:
            return JsonResponse({"message": "Stock cannot be negative"}, status=400)

        product.quantity += additional_stock
        if price:
            product.price = price
        product.save()

        return JsonResponse({"message": "Stock updated successfully", "new_stock": product.quantity}, status=200)

    except Product.DoesNotExist:
        return JsonResponse({"message": "Product not found"}, status=404)
    except Exception as e:
        print("Error:", str(e))
        return JsonResponse({"message": "An error occurred", "error": str(e)}, status=500)

# end of add stock api

# start of update shopkeeper profile api
@csrf_exempt
@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
# @verify_firebase_token
def update_shopkeeper_profile(request):
    try:
        shopkeeper_id = request.data.get('shopkeeper_id')
        shopkeeper_name = request.data.get('shopkeeper_name')
        shop_name = request.data.get('shop_name')
        phone_number = request.data.get('phone_number')
        profile_image = request.FILES.get('profile_image')

        shopkeeper = ShopKeeper.objects.get(id=shopkeeper_id)

        if shopkeeper_name:
            shopkeeper.full_name = shopkeeper_name

        if phone_number:
            shopkeeper.phone_number = phone_number
        if shop_name:
            shopkeeper.shop.shop_name = shop_name
            shopkeeper.shop.save()
        if profile_image:
            shopkeeper.profile_image = profile_image 

        shopkeeper.save()
        return JsonResponse({
            "message": "Profile updated successfully",
            "profile_image": shopkeeper.profile_image.url if shopkeeper.profile_image else None,
            "name": shopkeeper.full_name,
            "phone": shopkeeper.phone_number,
            "email": shopkeeper.email,
        }, status=200)

    except ShopKeeper.DoesNotExist:
        return JsonResponse({"message": "ShopKeeper not found"}, status=404)

    except Exception as e:
        print(e)
        return JsonResponse({
            "message": "Invalid login",
            "error": str(e)
        }, status=400)


# end of update shopkeeper profile api


# create bulky sale api
@csrf_exempt
@api_view(['POST'])
def create_bulk_sale(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            shop_id = data.get("shop_id")
            shopkeeper_id = data.get("shopkeeper_id")
            products = data.get("products", [])  # List of items

            if not shop_id or not shopkeeper_id or not products:
                return JsonResponse({"message": "Shop ID, ShopKeeper ID and product list are required"}, status=400)

            # shop check
            shop = Shop.objects.filter(id=shop_id).first()
            if not shop:
                return JsonResponse({"message": "Shop not found"}, status=404)

            # shopkeeper check
            shopkeeper = ShopKeeper.objects.filter(id=shopkeeper_id, shop=shop).first()
            if not shopkeeper:
                return JsonResponse({"message": "ShopKeeper not found for this shop"}, status=404)

            sale_ids = []
            for item in products:
                barcode_number = item.get("barcode_number")
                # quantity = item.get("quantity")
                # price = item.get("price")

                # Check required fields
                if not all([barcode_number]):
                    return JsonResponse({"message": "Missing product details in one of the items"}, status=400)

                # product check
                product = Product.objects.filter(shop=shop, barcode_number=barcode_number).first()
                if not product:
                    return JsonResponse({"message": f"Product with barcode {barcode_number} not found"}, status=404)

                if product.quantity < 1:
                    return JsonResponse({"message": f"Not enough stock for {product.product_name}"}, status=400)

                # Create sale
                sale = ProductSale.objects.create(
                    product=product,
                    shop=shop,
                    shopkeeper=shopkeeper,
                    quantity=1,
                    price=product.price,
                )
                product.quantity -= 1
                product.save()
                sale_ids.append(sale.id)

            return JsonResponse({"message": "All sales created successfully", "sale_ids": sale_ids}, status=200)

        except Exception as e:
            print("Error:", str(e))
            return JsonResponse({"message": "An error occurred", "error": str(e)}, status=500)

# endof create sale api

# delete product api
@api_view(['DELETE'])
def delete_product(request, shopkeeper_id, product_id):
    try:
        # check shopkeeper exists
        shopkeeper = ShopKeeper.objects.get(id=shopkeeper_id)
        if not shopkeeper:
            return JsonResponse({"message": "ShopKeeper not found"}, status=404)
        
        product = Product.objects.get(id=product_id, shop=shopkeeper.shop)
        if not product:
            return JsonResponse({"message": "Product not found"}, status=404)

        product.delete()
        return JsonResponse({"message": "Product deleted successfully"}, status=200)

    except Product.DoesNotExist:
        return JsonResponse({"message": "Product not found"}, status=404)

    except Exception as e:
        return JsonResponse({"message": "An error occurred", "error": str(e)}, status=500)

# end of delete product api

# api for shopkeeper dashboard
@api_view(["GET"])
def shopkeeper_dashboard(request, shopkeeper_id):
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    amount_expr = ExpressionWrapper(
        F("price") * F("quantity"),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    # Today's total
    today_sales = ProductSale.objects.filter(
        shopkeeper_id=shopkeeper_id,
        sold_at__date=today
    ).annotate(
        total=amount_expr
    ).aggregate(sum=Sum("total"))["sum"] or 0

    # Yesterday's total
    yesterday_sales = ProductSale.objects.filter(
        shopkeeper_id=shopkeeper_id,
        sold_at__date=yesterday
    ).annotate(
        total=amount_expr
    ).aggregate(sum=Sum("total"))["sum"] or 0

    # Performance calculation
    if yesterday_sales > 0:
        percentage_change = ((today_sales - yesterday_sales) / yesterday_sales) * 100
    else:
        percentage_change = 100 if today_sales > 0 else 0

    return Response({
        "today_total": float(today_sales),
        "yesterday_total": float(yesterday_sales),
        "percentage_change": round(float(percentage_change), 2),
        "is_up": today_sales >= yesterday_sales
    })

# end of shopkeeper dashboard api

# api for recent sales
@api_view(["GET"])
def recent_sales(request, shop_id):
    sales = ProductSale.objects.filter(
        shop_id=shop_id
    ).select_related("product").order_by("-sold_at")[:10]

    data = []

    for sale in sales:
        data.append({
            "id": sale.id,
            "product_name": sale.product.product_name,
            "quantity": sale.quantity,
            "amount": float(sale.price * sale.quantity),
            "time": timesince(sale.sold_at) + " ago"
        })

    return Response({"sales": data})
# end of recent sales api


# dashboard summary api
@api_view(["GET"])
def dashboard_summary(request, shop_id):
    # Total products
    total_products = Product.objects.filter(shop_id=shop_id).count()

    # Total sales amount
    total_sales = ProductSale.objects.filter(shop_id=shop_id).aggregate(
        total=Sum("price")
    )["total"] or 0

    return JsonResponse({
        "total_products": total_products,
        "total_sales": float(total_sales)
    })

# end of dashboard summary api


# api for weekly sales data
@api_view(["GET"])
def weekly_sales(request, shop_id):
    today = timezone.now().date()
    start_date = today - timedelta(days=6)

    sales = (
        ProductSale.objects
        .filter(shop_id=shop_id, sold_at__date__gte=start_date)
        .extra(select={'day': "date(sold_at)"})
        .values("day")
        .annotate(total=Sum("price"))
        .order_by("day")
    )

    # Prepare full week with zeros
    result = {}
    for i in range(7):
        day = start_date + timedelta(days=i)
        result[str(day)] = 0

    for s in sales:
        result[str(s["day"])] = float(s["total"])

    return JsonResponse({
        "labels": list(result.keys()),
        "data": list(result.values())
    })

# end of weekly sales api

# api for stock status
@api_view(["GET"])
def stock_status(request, shop_id):
    products = Product.objects.filter(shop_id=shop_id)

    data = []
    for p in products:
        data.append({
            "id": p.id,
            "name": p.product_name,
            "quantity": float(p.quantity),
            "status": "in" if p.quantity > 0 else "out"
        })

    return JsonResponse({
        "products": data
    })
# end of stock status api

# api to get plans
@api_view(["GET"])
def get_plans(request):
    plans = Plan.objects.filter(is_active=True)
    serializer = PlanSerializer(plans, many=True)
    return Response(serializer.data)

# end of get plans api

# api to get my subscription
@api_view(["GET"])
def my_subscription(request, shop_id):
    shop = Shop.objects.get(id=shop_id)
    # check shop
    if shop is None:
        return Response({"message": "Shop not found"}, status=404)

    sub = get_active_subscription(shop)

    if not sub:
        return Response({"has_subscription": False})

    serializer = ShopSubscriptionSerializer(sub)
    return Response({
        "has_subscription": True,
        "subscription": serializer.data
    })

# end of my subscription api

# start of daraja payment api
STK_PUSH_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
DARAJA_SHORTCODE = '174379'
DARAJA_PASSKEY = os.environ.get("DARAJA_PASSKEY")
CALLBACK_URL = 'https://shopscan-backend.onrender.com/mpesa_callback/'

def lipa_na_mpesa(phone_number, amount):
    # convert amount to int
    amount = int(amount)
    access_token = get_access_token()
    if not access_token:
        return {"error": "Could not get access token"}

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(f"{DARAJA_SHORTCODE}{DARAJA_PASSKEY}{timestamp}".encode()).decode()

    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "BusinessShortCode": DARAJA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": DARAJA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "ShopScan",
        "TransactionDesc": "Payment for subscription"
    }
    print("SHORTCODE:", DARAJA_SHORTCODE)
    print("PASSKEY:", DARAJA_PASSKEY)
    print("TOKEN:", access_token)
    print("URL:", STK_PUSH_URL)


    response = requests.post(STK_PUSH_URL, json=payload, headers=headers)
    return response.json()
    # return JsonResponse(response.json())


# callback endpoint to handle mpesa responses
@csrf_exempt
def mpesa_callback(request):
    if request.method == "POST":
        data = json.loads(request.body)
        stk = data.get("Body", {}).get("stkCallback", {})
        result_code = stk.get("ResultCode")
        checkout_request_id = stk.get("CheckoutRequestID")
        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
            if result_code == 0:
                metadata = stk.get("CallbackMetadata", {}).get("Item", [])
                meta = {i["Name"]: i.get("Value") for i in metadata}
                payment.status = "paid"
                payment.receipt_number = meta.get("MpesaReceiptNumber")
                payment.paid_at = timezone.now()
                payment.save()

                # deactivate old subscriptions
                shop = payment.shopkeeper.shop
                ShopSubscription.objects.filter(shop=shop, is_active=True).update(is_active=False)
        
                # create new subscription
                plan = Plan.objects.get(id=payment.plan.id)
                sub = ShopSubscription.objects.create(
                    shop=shop,
                    plan=plan,
                    start_date=timezone.now(),
                    end_date=timezone.now() + timedelta(days=plan.duration_days),
                    is_active=True
                )
                # send notification
                Notification.objects.create(
                    shopkeeper=payment.shopkeeper,
                    message=f"Your subscription to {plan.plan_name} plan has been activated."
                )


            else:
                payment.status = "failed"
                payment.save()

        except Payment.DoesNotExist:
            print("Payment with CheckoutRequestID not found:", checkout_request_id)

        print(data)
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
    return JsonResponse({"error": "Invalid request"})


# api for  subscribing to plans
@api_view(["POST"])
def subscribe_plan(request):
    plan_id = request.data.get("plan_id")
    shopkeeper = request.data.get("shopkeeper_id")
    phone_number = request.data.get("phone_number")

    print(f"Phone number: {phone_number}")

    plan = Plan.objects.get(id=plan_id)
    if not plan:
        return Response({"message": "Plan not found"}, status=404)

    shopkeeper = ShopKeeper.objects.get(id=shopkeeper)
    if not shopkeeper:
        return Response({"message": "Shopkeeper not found"}, status=404)
    
    phone_number = normalize_phone(phone_number)

    mpesa_response = lipa_na_mpesa(phone_number, plan.price)
    print("MPESA RESPONSE:", mpesa_response)

    if mpesa_response.get("ResponseCode") == "0":

        # create payment
        Payment.objects.create(
            shopkeeper=shopkeeper,
            plan=plan,
            amount=plan.price,
            payment_method="mpesa",
            payment_status="pending",
            paid_at=timezone.now(),
            checkout_request_id=mpesa_response.get("CheckoutRequestID")
        )

        return Response({
            "message": "Stk Push sent to phone number",
            "mpesa_response": mpesa_response
        })
    
    else:
        return Response({
            "message": "Failed to send Stk push.",
            "mpesa_response": mpesa_response
        })

# end of subscribe plan api