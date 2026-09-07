"""Fictional source and expected data used by every public demonstration."""

from __future__ import annotations

from aitran.artifacts import sha256_text
from aitran.speech_pronunciation import Pronunciation


SOURCE_BOOK = """## Chapter 1

Mira opened the observatory before sunrise. The old lens still pointed north.

“The signal returned,” Mira said. “It is weaker, but it is ours.”

Tomas checked the paper log. “Then we have one night to answer.”

## Chapter 2

Rain crossed the glass roof while the mechanism turned for the first time in years.

“Keep the lamp steady,” Mira whispered.

At midnight, a pale line appeared above the sea, and the observatory sent its reply.
"""

TRANSLATED_BY_ID = {
    "P000001": "## Глава 1",
    "P000002": "Мира открыла обсерваторию ещё до рассвета. Старый объектив по-прежнему смотрел на север.",
    "P000003": "— Сигнал вернулся, — сказала Мира. — Он стал слабее, но это наш сигнал.",
    "P000004": "Томас сверился с бумажным журналом. — Значит, у нас одна ночь, чтобы ответить.",
    "P000005": "## Глава 2",
    "P000006": "Дождь барабанил по стеклянной крыше, пока механизм впервые за долгие годы приходил в движение.",
    "P000007": "— Держи лампу ровно, — прошептала Мира.",
    "P000008": "В полночь над морем появилась бледная полоса, и обсерватория отправила ответ.",
}

ROLE_BY_ID = {
    "P000001": "narrator",
    "P000002": "narrator",
    "P000003": "female_dialogue",
    "P000004": "male_dialogue",
    "P000005": "narrator",
    "P000006": "narrator",
    "P000007": "female_dialogue",
    "P000008": "narrator",
}

PRONUNCIATIONS = (
    Pronunciation(written="Мира", stressed="М+ира"),
    Pronunciation(written="Томас", stressed="Т+омас"),
)

SOURCE_SHA256 = sha256_text(SOURCE_BOOK)
FIXTURE_ID = "last-light-v1"
