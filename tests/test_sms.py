from unittest.mock import patch, MagicMock
from app import send_sms_notification, _dispatch_sms_async


def test_send_sms_notification_empty():
    # Should safely return without starting thread or throwing errors
    send_sms_notification("", "sender1", "Subject")
    send_sms_notification(None, "sender1", "Subject")


@patch('app._dispatch_sms_async')
def test_send_sms_notification_triggers_async(mock_dispatch):
    send_sms_notification("+1234567890", "sender1", "Test Subject")
    # Wait briefly for daemon thread to start
    import time
    time.sleep(0.1)
    assert mock_dispatch.called


def test_dispatch_sms_async_simulation(capsys):
    # Tests fallback simulation logger when Twilio phone number is dummy/missing
    _dispatch_sms_async("+1234567890", "alice", "Meeting")
    captured = capsys.readouterr()
    assert "[SMS SIMULATION]" in captured.out
    assert "+1234567890" in captured.out
    assert "@alice" in captured.out
