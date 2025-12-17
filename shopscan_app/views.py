from django.shortcuts import render
from django.http import HttpResponse

import pyrebase
import firebase_admin
from firebase_admin import credentials, auth
import os, json
from django.http import JsonResponse


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