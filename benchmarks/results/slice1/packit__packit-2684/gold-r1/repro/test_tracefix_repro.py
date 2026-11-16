from flexmock import flexmock

from packit.utils.koji_helper import KojiHelper


def _helper_with_session(session):
    helper = KojiHelper()
    helper.__dict__["session"] = session
    return helper


def test_cancel_task_success():
    session = flexmock()
    session.should_receive("cancelTask").with_args(123, recurse=True).once()
    helper = _helper_with_session(session)
    assert helper.cancel_task(123) is True


def test_cancel_task_failure():
    session = flexmock()
    session.should_receive("cancelTask").and_raise(Exception("boom"))
    helper = _helper_with_session(session)
    assert helper.cancel_task(123) is False
