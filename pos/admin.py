# pos/admin.py
from django.contrib import admin
from django.db.models import Sum
from decimal import Decimal
from .models import Product, Category, Supplier, Sale, SaleItem, CashDrawerSession


# Registro de Productos (Sprint 2)
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'price', 'stock', 'category')
    list_filter = ('category', 'supplier')
    search_fields = ('name', 'sku')


# Registro de Sesiones de Caja (Sprint 3: Auditoría HU #12)
@admin.register(CashDrawerSession)
class CashDrawerSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_time', 'end_time',
                    'starting_balance', 'get_total_cash_sales',
                    'ending_balance', 'get_expected_balance', 'get_difference')
    readonly_fields = ('start_time',)
    list_filter = ('user', 'start_time')

    def get_total_cash_sales(self, obj):
        # Calcula ventas en efectivo para el turno
        total = obj.sales.filter(payment_method='cash').aggregate(total_sum=Sum('total_amount'))[
                    'total_sum'] or Decimal('0.00')
        return total

    get_total_cash_sales.short_description = 'Ventas Efectivo'

    def get_expected_balance(self, obj):
        # Fondo Inicial + Ventas en Efectivo
        cash_sales = self.get_total_cash_sales(obj)
        return obj.starting_balance + cash_sales

    get_expected_balance.short_description = 'Total Esperado'

    def get_difference(self, obj):
        if obj.ending_balance is None:
            return "N/A"
        expected = self.get_expected_balance(obj)
        difference = obj.ending_balance - expected

        style = "color: red;" if difference != Decimal('0.00') else "color: green;"
        return f'<span style="{style}">{difference.quantize(Decimal("0.01"))}</span>'

    get_difference.short_description = 'Diferencia'
    get_difference.allow_tags = True


# Registro de Modelos Simples
admin.site.register(Category)
admin.site.register(Supplier)
admin.site.register(Sale)
admin.site.register(SaleItem)