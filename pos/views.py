import datetime
from glob import escape
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.forms import DecimalField, models
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Sum, Count, Q, ExpressionWrapper, F
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import logout
from openpyxl import Workbook
from django.db.models import F

from .forms import ProductForm, StockUpdateForm
from .models import Product, Sale, SaleItem, CashDrawerSession, Supplier
from django.db.models.functions import ExtractYear, ExtractMonth
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- Redirección inicial tras login ---
@login_required
def redirect_after_login(request):
    """Redirige al usuario según si tiene sesión de caja activa."""
    active_session = CashDrawerSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if active_session:
        return redirect('pos_main')
    return redirect('open_session')


# --- Vistas de Caja ---
@login_required
def open_session_view(request):
    """Vista para iniciar un turno de caja (HU #6)."""
    active_session = CashDrawerSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if active_session:
        return redirect('pos_main')

    if request.method == 'POST':
        try:
            starting_balance = Decimal(request.POST.get('starting_balance', '0.00'))
        except:
            starting_balance = Decimal('0.00')

        CashDrawerSession.objects.create(
            user=request.user,
            starting_balance=starting_balance
        )
        return redirect('pos_main')

    return render(request, 'pos/open_session.html')


@login_required
def close_session_view(request):
    """Vista para cerrar el turno de caja (HU #6)."""
    # ... (Se mantiene la lógica para encontrar la sesión activa) ...
    active_session = CashDrawerSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if not active_session:
        return redirect('pos_main')

    # 1. Se calcula el total de ventas en efectivo
    cash_sales = active_session.sales.filter(payment_method='cash').aggregate(total_sum=Sum('total_amount'))[
                     'total_sum'] or Decimal('0.00')

    # 2. Se calcula el total de ventas con tarjeta (solo referencia)
    card_sales = active_session.sales.filter(payment_method='card').aggregate(total_sum=Sum('total_amount'))[
                     'total_sum'] or Decimal('0.00')

    # ✅ CORRECCIÓN CLAVE: El total esperado es SOLO las ventas en efectivo.
    # El fondo inicial se mantiene separado para que el cajero lo retire.
    expected_balance = cash_sales

    context = {
        'session': active_session,
        'cash_sales': cash_sales,
        'card_sales': card_sales,
        'expected_balance': expected_balance,  # Este valor ahora es igual a cash_sales
    }

    if request.method == 'POST':
        try:
            ending_balance = Decimal(request.POST.get('ending_balance', '0.00'))
        except:
            ending_balance = Decimal('0.00')

        notes = request.POST.get('notes', '')

        active_session.end_time = timezone.now()
        active_session.ending_balance = ending_balance
        active_session.notes = notes
        active_session.save()

        logout(request)
        return redirect('login')

    return render(request, 'pos/close_session.html', context)


# --- Vista principal del POS ---
@login_required
def pos_view(request):
    """Vista principal del POS."""
    cart_items = request.session.get('cart', {})
    cart_total = sum(item['subtotal'] for item in cart_items.values())

    active_session = CashDrawerSession.objects.filter(user=request.user, end_time__isnull=True).first()

    context = {
        'cart_items': cart_items.values(),
        'cart_total': cart_total,
        'active_session': active_session
    }
    return render(request, 'pos/pos_main.html', context)


# --- Añadir producto al carrito ---
@login_required
@require_POST
def add_product_view(request):
    """Lógica HTMX: Añadir/incrementar producto con validación de Stock y actualizar total."""
    sku = request.POST.get('sku', '').strip()

    try:
        product = Product.objects.get(sku=sku)
    except Product.DoesNotExist:
        return HttpResponse(
            '<tr style="color: red;"><td colspan="5">Producto con ese código no existe.</td></tr>'
        )

    if product.stock <= 0:
        return HttpResponse(
            '<tr style="color: red;"><td colspan="5">Producto sin stock disponible.</td></tr>'
        )

    cart = request.session.get('cart', {})
    product_id = str(product.id)
    quantity = cart.get(product_id, {}).get('quantity', 0) + 1

    if quantity > product.stock:
        return HttpResponse(
            f'<tr style="color: orange;"><td colspan="5">Stock máximo alcanzado ({product.stock}).</td></tr>'
        )

    cart[product_id] = {
        'id': product.id,
        'sku': product.sku,
        'name': product.name,
        'price': float(product.price),
        'quantity': quantity,
        'subtotal': float(product.price * quantity),
    }

    request.session['cart'] = cart
    request.session.modified = True

    cart_total = sum(item['subtotal'] for item in cart.values())
    context = {
        'item': cart[product_id],
        'cart_total': cart_total
    }

    return render(request, 'pos/cart_row_and_total.html', context)


# --- Finalizar venta ---
@login_required
@require_POST
@transaction.atomic
def checkout_view(request):
    cart = request.session.get('cart', {})
    payment_method = request.POST.get('payment_method', 'cash')

    if not cart:
        return HttpResponse('<p style="color:red;">No hay productos en el carrito.</p>')

    active_session = CashDrawerSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if not active_session:
        return HttpResponse('<p style="color:red;">No hay sesión de caja activa.</p>')

    try:
        sale_items_to_create = []
        cart_total = Decimal(0)

        for product_data in cart.values():
            product_id = product_data['id']
            quantity_sold = product_data['quantity']

            product = Product.objects.select_for_update().get(pk=product_id)

            if quantity_sold > product.stock:
                return HttpResponse(f'<p style="color:red;">Stock insuficiente para {escape(product.name)}.</p>')

            product.stock -= quantity_sold
            product.save()

            unit_price = Decimal(product_data['price'])
            subtotal = Decimal(product_data['subtotal'])
            cart_total += subtotal

            sale_items_to_create.append({
                'product': product,
                'quantity': quantity_sold,
                'unit_price': unit_price,
                'subtotal': subtotal
            })

        sale = Sale.objects.create(
            seller=request.user,
            total_amount=cart_total,
            cash_drawer_session=active_session,
            payment_method=payment_method
        )

        SaleItem.objects.bulk_create([
            SaleItem(
                sale=sale,
                product=item['product'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                subtotal=item['subtotal']
            ) for item in sale_items_to_create
        ])

        # Actualizar el balance de caja si el pago fue en efectivo
        if payment_method == 'cash':
            active_session.starting_balance += cart_total
            active_session.save()

        del request.session['cart']
        request.session.modified = True

    except Exception as e:
        return HttpResponse(f'<p style="color:red;">Error al finalizar la venta: {escape(str(e))}</p>')

    return HttpResponse(f"""
        <div class="success-message">
            ✅ Venta completada con éxito.<br>
            Total vendido: <b>${cart_total:.2f}</b><br>
            Método de pago: <b>{payment_method.title()}</b>
        </div>
        <script>
            const method = "{payment_method}";
            const total = {float(cart_total)};
            const balanceEl = document.getElementById("cash-balance");
            if (method === "cash" && balanceEl) {{
                const current = parseFloat(balanceEl.textContent.replace('$', ''));
                const updated = current + total;
                balanceEl.textContent = "$" + updated.toFixed(2);
            }}
        </script>
    """)

@login_required
def get_cart_total_view(request):
    """Calcula el total del carrito y devuelve solo el fragmento del total para HTMX."""
    cart_items = request.session.get('cart', {})
    cart_total = sum(item['subtotal'] for item in cart_items.values())

    context = {'cart_total': cart_total}
    # Renderiza un fragmento HTML con el nuevo total
    return render(request, 'pos/total_fragment.html', context)


def is_admin_staff(user):
    """Verifica si el usuario es administrador o superusuario."""
    return user.is_staff or user.is_superuser


# ----------------------------------------------------
# B. Tarea 1: Despacho por Rol (HU #14)
# ----------------------------------------------------

@login_required
def home_dispatch_view(request):
    if is_admin_staff(request.user):
        # 1. ADMIN: Va al dashboard
        return redirect('dashboard')
    else:
        # 2. VENDEDOR: Chequeo de caja (Lógica del HU #11/Sprint 3)
        active_session = CashDrawerSession.objects.filter(
            user=request.user,
            end_time__isnull=True
        ).first()

        if active_session:
            # Sesión activa: va al POS
            return redirect('pos_main')
        else:
            # Sesión inactiva: va a abrir caja
            return redirect('open_session')

    # ----------------------------------------------------


# C. Tarea 2: Dashboard y Top Productos (HU #8 y #13)
# ----------------------------------------------------

def is_admin_staff(user):
    return user.is_staff or user.is_superuser


@user_passes_test(is_admin_staff)
@login_required
def dashboard_view(request):
    today = timezone.now().date()

    # Filtramos las ventas para hoy (asumiendo que 'sale_date' es un campo DateTimeField o DateField)
    today_sales = Sale.objects.filter(sale_date__date=today)

    today_metrics = today_sales.aggregate(
        total_sales=Sum('total_amount'),
        num_transactions=Count('id')
    )

    total_sales = today_metrics.get('total_sales') or Decimal('0.00')
    num_transactions = today_metrics.get('num_transactions') or 0
    ticket_average = (total_sales / num_transactions) if num_transactions else Decimal('0.00')

    active_sessions = CashDrawerSession.objects.filter(end_time__isnull=True).count()

    # ✅ CORRECCIÓN FINAL (en la vista): Se elimina el alias product_name= para evitar el TypeError.
    top_products = SaleItem.objects.values('product__name') \
                       .annotate(total_sold=Sum('quantity')) \
                       .order_by('-total_sold')[:5]

    # 🎯 NUEVA LÓGICA: Contar productos con inventario bajo (HU #16)
    # Filtra los productos donde el stock actual es menor o igual al umbral definido.
    low_stock_count = Product.objects.filter(
        stock__lte=F('low_stock_threshold')
    ).count()

    context = {
        'ventas_hoy': total_sales,
        'transacciones_hoy': num_transactions,
        'ticket_promedio': ticket_average,
        'sesiones_activas': active_sessions,
        'top_products': top_products,
        'low_stock_count': low_stock_count,  # <<-- Se añade el conteo al contexto
    }

    return render(request, 'pos/dashboard.html', context)


@user_passes_test(is_admin_staff)
@login_required
def sales_report_view(request):
    sales = None
    totals = {}
    date_range_str = ""

    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')

        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date_inclusive = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                date_range_str = f"{start_date_str} a {end_date_str}"

                sales = Sale.objects.filter(
                    sale_date__date__gte=start_date,
                    sale_date__date__lte=end_date_inclusive
                ).select_related('cash_drawer_session__user').order_by('-sale_date')

                # NUEVA LÓGICA: Verificar si se solicitó la exportación a Excel
                if 'export_excel' in request.POST:
                    return export_sales_excel(request, sales, date_range_str)

                # Lógica ya existente: Verificar si se solicitó la exportación a PDF
                if 'export_pdf' in request.POST:
                    return export_sales_pdf(request, sales, date_range_str)

                # El resto del código solo se ejecuta si NO se exporta
                report_totals = sales.aggregate(
                    total_sales=Sum('total_amount'),
                    total_transactions=Count('id'),
                    total_cash_sales=Sum('total_amount', filter=Q(payment_method='cash')),
                    total_card_sales=Sum('total_amount', filter=Q(payment_method='card')),
                )

                totals = {
                    'total_sales': report_totals.get('total_sales') or 0.00,
                    'total_transactions': report_totals.get('total_transactions') or 0,
                    'total_cash': report_totals.get('total_cash_sales') or 0.00,
                    'total_card': report_totals.get('total_card_sales') or 0.00,
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                }

            except ValueError:
                pass

    context = {
        'sales': sales,
        'totals': totals,
    }
    return render(request, 'pos/sales_report.html', context)


# --- 1. Lista de Productos con Stock Bajo ---
@user_passes_test(is_admin_staff)
@login_required
def product_list_view(request):
    """Muestra una lista paginada de productos con opciones de filtro."""

    # Parámetros de filtro
    filter_by = request.GET.get('filter', 'all')

    products = Product.objects.select_related('category', 'supplier').all()

    if filter_by == 'low_stock':
        # Asumiendo que 'low_stock' se define como 5 unidades o menos
        products = products.filter(stock__lte=5)

    # Puedes implementar paginación aquí si la lista es muy grande

    context = {
        'products': products,
        'current_filter': filter_by,
        'low_stock_count': Product.objects.filter(stock__lte=5).count()
    }

    return render(request, 'pos/product_list.html', context)


# --- 2. Inventario por Proveedor ---
@user_passes_test(is_admin_staff)
@login_required
def supplier_inventory_view(request, supplier_id):
    """Muestra los productos de un proveedor específico."""

    # Asume que el modelo Supplier está importado
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    # 1. Traer todos los productos del proveedor
    # No usamos ninguna anotación o expresión compleja aquí.
    products = Product.objects.filter(supplier=supplier).select_related('category')

    total_stock_value = Decimal('0.00')

    # 2. ✅ SOLUCIÓN: Calcular el valor total del stock en Python.
    for product in products:
        # Multiplicar Costo (Decimal) por Stock (convertido a Decimal)
        product_stock = Decimal(product.stock)
        total_stock_value += product.cost * product_stock

    context = {
        'supplier': supplier,
        'products': products,
        'total_stock_value': total_stock_value
    }

    return render(request, 'pos/supplier_inventory.html', context)


# --- 3. Resumen de Ventas Mensuales ---
@user_passes_test(is_admin_staff)
@login_required
def monthly_summary_view(request):
    """Muestra un resumen de ventas totales agrupadas por mes."""

    # Agrupa las ventas por año y mes
    monthly_sales = Sale.objects.annotate(
        year=ExtractYear('sale_date'),
        month=ExtractMonth('sale_date')
    ).values('year', 'month').annotate(
        total_amount=Sum('total_amount'),
        total_transactions=Count('id')
    ).order_by('-year', '-month')

    # ✅ CORRECCIÓN CLAVE: Calcular el ticket promedio en Python
    sales_with_average = []
    for summary in monthly_sales:
        num_transactions = summary['total_transactions']
        total_amount = summary['total_amount']

        # Manejo seguro de la división por cero
        if num_transactions and total_amount:
            # Usar Decimal para mantener la precisión financiera
            summary['ticket_promedio'] = total_amount / Decimal(num_transactions)
        else:
            summary['ticket_promedio'] = Decimal('0.00')

        sales_with_average.append(summary)

    context = {
        'monthly_sales': sales_with_average
    }

    return render(request, 'pos/monthly_summary.html', context)


def export_sales_pdf(request, sales_queryset, date_range):
    """
    Genera un archivo PDF con la lista de ventas proporcionada por el queryset.

    :param sales_queryset: Queryset de objetos Sale (Venta) ya filtrados.
    :param date_range: Cadena de texto descriptiva del rango de fechas (ej: "2023-01-01 a 2023-01-31").
    """
    # 1. Configurar la respuesta HTTP para PDF
    response = HttpResponse(content_type='application/pdf')
    # Define el nombre del archivo para la descarga
    file_name = f"reporte_ventas_{datetime.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'

    # 2. Crear el objeto SimpleDocTemplate de reportlab
    # Este objeto gestiona el documento y aplica los datos a la respuesta.
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []  # Lista de elementos (Párrafos, Tablas, Espacios) a añadir al PDF.

    # Obtener estilos de ejemplo
    styles = getSampleStyleSheet()

    # 3. Título del Reporte
    title_text = f"Reporte de Ventas: {date_range}"
    elements.append(Paragraph(title_text, styles['Heading1']))
    elements.append(Spacer(1, 18))  # Espacio vertical de 18 puntos

    # 4. Preparar los datos de la tabla
    # Encabezados de la tabla
    data = [
        ['ID Venta', 'Fecha', 'Total ($)', 'Vendedor']
    ]

    # Llenar la tabla con los datos del queryset
    for sale in sales_queryset:
        # Asegúrate de que los campos existan en tu modelo Sale (Venta)
        data.append([
            sale.id,
            sale.sale_date.strftime("%Y-%m-%d %H:%M"),
            f"{sale.total_amount:.2f}",  # Formato de moneda
            sale.seller.username if sale.seller else 'N/A'
        ])

    # 5. Crear la tabla y aplicar estilos
    table = Table(data, colWidths=[60, 140, 100, 140])

    # Estilos de la tabla
    style = TableStyle([
        # Encabezado (primera fila)
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361ee')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

        # Alineación y Bordes
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),  # Alineación general
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),  # Alinea la columna de Total a la derecha
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ])

    # Alternar color de fondo en filas de datos para mejor legibilidad
    row_count = len(data)
    for i in range(1, row_count):
        bg_color = colors.white if i % 2 == 0 else colors.HexColor('#f0f0f0')  # Gris claro
        style.add('BACKGROUND', (0, i), (-1, i), bg_color)

    table.setStyle(style)
    elements.append(table)

    # 6. Construir y retornar el PDF
    doc.build(elements)

    return response


def export_sales_excel(request, sales_queryset, date_range):
    """
    Genera un archivo Excel con la lista de ventas.
    """
    # 1. Configurar la respuesta HTTP para Excel
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    file_name = f"reporte_ventas_{datetime.now().strftime('%Y%m%d')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'

    # 2. Crear Workbook y Hoja
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte de Ventas"

    # 3. Encabezados de la tabla
    headers = ['ID Venta', 'Fecha y Hora', 'Total ($)', 'Método de Pago', 'Vendedor']
    ws.append(headers)

    # Estilo de encabezado (opcional, pero mejora la presentación)
    header_style = ws['A1':'E1']
    from openpyxl.styles import Font, PatternFill
    font = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="4361ee")

    for cell in header_style[0]:
        cell.font = font
        cell.fill = fill

    # 4. Llenar la tabla con los datos
    for sale in sales_queryset:
        # Utilizamos el método get_payment_method_display() tal como se usa en el HTML
        data_row = [
            sale.id,
            sale.sale_date.strftime("%Y-%m-%d %H:%M"),
            sale.total_amount,
            sale.get_payment_method_display(),
            sale.cash_drawer_session.user.username if sale.cash_drawer_session and sale.cash_drawer_session.user else 'N/A',
        ]
        ws.append(data_row)

    # Ajustar el ancho de las columnas
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter  # Get the column name
        for cell in col:
            try:  # Necessary to avoid error on empty cells
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

    # 5. Guardar el Workbook en la respuesta HTTP
    wb.save(response)
    return response


@user_passes_test(is_admin_staff)
@login_required
def low_inventory_alert_view(request):
    """
    Muestra la lista de productos cuyo stock es bajo.
    """
    # El filtro ahora funciona correctamente porque F está importado desde django.db.models
    low_stock_products = Product.objects.filter(
        stock__lte=F('low_stock_threshold')
    ).order_by('stock')

    context = {
        'products': low_stock_products,
        'alert_count': low_stock_products.count(),
    }

    return render(request, 'pos/low_inventory_alert.html', context)


@user_passes_test(is_admin_staff)
@login_required
def product_edit_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        # 🎯 Usamos el formulario ligero aquí
        form = StockUpdateForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            # Opcional: Agregar mensaje de éxito
            # messages.success(request, f"Stock de {product.name} actualizado con éxito.")
            return redirect('low_inventory_alert')
    else:
        # 🎯 Usamos el formulario ligero para mostrar
        form = StockUpdateForm(instance=product)

    # Cambiamos el nombre del template si vas a crear uno nuevo,
    # pero si solo quieres modificar el actual, lo mantienes.
    return render(request, 'pos/product_form.html', {'form': form, 'product': product})