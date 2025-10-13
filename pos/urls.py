# pos/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Rutas de Caja (Sprint 3)
    # 🎯 La vista open_session_view es el destino forzado por el Middleware.
    path('open-session/', views.open_session_view, name='open_session'),
    path('close-session/', views.close_session_view, name='close_session'),

    # Rutas del POS (Sprint 1, 2)
    # 🎯 Esta ruta es el objetivo del Vendedor después del login/despacho.
    # El Middleware interceptará esta ruta si no hay caja activa.
    path('', views.pos_view, name='pos_main'),

    path('add-product/', views.add_product_view, name='add_product'),
    path('checkout/', views.checkout_view, name='checkout'),

    # ⚠️ Esta ruta es solo para lógica interna del POS (ej. HTMX)
    path('get-total-htmx/', views.get_cart_total_view, name='update_total'),

    # Rutas de BI/Admin (Sprint 4)
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('reports/sales/', views.sales_report_view, name='sales_report'),

    # NOTA: La ruta 'inicio/' y la segunda 'add-product/' se han eliminado por duplicación/redundancia.
]