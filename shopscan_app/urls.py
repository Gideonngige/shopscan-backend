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
    path('get_products/<int:shop_id>/', views.get_products, name='get_products'),
    path('add_stock/', views.add_stock, name='add_stock'),
    path('update_shopkeeper_profile/', views.update_shopkeeper_profile, name='update_shopkeeper_profile'),
    path('create_bulk_sale/', views.create_bulk_sale, name='create_bulk_sale'),
    path('delete_product/<int:shopkeeper_id>/<int:product_id>/', views.delete_product, name='delete_product'),
    path('shopkeeper_dashboard/<int:shopkeeper_id>/', views.shopkeeper_dashboard, name='shopkeeper_dashboard'),
    path('recent_sales/<int:shop_id>/', views.recent_sales, name='recent_sales'),
    path('dashboard_summary/<int:shop_id>/', views.dashboard_summary, name='dashboard_summary'),
    path('weekly_sales/<int:shop_id>/', views.weekly_sales, name='weekly_sales'),
    path('stock_status/<int:shop_id>/', views.stock_status, name='stock_status'),
]