"""Mise en forme des salaires, partagée par veille.py et tableau.py."""

# Ce qui suit « k » dans « 60 à 100 k€ ». Une devise absente s'écrit avec son code (« kSEK »).
SYMBOLES = {"EUR": "€", "USD": "$", "GBP": "£", "CAD": "CA$", "CHF": " CHF"}


def fourchette(mini, maxi, devise="EUR"):
    """Texte lisible d'une fourchette annuelle : « 60 à 100 k€ »."""
    if not maxi:
        return ""
    symbole = SYMBOLES.get(devise, devise)
    if mini and mini != maxi:
        return f"{round(mini / 1000)} à {round(maxi / 1000)} k{symbole}"
    return f"{round(maxi / 1000)} k{symbole}"
