from django.contrib import admin
from django.contrib.auth import views as auth
from django.shortcuts import redirect
from django.urls import path

from inventario import views

admin.site.site_header = "Administración"
admin.site.site_title = "Materiales"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth.LoginView.as_view(template_name="inventario/login.html",
                                          redirect_authenticated_user=True), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("", lambda r: redirect("ocarinas"), name="inicio"),
    path("ocarinas/", views.pagina, {"tabla": "ocarina"}, name="ocarinas"),
    path("manipulos/", views.pagina, {"tabla": "manipulo"}, name="manipulos"),
    path("api/<slug:tabla>/nuevo/", views.nuevo),
    path("api/<slug:tabla>/<int:pk>/ajustar/", views.ajustar),
    path("api/<slug:tabla>/<int:pk>/editar/", views.editar),
    path("api/<slug:tabla>/<int:pk>/borrar/", views.borrar),
]
