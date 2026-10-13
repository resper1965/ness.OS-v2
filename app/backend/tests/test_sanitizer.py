# -------------------------------------------------------
# n.infraops — Testes unitários do Sanitizer
# -------------------------------------------------------
from app.core.sanitizer import sanitize, sanitize_dict


def test_sanitize_ipv4():
    text = "Erro no host 192.168.1.100 ao conectar no gateway."
    assert sanitize(text) == "Erro no host [IP_REDACTED] ao conectar no gateway."


def test_sanitize_connection_string():
    text = "Conectando ao banco: postgresql+asyncpg://nessops:changeme@localhost:5432/nessops"
    assert sanitize(text) == "Conectando ao banco: [CONN_STRING_REDACTED]"


def test_sanitize_passwords():
    text1 = "password=SuperSecret123!"
    text2 = "pwd: my_secret_pass"
    assert sanitize(text1) == "password=[REDACTED]"
    assert sanitize(text2) == "pwd=[REDACTED]"


def test_sanitize_api_keys():
    text1 = "api_key=abc123xyz"
    text2 = "client_secret = secret_value"
    assert sanitize(text1) == "api_key=[REDACTED]"
    assert sanitize(text2) == "client_secret=[REDACTED]"


def test_sanitize_bearer_tokens():
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    assert sanitize(text) == "Authorization: Bearer [REDACTED]"


def test_sanitize_aws_keys():
    text = "Minha chave da AWS é ASIA1234567890ABCDEF."
    assert sanitize(text) == "Minha chave da AWS é [AWS_KEY_REDACTED]."


def test_sanitize_hex_tokens():
    # Monte o token fictício em execução para não parecer um segredo no checkout.
    token = "a" * 40
    text = f"Token hexadecimal longo: {token}"
    assert sanitize(text) == "Token hexadecimal longo: [HEX_TOKEN_REDACTED]"


def test_sanitize_dict():
    raw_data = {
        "ip": "10.0.0.1",
        "description": "Server log message: connection failed on postgres://db",
        "nested": {
            "password": "my_password",
            "values": ["192.168.0.1", 123, "safe string"],
        },
    }
    sanitized_data = sanitize_dict(raw_data)
    assert sanitized_data["ip"] == "[IP_REDACTED]"
    assert (
        sanitized_data["description"]
        == "Server log message: connection failed on [CONN_STRING_REDACTED]"
    )
    assert sanitized_data["nested"]["password"] == "[REDACTED]"
    assert sanitized_data["nested"]["values"][0] == "[IP_REDACTED]"
    assert sanitized_data["nested"]["values"][1] == 123
    assert sanitized_data["nested"]["values"][2] == "safe string"
