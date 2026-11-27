"""Month names of some languages in dates that are read by a simple rule.

For each spelling, lowercase, and each phrasing, e.g. ``plain`` for
"5 janvier 2020" or ``de`` for "5 de marzo de 2019", the locale that reads the
date and the number of the month, as found by running the parsers on dates of
that form. See :data:`flashdate.date._FOREIGN`.

The tests read a date of each entry with the parsers and compare, so a change
to the data of a language that changes one of them does not go unnoticed.
"""

_MONTH_WORDS_DATA = """
abr de=es4 dot=es4 g=es4 plain=es4
abril de=es4 dot=es4 g=es4 plain=es4
ago de=es8 dot=es8 g=es8 plain=es8
agosto de=es8 dot=es8 g=es8 plain=es8
aou dot=fr8 g=fr8 le=fr8 plain=fr8
aout dot=fr8 g=fr8 le=fr8 plain=fr8
aoû dot=fr8 g=fr8 le=fr8 plain=fr8
août dot=fr8 g=fr8 le=fr8 plain=fr8
apr de=ro4 dot=en4 g=en4 plain=en4
april dot=en4 g=en4 plain=en4
aprile dot=it4 g=it4 plain=it4
aug de=ro8 dot=en8 g=en8 plain=en8
august de=ro8 dot=en8 g=en8 plain=en8
avr dot=fr4 g=fr4 le=fr4 plain=fr4
avril dot=fr4 g=fr4 le=fr4 plain=fr4
dec de=ro12 dot=en12 g=en12 le=fr12 plain=en12
decembre dot=fr12 g=fr12 le=fr12 plain=fr12
dez de=pt12 dot=de12 g=de12 plain=de12
dezember dot=de12 g=de12 plain=de12
dezembro de=pt12 dot=pt12 g=pt12 plain=pt12
dic de=es12 dot=es12 g=es12 plain=es12
dicembre dot=it12 g=it12 plain=it12
diciembre de=es12 dot=es12 g=es12 plain=es12
déc de=ro12 dot=en12 g=en12 le=fr12 plain=en12
décembre dot=fr12 g=fr12 le=fr12 plain=fr12
ene de=es1 dot=es1 g=es1 plain=es1
enero de=es1 dot=es1 g=es1 plain=es1
feb de=es2 dot=en2 g=en2 plain=en2
febbraio dot=it2 g=it2 plain=it2
feber dot=de2 g=de2 plain=de2
febrero de=es2 dot=es2 g=es2 plain=es2
februar dot=de2 g=de2 plain=de2
fev de=pt2 dot=fr2 g=fr2 le=fr2 plain=fr2
fevereiro de=pt2 dot=pt2 g=pt2 plain=pt2
fevr dot=fr2 g=fr2 le=fr2 plain=fr2
fevrier dot=fr2 g=fr2 le=fr2 plain=fr2
fév de=pt2 dot=fr2 g=fr2 le=fr2 plain=fr2
févr dot=fr2 g=fr2 le=fr2 plain=fr2
février dot=fr2 g=fr2 le=fr2 plain=fr2
gen de=ca1 dot=it1 g=it1 plain=it1
gennaio dot=it1 g=it1 plain=it1
giu dot=it6 g=it6 plain=it6
giugno dot=it6 g=it6 plain=it6
jan de=pt1 dot=en1 g=en1 le=fr1 plain=en1
janeiro de=pt1 dot=pt1 g=pt1 plain=pt1
janner dot=de1 g=de1 plain=de1
januar dot=de1 g=de1 plain=de1
janv dot=fr1 g=fr1 le=fr1 plain=fr1
janvier dot=fr1 g=fr1 le=fr1 plain=fr1
juil dot=fr7 g=fr7 le=fr7 plain=fr7
juillet dot=fr7 g=fr7 le=fr7 plain=fr7
juin dot=fr6 g=fr6 le=fr6 plain=fr6
jul de=es7 dot=en7 g=en7 le=fr7 plain=en7
julho de=pt7 dot=pt7 g=pt7 plain=pt7
juli dot=de7 g=de7 plain=de7
julio de=es7 dot=es7 g=es7 plain=es7
jun de=es6 dot=en6 g=en6 le=fr6 plain=en6
junho de=pt6 dot=pt6 g=pt6 plain=pt6
juni dot=de6 g=de6 plain=de6
junio de=es6 dot=es6 g=es6 plain=es6
jänner dot=de1 g=de1 plain=de1
lug dot=it7 g=it7 plain=it7
luglio dot=it7 g=it7 plain=it7
mag dot=it5 g=it5 plain=it5
maggio dot=it5 g=it5 plain=it5
mai de=pt5 dot=fr5 g=fr5 le=fr5 plain=fr5
maio de=pt5 dot=pt5 g=pt5 plain=pt5
mar de=es3 dot=en3 g=en3 plain=en3
marco de=pt3 dot=pt3 g=pt3 plain=pt3
mars dot=fr3 g=fr3 le=fr3 plain=fr3
marz dot=de3 g=de3 plain=de3
marzo de=es3 dot=es3 g=es3 plain=es3
março de=pt3 dot=pt3 g=pt3 plain=pt3
may de=es5 dot=en5 g=en5 plain=en5
mayo de=es5 dot=es5 g=es5 plain=es5
mrz dot=de3 g=de3 plain=de3
mär de=es3 dot=en3 g=en3 plain=en3
märz dot=de3 g=de3 plain=de3
nov de=es11 dot=en11 g=en11 le=fr11 plain=en11
november dot=en11 g=en11 plain=en11
novembre de=ca11 dot=fr11 g=fr11 le=fr11 plain=fr11
novembro de=pt11 dot=pt11 g=pt11 plain=pt11
noviembre de=es11 dot=es11 g=es11 plain=es11
oct de=es10 dot=en10 g=en10 le=fr10 plain=en10
octobre dot=fr10 g=fr10 le=fr10 plain=fr10
octubre de=es10 dot=es10 g=es10 plain=es10
okt dot=de10 g=de10 plain=de10
oktober dot=de10 g=de10 plain=de10
ott dot=it10 g=it10 plain=it10
ottobre dot=it10 g=it10 plain=it10
out de=pt10 dot=pt10 g=pt10 plain=pt10
outubro de=pt10 dot=pt10 g=pt10 plain=pt10
sep de=es9 dot=en9 g=en9 le=fr9 plain=en9
sept de=es9 dot=en9 g=en9 le=fr9 plain=en9
september dot=en9 g=en9 plain=en9
septembre dot=fr9 g=fr9 le=fr9 plain=fr9
septembro de=pt9 dot=pt9 g=pt9 plain=pt9
septiembre de=es9 dot=es9 g=es9 plain=es9
set de=es9
setembro de=pt9 dot=pt9 g=pt9 plain=pt9
setiembre de=es9 dot=es9 g=es9 plain=es9
settembre dot=it9 g=it9 plain=it9
авг dot=ru8 g=ru8 plain=ru8
август dot=ru8 g=ru8 plain=ru8
августа dot=ru8 g=ru8 plain=ru8
апр dot=ru4 g=ru4 plain=ru4
апрель dot=ru4 g=ru4 plain=ru4
апреля dot=ru4 g=ru4 plain=ru4
дек dot=ru12 g=ru12 plain=ru12
декабрь dot=ru12 g=ru12 plain=ru12
декабря dot=ru12 g=ru12 plain=ru12
июл dot=ru7 g=ru7 plain=ru7
июль dot=ru7 g=ru7 plain=ru7
июля dot=ru7 g=ru7 plain=ru7
июн dot=ru6 g=ru6 plain=ru6
июнь dot=ru6 g=ru6 plain=ru6
июня dot=ru6 g=ru6 plain=ru6
маи dot=ru5 g=ru5 plain=ru5
май dot=ru5 g=ru5 plain=ru5
мар dot=ru3 g=ru3 plain=ru3
март dot=ru3 g=ru3 plain=ru3
марта dot=ru3 g=ru3 plain=ru3
мая dot=ru5 g=ru5 plain=ru5
ноя dot=ru11 g=ru11 plain=ru11
нояб dot=ru11 g=ru11 plain=ru11
ноябрь dot=ru11 g=ru11 plain=ru11
ноября dot=ru11 g=ru11 plain=ru11
окт dot=ru10 g=ru10 plain=ru10
октябрь dot=ru10 g=ru10 plain=ru10
октября dot=ru10 g=ru10 plain=ru10
сен dot=ru9 g=ru9 plain=ru9
сент dot=ru9 g=ru9 plain=ru9
сентябрь dot=ru9 g=ru9 plain=ru9
сентября dot=ru9 g=ru9 plain=ru9
фев dot=ru2 g=ru2 plain=ru2
февр dot=ru2 g=ru2 plain=ru2
февраль dot=ru2 g=ru2 plain=ru2
февраля dot=ru2 g=ru2 plain=ru2
янв dot=ru1 g=ru1 plain=ru1
январь dot=ru1 g=ru1 plain=ru1
января dot=ru1 g=ru1 plain=ru1
"""


def _load() -> dict[str, dict[str, tuple[str, int]]]:
    words: dict[str, dict[str, tuple[str, int]]] = {}
    for line in _MONTH_WORDS_DATA.split("\n"):
        if not line:
            continue
        word, *phrasings = line.split(" ")
        for phrasing in phrasings:
            key, _, value = phrasing.partition("=")
            locale = value.rstrip("0123456789")
            words.setdefault(word, {})[key] = (locale, int(value[len(locale) :]))
    return words


MONTH_WORDS = _load()
