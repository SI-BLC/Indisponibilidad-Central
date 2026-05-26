from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError
from config import settings


def authenticate_user(username: str, password: str) -> dict | None:
    """
    Autentica usuario contra Active Directory.
    1. Bind con cuenta de servicio para buscar el usuario.
    2. Bind con credenciales del usuario para verificar contraseña.
    3. Verifica membresía en grupo que empiece con LDAP_GROUP_PREFIX.
    Retorna dict con info del usuario o None si falla.
    """
    server = Server(settings.LDAP_HOST, port=settings.LDAP_PORT, get_info=ALL)

    # Bind con cuenta de servicio
    try:
        service_conn = Connection(
            server,
            user=f"{settings.LDAP_BIND_USER}@{settings.LDAP_DOMAIN}",
            password=settings.LDAP_BIND_PASSWORD,
            auto_bind=True,
        )
    except LDAPException as e:
        raise RuntimeError(f"No se pudo conectar al servidor LDAP: {e}")

    # Buscar usuario por sAMAccountName
    service_conn.search(
        search_base=settings.LDAP_BASE_DN,
        search_filter=f"(sAMAccountName={username})",
        search_scope=SUBTREE,
        attributes=["distinguishedName", "displayName", "mail", "memberOf", "sAMAccountName"],
    )

    if not service_conn.entries:
        service_conn.unbind()
        return None

    user_entry = service_conn.entries[0]
    user_dn = str(user_entry.distinguishedName)
    service_conn.unbind()

    # Verificar contraseña bindeando como el usuario
    try:
        user_conn = Connection(
            server,
            user=user_dn,
            password=password,
            auto_bind=True,
        )
        user_conn.unbind()
    except LDAPBindError:
        return None
    except LDAPException:
        return None

    # Verificar membresía en grupo autorizado
    member_of = list(user_entry.memberOf) if user_entry.memberOf else []
    authorized = False
    for group_dn in member_of:
        # group_dn ej: "CN=Security - BLC PG Admins,OU=...,DC=blcglobal,DC=net"
        cn_part = str(group_dn).split(",")[0]
        cn_value = cn_part[3:] if cn_part.upper().startswith("CN=") else cn_part
        if cn_value.startswith(settings.LDAP_GROUP_PREFIX):
            authorized = True
            break

    if not authorized:
        return None

    return {
        "username": str(user_entry.sAMAccountName),
        "display_name": str(user_entry.displayName) if user_entry.displayName else username,
        "email": str(user_entry.mail) if user_entry.mail else "",
    }
