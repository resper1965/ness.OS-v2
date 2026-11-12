#!/usr/bin/env python3
"""Imprime o SQL que grava config/glpi/ness-entity.css na entidade raiz do GLPI.

Uso (na aiops, depois de backup do custom_css_code):
  python3 glpi-apply-brand.py ness-entity.css logo.png logo-inverse.png \
    | docker exec -i ninf-glpi-db sh -c 'mariadb -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
O GLPI aplica strip_tags no CSS; por isso o CSS não pode conter '<'.
"""

import base64
import sys
from pathlib import Path


def build(css: str, big: bytes, small: bytes) -> str:
    def uri(b: bytes) -> str:
        return f'url("data:image/png;base64,{base64.b64encode(b).decode()}")'

    out = css.replace("__LOGO_BIG__", uri(big)).replace("__LOGO_SMALL__", uri(small))
    assert "<" not in out and "__LOGO_" not in out
    return (
        "UPDATE glpi_entities SET enable_custom_css=1, "
        f"custom_css_code=X'{out.encode().hex()}' WHERE id=0;\n"
    )


if __name__ == "__main__":
    css, big, small = sys.argv[1:4]
    sys.stdout.write(
        build(Path(css).read_text(), Path(big).read_bytes(), Path(small).read_bytes())
    )
