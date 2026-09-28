from app.api.routers.tenants import _tenant_list


def test_tenant_list_deduplicates_case_insensitively_and_sorts_by_name() -> None:
    assert _tenant_list(
        [
            ("Cavan", "Cavan Tecnologia"),
            ("cavan", "Cavan RMM"),
            ("alupar", "Alupar"),
            (" ", "Sem identificador"),
            (None, None),
        ]
    ) == [
        {"id": "alupar", "name": "Alupar"},
        {"id": "cavan", "name": "Cavan Tecnologia"},
    ]
