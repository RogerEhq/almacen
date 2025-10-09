# ferrepos/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from pos.models import CashDrawerSession

class CashDrawerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. No aplicar si no está autenticado o es superusuario (Admin)
        if not request.user.is_authenticated or request.user.is_superuser:
            return self.get_response(request)

        # 2. Solo aplicar a las rutas del POS (asumimos que 'pos_main' es la base)
        if request.path.startswith(reverse('pos_main').strip('/')):
            # Rutas permitidas sin sesión activa
            allowed_paths = [
                reverse('open_session'),
                reverse('logout'),
                reverse('login'),
            ]

            # Si el usuario está en una ruta permitida (ej: open-session), permite el paso
            if request.path in allowed_paths:
                return self.get_response(request)

            # 3. Buscar sesión activa (end_time es NULL)
            active_session = CashDrawerSession.objects.filter(
                user=request.user,
                end_time__isnull=True
            ).first()

            # 4. Si NO existe sesión activa, redirige a la apertura
            if not active_session:
                return redirect('open_session')

        return self.get_response(request)