"""Keep each WAN widget bound to its verified interface, not its host label."""
import json
from pathlib import Path


def test_cavan_link_identity_and_geometry():
    config = Path(__file__).resolve().parents[2] / 'config/zabbix/cavan-links-uat-dashboard.json'
    payload = json.loads(config.read_text())
    assert payload['private'] == 1 and 'sem coleta' in payload['name']
    widgets = payload['pages'][0]['widgets']
    assert [w['fields'][0]['value'] for w in widgets] == [
        '97682', '97742', '97782', '98076', '98136', '98176']
    for index, widget in enumerate(widgets):
        assert 'wan' in widget['name'] if index < 3 else 'lan3' in widget['name']
        assert {'type': 0, 'name': 'show.1', 'value': 3} in widget['fields']
        assert widget['width'] > 0 and widget['height'] > 0
        for other in widgets[index + 1:]:
            assert not (widget['x'] < other['x'] + other['width']
                        and other['x'] < widget['x'] + widget['width']
                        and widget['y'] < other['y'] + other['height']
                        and other['y'] < widget['y'] + widget['height'])
