"""
Kredit Kalkulyator Moduli
=========================
Annuitet va Differentsial kredit hisoblash.
To'liq oylik to'lov jadvali generatsiya qilish.
Imtiyozli davr qo'llab-quvvatlash.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class KreditTolov:
    """Bitta oylik to'lov ma'lumotlari"""
    oy: int
    oylik_tolov: float
    asosiy_qarz: float
    foiz_tolov: float
    qoldiq: float
    imtiyozli: bool = False


@dataclass 
class KreditNatija:
    """To'liq kredit hisoblash natijasi"""
    turi: str  # "annuitet" yoki "differentsial"
    kredit_summa: float
    foiz_stavka: float
    muddat_oy: int
    imtiyoz_oy: int
    oylik_tolov: float  # O'rtacha yoki annuitet oylik
    jami_tolov: float
    jami_foiz: float
    jadval: List[KreditTolov] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "turi": self.turi,
            "kredit_summa": self.kredit_summa,
            "foiz_stavka": self.foiz_stavka,
            "muddat_oy": self.muddat_oy,
            "imtiyoz_oy": self.imtiyoz_oy,
            "oylik_tolov": round(self.oylik_tolov, 2),
            "jami_tolov": round(self.jami_tolov, 2),
            "jami_foiz": round(self.jami_foiz, 2),
            "jadval": [
                {
                    "oy": t.oy,
                    "oylik_tolov": round(t.oylik_tolov, 2),
                    "asosiy_qarz": round(t.asosiy_qarz, 2),
                    "foiz_tolov": round(t.foiz_tolov, 2),
                    "qoldiq": round(t.qoldiq, 2),
                    "imtiyozli": t.imtiyozli
                }
                for t in self.jadval
            ]
        }


def annuitet_hisob(summa: float, yillik_foiz: float, muddat_oy: int, 
                    imtiyoz_oy: int = 0) -> KreditNatija:
    """
    Annuitet kredit hisoblash.
    Imtiyozli davrda faqat foiz to'lanadi.
    Asosiy davrda annuitet formula bo'yicha to'lanadi.
    """
    if summa <= 0 or muddat_oy <= 0:
        return KreditNatija("annuitet", 0, 0, 0, 0, 0, 0, 0)

    imtiyoz_oy = min(max(imtiyoz_oy, 0), muddat_oy)
    asosiy_muddat = muddat_oy - imtiyoz_oy
    r = yillik_foiz / 12 / 100 if yillik_foiz > 0 else 0

    jadval: List[KreditTolov] = []
    qoldiq = summa
    jami_tolov = 0
    jami_foiz = 0

    # Annuitet oylik to'lov (asosiy davr uchun)
    if r > 0 and asosiy_muddat > 0:
        annuitet = summa * (r * (1 + r)**asosiy_muddat) / ((1 + r)**asosiy_muddat - 1)
    elif asosiy_muddat > 0:
        annuitet = summa / asosiy_muddat
    else:
        annuitet = 0

    # 1. Imtiyozli davr — faqat foiz to'lash
    for oy in range(1, imtiyoz_oy + 1):
        foiz_t = qoldiq * r
        tolov = KreditTolov(
            oy=oy, oylik_tolov=round(foiz_t, 2),
            asosiy_qarz=0, foiz_tolov=round(foiz_t, 2),
            qoldiq=round(qoldiq, 2), imtiyozli=True
        )
        jadval.append(tolov)
        jami_tolov += foiz_t
        jami_foiz += foiz_t

    # 2. Asosiy davr — annuitet to'lov
    for oy in range(imtiyoz_oy + 1, muddat_oy + 1):
        foiz_t = qoldiq * r
        asosiy_t = annuitet - foiz_t
        qoldiq -= asosiy_t

        if qoldiq < 0.01:
            qoldiq = 0

        tolov = KreditTolov(
            oy=oy, oylik_tolov=round(annuitet, 2),
            asosiy_qarz=round(asosiy_t, 2), foiz_tolov=round(foiz_t, 2),
            qoldiq=round(qoldiq, 2), imtiyozli=False
        )
        jadval.append(tolov)
        jami_tolov += annuitet
        jami_foiz += foiz_t

    return KreditNatija(
        turi="annuitet", kredit_summa=summa, foiz_stavka=yillik_foiz,
        muddat_oy=muddat_oy, imtiyoz_oy=imtiyoz_oy,
        oylik_tolov=annuitet, jami_tolov=jami_tolov,
        jami_foiz=jami_foiz, jadval=jadval
    )


def differentsial_hisob(summa: float, yillik_foiz: float, muddat_oy: int,
                         imtiyoz_oy: int = 0) -> KreditNatija:
    """
    Differentsial kredit hisoblash.
    Asosiy qarz teng bo'linadi, foiz qoldiqdan hisoblanadi.
    Imtiyozli davrda faqat foiz to'lanadi.
    """
    if summa <= 0 or muddat_oy <= 0:
        return KreditNatija("differentsial", 0, 0, 0, 0, 0, 0, 0)

    imtiyoz_oy = min(max(imtiyoz_oy, 0), muddat_oy)
    asosiy_muddat = muddat_oy - imtiyoz_oy
    r = yillik_foiz / 12 / 100 if yillik_foiz > 0 else 0

    # Asosiy qarz bo'lagi (har oy teng)
    asosiy_bolag = summa / asosiy_muddat if asosiy_muddat > 0 else 0

    jadval: List[KreditTolov] = []
    qoldiq = summa
    jami_tolov = 0
    jami_foiz = 0

    # 1. Imtiyozli davr
    for oy in range(1, imtiyoz_oy + 1):
        foiz_t = qoldiq * r
        tolov = KreditTolov(
            oy=oy, oylik_tolov=round(foiz_t, 2),
            asosiy_qarz=0, foiz_tolov=round(foiz_t, 2),
            qoldiq=round(qoldiq, 2), imtiyozli=True
        )
        jadval.append(tolov)
        jami_tolov += foiz_t
        jami_foiz += foiz_t

    # 2. Asosiy davr — differentsial
    for oy in range(imtiyoz_oy + 1, muddat_oy + 1):
        foiz_t = qoldiq * r
        oylik = asosiy_bolag + foiz_t
        qoldiq -= asosiy_bolag

        if qoldiq < 0.01:
            qoldiq = 0

        tolov = KreditTolov(
            oy=oy, oylik_tolov=round(oylik, 2),
            asosiy_qarz=round(asosiy_bolag, 2), foiz_tolov=round(foiz_t, 2),
            qoldiq=round(qoldiq, 2), imtiyozli=False
        )
        jadval.append(tolov)
        jami_tolov += oylik
        jami_foiz += foiz_t

    # O'rtacha oylik to'lov
    ortacha = jami_tolov / muddat_oy if muddat_oy > 0 else 0

    return KreditNatija(
        turi="differentsial", kredit_summa=summa, foiz_stavka=yillik_foiz,
        muddat_oy=muddat_oy, imtiyoz_oy=imtiyoz_oy,
        oylik_tolov=ortacha, jami_tolov=jami_tolov,
        jami_foiz=jami_foiz, jadval=jadval
    )


def hisob_kredit(summa: float, yillik_foiz: float, muddat_oy: int,
                  imtiyoz_oy: int = 0, turi: str = "annuitet") -> KreditNatija:
    """Umumiy kredit hisoblash funksiyasi"""
    if turi == "differentsial":
        return differentsial_hisob(summa, yillik_foiz, muddat_oy, imtiyoz_oy)
    return annuitet_hisob(summa, yillik_foiz, muddat_oy, imtiyoz_oy)
