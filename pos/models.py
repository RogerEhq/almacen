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
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        verbose_name="Umbral de Stock Bajo",
        help_text="Stock mínimo para disparar una alerta."
    )
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
    client = models.ForeignKey(
        'Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Cliente Asociado"
    )
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


class Client(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellido", blank=True, null=True)
    company_name = models.CharField(max_length=200, verbose_name="Empresa / Razón Social", blank=True, null=True)
    # Identificador clave para clientes profesionales (ej: NIT, Cédula, RUC)
    tax_id = models.CharField(max_length=50, unique=True, verbose_name="RUC/NIT/ID Fiscal")
    phone = models.CharField(max_length=20, verbose_name="Teléfono", blank=True, null=True)
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    address = models.CharField(max_length=255, verbose_name="Dirección de Facturación", blank=True, null=True)

    # Campo para identificar clientes que requieren factura formal
    is_professional = models.BooleanField(default=False, verbose_name="Cliente Profesional/Empresa")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        # Muestra el nombre completo o la empresa si existe
        if self.company_name:
            return f"{self.company_name} ({self.tax_id})"
        return f"{self.first_name} {self.last_name or ''}"