import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('link-transition-recovery.py'))
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class Transport:
    def __init__(self, failure):
        self.failure = failure
        self.macro = True
        self.template = '10989'

    def call(self, method, params, token):
        if method == 'usermacro.get':
            assert params['hostids'] == ['10873']
            if self.failure == 'macro_read':
                raise TimeoutError()
            return [{'hostmacroid': '99'}] if self.macro else []
        if method == 'usermacro.delete':
            assert params == ['99']
            if self.failure == 'macro_delete':
                raise TimeoutError()
            self.macro = False
            if self.failure == 'macro_response_lost':
                raise TimeoutError()
            return ['99']
        if method == 'host.update':
            assert not self.macro, 'Never restore deleting retention under a restrictive filter'
            assert params == {'hostid': '10873', 'templates': [{'templateid': '10604'}]}
            self.template = '10604'
            if self.failure == 'template_response_lost':
                raise TimeoutError()
            return ['10873']
        if method == 'host.get':
            return [{'parentTemplates': [{'templateid': self.template}]}]
        raise AssertionError('Unexpected API method')


def test_unknown_filter_preserves_never_delete_template():
    for failure in ['macro_read', 'macro_delete']:
        transport = Transport(failure)
        result = recovery.recover_link(transport.call, '10873', '10604', 'opaque')
        assert result['restored'] is False
        assert transport.template == '10989'
        assert result['errors']


def test_lost_responses_are_verified_by_state_not_repeated_blindly():
    for failure in ['macro_response_lost', 'template_response_lost', None]:
        transport = Transport(failure)
        result = recovery.recover_link(transport.call, '10873', '10604', 'opaque')
        assert result['restored'] is True
        assert transport.macro is False
        assert transport.template == '10604'
