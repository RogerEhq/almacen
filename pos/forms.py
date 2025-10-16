from django import forms
from .models import Product, Category, Supplier


# Asume que Category y Supplier están en el mismo archivo models.py

class ProductForm(forms.ModelForm):
    """
    Formulario utilizado para crear y editar productos.
    Se utiliza en product_edit_view para reabastecer el stock.
    """

    class Meta:
        model = Product
        # Se incluyen todos los campos del modelo para edición.
        fields = [
            'name',
            'sku',
            'price',
            'cost',
            'stock',
            'category',
            'supplier',
            'low_stock_threshold'
        ]

        # Etiquetas personalizadas para mejorar la interfaz de usuario en español
        labels = {
            'name': 'Nombre del Producto',
            'sku': 'SKU / Código',
            'price': 'Precio de Venta ($)',
            'cost': 'Precio de Costo ($)',
            'stock': 'Stock Actual (para Reabastecer)',
            'category': 'Categoría',
            'supplier': 'Proveedor',
            'low_stock_threshold': 'Umbral Mínimo de Alerta',
        }

        # Widgets para asegurar que los campos numéricos sean tratados como números
        widgets = {
            'stock': forms.NumberInput(attrs={'min': 0}),
            'low_stock_threshold': forms.NumberInput(attrs={'min': 0}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
            'cost': forms.NumberInput(attrs={'step': '0.01'}),
        }


class StockUpdateForm(forms.ModelForm):
    """
    Formulario minimalista para actualizar SÓLO el stock y el umbral de alerta.
    Esto previene errores de validación en otros campos al reabastecer.
    """

    class Meta:
        model = Product
        # Solo incluimos los campos que queremos modificar
        fields = [
            'stock',
            'low_stock_threshold'
        ]

        labels = {
            'stock': 'Stock Nuevo/Total (para Reabastecer)',
            'low_stock_threshold': 'Umbral Mínimo de Alerta',
        }

        widgets = {
            'stock': forms.NumberInput(attrs={'min': 0, 'class': 'form-control-lg'}),
            'low_stock_threshold': forms.NumberInput(attrs={'min': 0}),
        }