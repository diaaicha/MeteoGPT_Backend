from pydantic import BaseModel


class WhatsAppTextMessage(BaseModel):
    """
    Message texte WhatsApp normalisé depuis un webhook Meta.
    """

    sender: str

    message_id: str

    text: str


class WhatsAppWebhookResponse(BaseModel):
    """
    Réponse HTTP renvoyée à Meta après réception du webhook.
    """

    status: str = "received"

    messages_received: int = 0
