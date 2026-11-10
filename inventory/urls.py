from django.urls import path

from . import views

app_name = "inventory"
urlpatterns = [
    path("", views.stock_list, name="stock"),
    path("receive/", views.receive_stock, name="receive"),
    path("waste/", views.waste_list, name="waste"),
    path("waste/new/", views.record_waste, name="waste_new"),
    path("products/", views.product_list, name="products"),
    path("products/new/", views.product_edit, name="product_new"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
]
