"""Excepciones del dominio de servicios (las rutas las mapean a HTTP)."""


class ServiceError(Exception):
    """Base de errores de negocio."""


class AuthError(ServiceError):
    """Credenciales no válidas o cuenta no utilizable. Mensaje genérico."""


class InvitationError(ServiceError):
    """Invitación inexistente, caducada, usada o agotada."""


class ConflictError(ServiceError):
    """username o email ya en uso."""

    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field
