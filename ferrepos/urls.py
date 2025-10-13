# ferrepos/urls.py
from django.contrib import admin
from django.urls import path, include
# 🎯 CAMBIO: Importamos la nueva vista de despacho en lugar de pos_view
from pos.views import home_dispatch_view

urlpatterns = [
    path('admin/', admin.site.urls),
    # Rutas de Autenticación (incluye login/logout)
    path('accounts/', include('django.contrib.auth.urls')),

    # Rutas de la App POS
    path('pos/', include('pos.urls')),

    # 🎯 Sprint 4: Redirección de la raíz usando la vista de despacho (HU #14)
    # Esta vista redirige automáticamente a 'dashboard' o 'pos_main' según el rol.
    path('', home_dispatch_view, name='home'),
]