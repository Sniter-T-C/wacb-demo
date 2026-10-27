import pytest

from notifiers.base import Notifier
from notifiers.whatsapp import WhatsAppNotifier


def test_whatsapp_notifier_is_a_notifier():
    assert isinstance(WhatsAppNotifier(), Notifier)


def test_whatsapp_send_is_not_implemented():
    with pytest.raises(NotImplementedError, match="WhatsApp"):
        WhatsAppNotifier().send("hola")
