from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.catalog, name="list"),
    path("shoe/<slug:slug>/", views.product_detail, name="product"),
]
