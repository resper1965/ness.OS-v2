from types import SimpleNamespace as N

from app.api.routers.dashboard import canonical_names


def test_canonical_names_merge_case_and_aliases():
    names = canonical_names(
        [
            N(id=1, key="ness", display_name="Ness"),
            N(id=2, key="alupar-co", display_name="Alupar CO"),
        ],
        [
            N(alias_norm="ness processos e tecnologia ltda.", customer_id=1),
            N(alias_norm="órfão", customer_id=9),
        ],
    )
    assert names["ness"] == "Ness"  # cobre NESS/Ness depois do lower()
    assert names["alupar co"] == names["alupar-co"] == "Alupar CO"
    assert names["ness processos e tecnologia ltda."] == "Ness"
    assert "órfão" not in names
