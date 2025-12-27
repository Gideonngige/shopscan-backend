from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signin/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    path('delete_account/', views.delete_account, name='delete_account'),
    path('request_password_reset/', views.request_password_reset, name='request_password_reset'),
    path('get_notifications/<int:shopkeeper_id>/', views.get_notifications, name='get_notifications'),
    path('add_product/', views.add_product, name='add_product'),
]