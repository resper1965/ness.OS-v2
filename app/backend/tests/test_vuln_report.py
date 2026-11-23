"""Texto do e-mail mensal de vulnerabilidades (sem banco)."""


def test_monthly_email_body_lists_each_customer():
    from app.services.vuln_report import body

    text = body(
        [("rzk", "Critical", 1500), ("rzk", "High", 3), ("target", "Low", 2)],
        {"rzk": 10, "target": 1},
        "https://x/e",
    )
    assert "RZK: 10 máquinas · Crítica 1.500 · Alta 3 · Média 0 · Baixa 0" in text
    assert "TARGET: 1 máquinas" in text and text.endswith("https://x/e")
