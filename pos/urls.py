# pos/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Rutas de Caja (Sprint 3)
    path('open-session/', views.open_session_view, name='open_session'),
    path('close-session/', views.close_session_view, name='close_session'),

    # Rutas del POS (Sprint 1, 2)
    path('', views.pos_view, name='pos_main'),
    path('add-product/', views.add_product_view, name='add_product'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('inicio/', views.redirect_after_login, name='redirect_after_login'),
    path('add-product/', views.add_product_view, name='add_product'),
    path('get-total-htmx/', views.get_cart_total_view, name='update_total'),


]