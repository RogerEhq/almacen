from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import logout

from .models import Product, Sale, SaleItem, CashDrawerSession


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
    active_session = CashDrawerSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if not active_session:
        return redirect('pos_main')

    cash_sales = active_session.sales.filter(payment_method='cash').aggregate(total_sum=Sum('total_amount'))['total_sum'] or Decimal('0.00')
    card_sales = active_session.sales.filter(payment_method='card').aggregate(total_sum=Sum('total_amount'))['total_sum'] or Decimal('0.00')
    expected_balance = active_session.starting_balance + cash_sales

    context = {
        'session': active_session,
        'cash_sales': cash_sales,
        'card_sales': card_sales,
        'expected_balance': expected_balance,
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
    """Lógica HTMX: Añadir/incrementar producto con validación de Stock."""
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

    context = {'item': cart[product_id]}
    return render(request, 'pos/product_row.html', context)


# --- Finalizar venta ---
@login_required
@require_POST
@transaction.atomic
def checkout_view(request):
    """Finaliza la venta, reduce stock y registra método de pago."""
    cart = request.session.get('cart', {})
    payment_method = request.POST.get('payment_method', 'cash')

    if not cart:
        return redirect('pos_main')

    active_session = CashDrawerSession.objects.filter(user=request.user, end_time__isnull=True).first()
    if not active_session:
        return redirect('open_session')

    try:
        sale_items_to_create = []
        cart_total = Decimal(0)

        for product_data in cart.values():
            product_id = product_data['id']
            quantity_sold = product_data['quantity']

            product = Product.objects.select_for_update().get(pk=product_id)

            if quantity_sold > product.stock:
                raise Exception(f"Stock insuficiente para {product.name}.")

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

        del request.session['cart']
        request.session.modified = True

    except Exception:
        return redirect('pos_main')

    return redirect('pos_main')

@login_required
def get_cart_total_view(request):
    """Calcula el total del carrito y devuelve solo el fragmento del total para HTMX."""
    cart_items = request.session.get('cart', {})
    cart_total = sum(item['subtotal'] for item in cart_items.values())

    context = {'cart_total': cart_total}
    # Renderiza un fragmento HTML con el nuevo total
    return render(request, 'pos/total_fragment.html', context)