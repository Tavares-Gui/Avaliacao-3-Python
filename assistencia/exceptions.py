import logging

from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)
MENSAGEM_ERRO_INTERNO = "Erro interno do servidor. Tente novamente mais tarde."


def api_exception_handler(exc, context):
    """Mantém erros do DRF; traduz PROTECT e não expõe detalhes de falhas inesperadas."""
    if isinstance(exc, ProtectedError):
        return Response(
            {"detail": "Não é possível excluir um cliente com ordens de serviço vinculadas."},
            status=400,
        )
    response = exception_handler(exc, context)
    if response is not None:
        return response
    logger.error("Erro inesperado na API", exc_info=(type(exc), exc, exc.__traceback__))
    return Response({"detail": MENSAGEM_ERRO_INTERNO}, status=500)


def server_error(request):
    """Resposta JSON para falhas externas às views DRF quando DEBUG=False."""
    return JsonResponse({"detail": MENSAGEM_ERRO_INTERNO}, status=500)
