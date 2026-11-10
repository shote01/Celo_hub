from django.urls import path

from . import views

app_name = "sales"
urlpatterns = [
    path("", views.sale_list, name="list"),
    path("new/", views.sale_new, name="new"),
    path("<int:pk>/receipt/", views.receipt, name="receipt"),
    path("customers/", views.customer_lookup, name="customers"),
    path("customers/new/", views.customer_edit, name="customer_new"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
]
