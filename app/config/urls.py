from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path

from inventario import faltas, historial, views

admin.site.site_header = "Administración"
admin.site.site_title = "Materiales"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth.LoginView.as_view(template_name="inventario/login.html",
                                          redirect_authenticated_user=True), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("", views.inicio, name="inicio"),
    path("ocarines/", views.menu_variantes, {"tabla": "ocarina"}, name="ocarines"),
    path("ocarines/<slug:variante>/", views.pagina, {"tabla": "ocarina"}, name="ocarina_var"),
    path("manipulos/", views.menu_variantes, {"tabla": "manipulo"}, name="manipulos"),
    path("manipulos/<slug:variante>/", views.pagina, {"tabla": "manipulo"}, name="manipulo_var"),
    path("historial/", historial.historial, name="historial"),
    path("faltas/", faltas.faltas, name="faltas"),
    path("api/historial/<uuid:lote>/deshacer/", historial.deshacer),
    path("api/<slug:tabla>/nuevo/", views.nuevo),
    path("api/<slug:tabla>/montar/", views.montar),
    path("api/<slug:tabla>/reciclar/", views.reciclar),
    path("api/<slug:tabla>/<int:pk>/ajustar/", views.ajustar),
    path("api/<slug:tabla>/<int:pk>/editar/", views.editar),
    path("api/<slug:tabla>/<int:pk>/borrar/", views.borrar),
]
