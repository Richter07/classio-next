import phonenumbers


class InvalidPhone(ValueError):
    pass


def normalize_phone(raw: str, region: str = "BJ") -> str:
    """Renvoie le numéro au format E.164, ou lève InvalidPhone.

    Depuis fin 2024, les numéros mobiles béninois comptent 10 chiffres et commencent par 01.
    Les fichiers d'écoles contiennent encore l'ancien format à 8 chiffres : on le convertit.
    """
    text = str(raw).strip()
    digits = "".join(c for c in text if c.isdigit())
    if region == "BJ":
        if len(digits) == 8:
            text = f"01{digits}"
        elif len(digits) == 11 and digits.startswith("229"):
            text = f"+22901{digits[3:]}"
    try:
        parsed = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhone(str(raw)) from exc
    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhone(str(raw))
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
