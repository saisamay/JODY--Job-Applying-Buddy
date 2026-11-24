"""Tenant-facing presentation contract. Operator checks never change tenant connection state."""

from enum import StrEnum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .routes import Owner

GMAIL_CALLBACK = "/api/v1/integrations/gmail/callback"
LOCAL_CALLBACK = "http://127.0.0.1:8765" + GMAIL_CALLBACK
READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
callback_contract = APIRouter()


@callback_contract.get(GMAIL_CALLBACK)
def inactive_callback(owner: Owner) -> None:
    # The deployed API has no pending browser authorization ceremony.
    raise HTTPException(409, "No active Gmail authorization. Start the local owner check.")


class ConnectionState(StrEnum):
    disconnected = "Disconnected"
    authorization_required = "Authorization required"
    connecting = "Connecting"
    verified = "Connected and verified"
    expired = "Expired"
    failed = "Failed"
    disabled = "Disabled"


class IntegrationCard(BaseModel):
    provider: str
    label: str
    state: ConnectionState
    instruction: str


PROVIDERS = {
    "gmail": ("Gmail", "Authorize read-only mailbox access with the owner check."),
    "github": ("GitHub projects", "Check a selected repository using Contents read access."),
    "resume_git": ("Private LaTeX repository", "Verify the master file at a pinned commit."),
    "telegram": ("Telegram", "Verify the operator bot. Private chat linking is pending."),
    "gemini": ("Gemini", "Inspect the model catalog and your free project quota."),
    "groq": ("Groq", "Inspect available models and your organization’s free limits."),
    "openrouter": ("OpenRouter", "Check key access and zero-priced model availability."),
    "ollama": ("Local Ollama", "Check installed models on the Ubuntu inference host."),
    "ntfy": ("Private ntfy", "Check an authenticated account on your private server."),
    "whatsapp": (
        "WhatsApp",
        "Read-only pairing requires platform authorization and a chat allowlist.",
    ),
    "linkedin": (
        "LinkedIn alerts",
        "Use consented Gmail alerts. Feed access requires platform permission.",
    ),
}


def cards(stored: list[str], locked: bool) -> list[IntegrationCard]:
    output = []
    for code, (name, instruction) in PROVIDERS.items():
        if locked or code in {"whatsapp", "linkedin"}:
            state = ConnectionState.disabled
        elif code in stored:
            state = ConnectionState.authorization_required
            instruction = "A credential is stored. Verification is still required."
        else:
            state = ConnectionState.disconnected
        output.append(
            IntegrationCard(provider=code, label=name, state=state, instruction=instruction)
        )
    return output
