from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
# Sprint 2: Modelos de Soporte
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre")

    def __str__(self): return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=150, verbose_name="Nombre del Proveedor")

    def __str__(self): return self.name


# Sprint 2: Modelo Producto Extendido
class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nombre")
    sku = models.CharField(max_length=100, unique=True, verbose_name="SKU / Código")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de Venta")
    cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de Costo", null=True, blank=True)
    stock = models.PositiveIntegerField(default=0, verbose_name="Cantidad en Stock")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoría")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Proveedor")

    def __str__(self): return self.name


# Sprint 3: Modelo Sesión de Caja
class CashDrawerSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Cajero")
    start_time = models.DateTimeField(auto_now_add=True, verbose_name="Hora de Apertura")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="Hora de Cierre")
    starting_balance = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Fondo Inicial")
    ending_balance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name="Saldo de Cierre")
    notes = models.TextField(blank=True, verbose_name="Notas de Cierre")

    def __str__(self):
        end_str = self.end_time.strftime('%H:%M') if self.end_time else 'Activa'
        return f"Sesión {self.id} de {self.user.username}"


# Sprint 3: Modelo Venta
class Sale(models.Model):
    # Usamos 'sale_date' como campo principal, que en el error anterior era 'fecha_de_venta'
    sale_date = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Si estás usando la configuración estándar de Django, 'User' es correcto.
    seller = models.ForeignKey(User, on_delete=models.CASCADE)

    # Vínculo a la Sesión de Caja (HU #6)
    cash_drawer_session = models.ForeignKey(CashDrawerSession, on_delete=models.PROTECT, related_name='sales',
                                            verbose_name="Turno de Caja")

    # Múltiples Métodos de Pago (HU #5)
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Efectivo'),
        ('card', 'Tarjeta'),
    ]
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='cash',
                                      verbose_name="Método de Pago")

    def __str__(self):
        return f"Venta #{self.id} - Total: ${self.total_amount}"


# Sprint 1: Modelo Ítem de Venta
class SaleItem(models.Model):
    # 🎯 CORRECCIÓN CLAVE: Usamos la cadena 'Sale' para evitar el error E300.
    sale = models.ForeignKey('Sale', related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    # Campo para guardar el nombre del producto en el momento de la venta (para reportes)
    product_name = models.CharField(max_length=200, default='N/A')

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
