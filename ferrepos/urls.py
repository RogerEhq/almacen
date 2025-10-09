# ferrepos/urls.py
from django.contrib import admin
from django.urls import path, include
from pos.views import pos_view

urlpatterns = [
    path('admin/', admin.site.urls),
    # Rutas de Autenticación
    path('accounts/', include('django.contrib.auth.urls')),

    # Rutas de la App POS
    path('pos/', include('pos.urls')),

    # Redirección de la raíz al POS después del login
    path('', pos_view, name='home'),
]