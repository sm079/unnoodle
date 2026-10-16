"""A first layer of safety: prompts with banned words are refused before they are queued.

Words are compared after evening out the simple ways around a list: case, accents, digits and symbols standing in for
letters (nud3, s3x, $ex), letters held down (nuuude) and letters spaced out (n u d e). An entry of several words matches
them in a row, and a word matches its plural too. This is only a first layer: misspellings, other languages and what
is in an uploaded photo get past it. The rest is that generating takes credits, which admins hand out, and that admins
can see and delete anything. A new install starts with a short list (the banned_words migration).
"""

import re
import unicodedata
from collections.abc import Iterable

# Stand-ins for letters, as typed to get past a word list
LOOKALIKES = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
DIGITS = str.maketrans({k: v for k, v in LOOKALIKES.items() if chr(k).isdigit()})
# A symbol stands in for a letter only next to one, so "nsfw!!" is still nsfw
SYMBOLS = re.compile(r"(?<=\w)[@$!]+(?=\w)|(?<![\w@$!])[@$!](?=\w)")
TOKEN = re.compile(r"[^\W_]+")
REPEATS = re.compile(r"(.)\1+")


def tokens(text: str) -> list[str]:
    """The words of a text, evened out for comparing."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    plain = SYMBOLS.sub(lambda symbol: symbol.group().translate(LOOKALIKES), plain.casefold())
    words = TOKEN.findall(plain.translate(DIGITS))
    # Letters spaced out are read as the word they spell
    joined: list[str] = []
    spelling = False
    for word in words:
        if len(word) == 1 and spelling:
            joined[-1] += word
        else:
            joined.append(word)
        spelling = len(word) == 1
    return [REPEATS.sub(r"\1", word) for word in joined]


def banned_in(prompt: str, banned: Iterable[str]) -> str | None:
    """The first banned word or phrase the prompt contains, as the list has it, or None."""
    words = tokens(prompt)
    for entry in banned:
        wanted = tokens(entry)
        if wanted and any(matches(words[i : i + len(wanted)], wanted) for i in range(len(words) - len(wanted) + 1)):
            return entry
    return None


def matches(words: list[str], wanted: list[str]) -> bool:
    # The last word may be a plural: "nudes" for "nude"
    *start, last = wanted
    return words[:-1] == start and words[-1] in (last, last + "s", last + "es")
