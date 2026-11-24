from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("profile/", views.profile, name="profile"),
    path("password/", views.CeloPasswordChangeView.as_view(), name="password_change"),
]
