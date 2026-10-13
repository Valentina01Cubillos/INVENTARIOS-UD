def navigation(request):
    from .models import Traslado,AparienciaPerfil
    from .appearance import theme
    from .views import solicitudes_visibles
    query=request.GET.copy()
    query.pop('page',None)
    encoded=query.urlencode()
    pendientes=Traslado.objects.filter(aprobador=request.user,estado='Pendiente').count() if request.user.is_authenticated else 0
    solicitudes=solicitudes_visibles(request.user).filter(estado='Pendiente').count() if request.user.is_authenticated else 0
    appearance=(AparienciaPerfil.objects.filter(usuario=request.user).first() if request.user.is_authenticated else None) or AparienciaPerfil()
    admin=request.user.is_authenticated and (request.user.is_superuser or any(request.user.has_perm(perm) for perm in ['lab.change_laboratorio','lab.importar_datos','auth.view_user','lab.view_auditoria']))
    return {'querystring':encoded+'&' if encoded else '', 'traslados_pendientes':pendientes, 'solicitudes_pendientes':solicitudes,'apariencia':appearance,'tema':theme(appearance),'mostrar_administracion':admin}
