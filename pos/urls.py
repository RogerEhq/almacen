# pos/urls.py
from django.urls import path
from . import views
from .views import product_list_view, supplier_inventory_view, monthly_summary_view

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
    path('inventory/products/', product_list_view, name='product_list'),

    # 2. Inventario por Proveedor (Requiere el ID del proveedor)
    path('inventory/suppliers/<int:supplier_id>/', supplier_inventory_view, name='supplier_inventory'),

    # 3. Resumen Mensual
    path('reports/monthly-summary/', monthly_summary_view, name='monthly_summary'),
    # NOTA: La ruta 'inicio/' y la segunda 'add-product/' se han eliminado por duplicación/redundancia.
    path('inventario/alerta-stock/', views.low_inventory_alert_view, name='low_inventory_alert'),
    path('productos/editar/<int:product_id>/', views.product_edit_view, name='product_edit'),
    path('clientes/', views.client_list_view, name='client_list'),
    path('clientes/crear/', views.client_create_view, name='client_create'),
    path('clientes/editar/<int:client_id>/', views.client_edit_view, name='client_edit'),
    path('clientes/eliminar/<int:client_id>/', views.client_delete_view, name='client_delete'),
    path('ajax/clientes/buscar/', views.client_search_ajax, name='client_search_ajax'),
]