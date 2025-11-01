from django.urls import path
from . import views

urlpatterns = [
    path("", views.map_view, name="map"),
    path("iso/", views.get_isochrones, name="get_isochrones"),
    path("facilities/", views.get_facilities, name="get_facilities"),  # 👈 new
]

