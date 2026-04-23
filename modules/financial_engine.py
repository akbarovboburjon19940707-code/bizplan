"""
Moliyaviy Dvigatel (Financial Engine) — Enterprise Edition
===========================================================
Excel modelini 100% Python da qayta yaratilgan versiyasi.
Barcha 12+ jadval (ProjCost, FinPlan, ShareOfCosts, Depreciation,
Labour, ProdPlan, Loans, Taxes, CostSold, ProfLoss, CashFlow, NPV)
to'liq hisob-kitob qilinadi.

Soliq turlari: YTT (yagona soliq) va MCHJ (QQS + foyda solig'i).
Kredit turlari: Annuitet va Differentsial.
"""
from typing import List, Dict, Any, Optional
import math
from .credit_calculator import hisob_kredit, KreditNatija
from .business_categories import FAOLIYAT_TURLARI, get_cost_structure, get_faoliyat_turi


# ── Yordamchi ────────────────────────────────────────────
def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        # Tozalash: vergulni nuqtaga, barcha turdagi probellarni bo'shliqqa
        clean_val = str(value).replace(",", ".").replace(" ", "").replace("\u00A0", "").replace("\u202F", "")
        return float(clean_val)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        clean_val = str(value).replace(",", ".").replace(" ", "").replace("\u00A0", "").replace("\u202F", "")
        return int(float(clean_val))
    except (ValueError, TypeError):
        return default


def fmt_num(n: float) -> str:
    """Raqamni o'zbek formatda chiqarish: 1 234 567"""
    if n is None:
        return "0"
    return f"{n:,.0f}".replace(",", " ")


# ── NPV / IRR ───────────────────────────────────────────
def calculate_npv(discount_rate_pct: float, cash_flows: List[float]) -> float:
    r = discount_rate_pct / 100.0
    if r <= -1:
        return 0.0
    return sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows))


def calculate_irr(cash_flows: List[float], max_iter: int = 1000) -> Optional[float]:
    if not cash_flows or len(cash_flows) < 2:
        return None
        
    has_positive = any(cf > 0 for cf in cash_flows)
    has_negative = any(cf < 0 for cf in cash_flows)
    if not (has_positive and has_negative):
        return 0.0

    guess = 0.1
    for _ in range(max_iter):
        npv_val = sum(cf / ((1 + guess) ** t) for t, cf in enumerate(cash_flows))
        dnpv = sum(-t * cf / ((1 + guess) ** (t + 1)) for t, cf in enumerate(cash_flows) if t > 0)
        if abs(dnpv) < 1e-12:
            break
        new_guess = guess - npv_val / dnpv
        if abs(new_guess - guess) < 1e-7:
            return round(new_guess * 100, 2)
        guess = new_guess
    low, high = -0.99, 10.0
    for _ in range(max_iter):
        mid = (low + high) / 2
        npv_val = sum(cf / ((1 + mid) ** t) for t, cf in enumerate(cash_flows))
        if abs(npv_val) < 1e-6:
            return round(mid * 100, 2)
        if npv_val > 0:
            low = mid
        else:
            high = mid
    return round(((low + high) / 2) * 100, 2)


# ══════════════════════════════════════════════════════════
#  FINANCIAL ENGINE
# ══════════════════════════════════════════════════════════
class FinancialEngine:
    """
    Barcha moliyaviy hisob-kitoblarni bajaradi.
    Excel fayl strukturasini to'liq takrorlaydi.
    """

    def __init__(self, params: Dict[str, Any]):
        self._parse_inputs(params)
        self._calculate_all()

    # ── Input Parsing ────────────────────────────────────
    def _parse_inputs(self, p: Dict[str, Any]):
        # Loyiha ma'lumotlari
        self.loyiha_nomi = str(p.get("loyiha_nomi", ""))
        self.tashabbuskor = str(p.get("tashabbuskor", ""))
        self.manzil = str(p.get("manzil", ""))
        self.bank = str(p.get("bank", ""))
        self.stir = str(p.get("stir", ""))
        self.jshshir = str(p.get("jshshir", ""))
        self.faoliyat = str(p.get("faoliyat_turi_text", p.get("faoliyat", "")))
        self.mulk = str(p.get("mulk", ""))
        self.fio = str(p.get("fio", ""))
        self.pasport = str(p.get("pasport", ""))
        self.berilgan_vaqti = str(p.get("berilgan_vaqti", ""))

        # ═══ FAOLIYAT TURI (4 ta asosiy yo'nalish) ═══
        self.faoliyat_turi = str(p.get("faoliyat_turi", ""))
        if not self.faoliyat_turi or self.faoliyat_turi not in FAOLIYAT_TURLARI:
            # loyiha nomidan aniqlashga harakat
            self.faoliyat_turi = get_faoliyat_turi(self.loyiha_nomi)
        self.cost_structure = get_cost_structure(self.faoliyat_turi)

        # Moliyaviy
        self.loyiha_qiymati = safe_float(p.get("loyiha_qiymati"))
        self.oz_mablag = safe_float(p.get("oz_mablag"))
        self.kredit_summa = safe_float(p.get("kredit"))
        self.foiz = safe_float(p.get("foiz"), 14.0)
        self.muddat_oy = safe_int(p.get("muddat"), 84)
        self.imtiyoz_oy = safe_int(p.get("imtiyoz"), 0)
        self.kredit_turi = str(p.get("kredit_turi", "annuitet"))
        self.soliq_turi = str(p.get("soliq_turi", "ytt"))
        self.discount_rate = safe_float(p.get("discount_rate"), 13.5)

        # Mahsulot
        self.mahsulot = str(p.get("mahsulot", ""))
        self.hajm = safe_float(p.get("hajm"))
        self.narx = safe_float(p.get("narx"))
        self.olchov = str(p.get("olchov", "dona"))

        # ═══ Faoliyat turiga qarab qo'shimcha fieldlar ═══
        self.xomashyo_narx = safe_float(p.get("xomashyo_narx"))
        self.uskuna_qiymati = safe_float(p.get("uskuna_qiymati"))
        self.energiya_oylik = safe_float(p.get("energiya_oylik"))
        self.urug_yem_narx = safe_float(p.get("urug_yem_narx"))
        self.texnika_xarajat = safe_float(p.get("texnika_xarajat"))
        self.yer_ijarasi = safe_float(p.get("yer_ijarasi"))
        self.tovar_xaridi = safe_float(p.get("tovar_xaridi"))
        self.dokon_ijarasi = safe_float(p.get("dokon_ijarasi"))
        self.transport_xarajat = safe_float(p.get("transport_xarajat"))
        self.uskuna_ijarasi = safe_float(p.get("uskuna_ijarasi"))
        self.joy_ijarasi = safe_float(p.get("joy_ijarasi"))
        self.kommunal_oylik_input = safe_float(p.get("kommunal_oylik"))

        # Xodimlar
        self.direktor_soni = max(safe_int(p.get("direktor"), 1), 1)
        self.xodim_soni = safe_int(p.get("xodim"))
        self.yangi_xodim_soni = safe_int(p.get("yangi_xodim"))
        self.rahbar_oylik = safe_float(p.get("rahbar_oylik"))
        self.ishchi_oylik = safe_float(p.get("ishchi_oylik"))
        self.yangi_ishchi_oylik = safe_float(p.get("yangi_ishchi_oylik"))

        # Kommunal
        self.elektr = safe_float(p.get("elektr"))
        self.gaz = safe_float(p.get("gaz"))
        self.suv = safe_float(p.get("suv"))
        self.oqava = safe_float(p.get("oqava"))

        # Derived
        self.muddat_yil = max(math.ceil(self.muddat_oy / 12), 1)
        self.imtiyoz_yil = max(math.ceil(self.imtiyoz_oy / 12), 0)
        self.asosiy_vositalar = self.kredit_summa + self.oz_mablag
        if self.asosiy_vositalar <= 0:
            self.asosiy_vositalar = self.loyiha_qiymati

        # Dynamically size the model years
        self.MODEL_YEARS = min(max(self.muddat_yil, 1), 7)
        self.YEAR_LABELS = [f"{i}-yil" for i in range(1, self.MODEL_YEARS + 1)]
        self.CAPACITIES = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00][:self.MODEL_YEARS]
        self.CAPACITIES_STR = [f"{int(c * 100)}%" for c in self.CAPACITIES]

        # Raw params for context
        self._raw = p

    # ── Master Calculate ─────────────────────────────────
    def _calculate_all(self):
        self.t_proj_cost = self._calc_proj_cost()
        self.t_share_costs = self._calc_share_of_costs()
        self.t_fin_plan = self._calc_fin_plan()
        self.t_depreciation = self._calc_depreciation()
        self.t_labour = self._calc_labour()
        self.t_kommunal = self._calc_kommunal()
        self.t_prod_summary = self._calc_prod_summary()
        self.t_prod_plan = self._calc_prod_plan()
        self.t_loans = self._calc_loans()
        self.t_taxes = self._calc_taxes()
        self.t_cost_sold = self._calc_cost_sold()
        self.t_cost_total = self._calc_cost_total()
        self.t_prof_loss = self._calc_prof_loss()
        self.t_cash_flow = self._calc_cash_flow()
        self.t_npv = self._calc_npv()

    # ─────────────────────────────────────────────────────
    # 1. PROJ COST (1-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_proj_cost(self) -> Dict:
        kredit = self.kredit_summa
        oz = self.oz_mablag
        jami = self.loyiha_qiymati if self.loyiha_qiymati > 0 else kredit + oz
        aylanma = max(jami - kredit - oz, 0)

        rows = [
            ["Asosiy vositalarni sotib olish (jihozlar)", 0, kredit, kredit],
            ["Asosiy vositalar (o'z mablag')", oz, 0, oz],
            ["JAMI asosiy mablag'lar", oz, kredit, oz + kredit],
            ["Aylanma kapital", aylanma, 0, aylanma],
            ["LOYIHA QIYMATI", oz + aylanma, kredit, jami],
        ]
        return {
            "title": "LOYIHA QIYMATI",
            "ilova": "1-ILOVA",
            "headers": ["Ko'rsatkich", "O'z mablag' (so'm)", "Bank krediti (so'm)", "Jami (so'm)"],
            "rows": rows,
            "data": {"jami": jami, "kredit": kredit, "oz": oz, "aylanma": aylanma},
        }

    # ─────────────────────────────────────────────────────
    # 2. SHARE OF COSTS (3-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_share_of_costs(self) -> Dict:
        kredit = self.kredit_summa
        oz = self.oz_mablag
        jami = self.loyiha_qiymati if self.loyiha_qiymati > 0 else kredit + oz

        rows = [
            ["Asosiy vositalar (o'z mablag')", oz, 0, oz],
            ["Asosiy vositalar (kredit)", 0, kredit, kredit],
            ["Sug'urta xarajatlari", 0, 0, 0],
            ["Boshqa xarajatlar", 0, 0, 0],
            ["Aylanma kapital", max(jami - oz - kredit, 0), 0, max(jami - oz - kredit, 0)],
            ["JAMI ASOSIY KAPITAL", oz + max(jami - oz - kredit, 0), kredit, jami],
        ]
        return {
            "title": "Loyiha ishtirokchilari hissasi",
            "ilova": "3-ILOVA",
            "headers": ["Ko'rsatkich", "O'z mablag' (so'm)", "Kredit (so'm)", "Jami (so'm)"],
            "rows": rows,
            "data": {"asosiy_vositalar": oz + kredit},
        }

    # ─────────────────────────────────────────────────────
    # 3. FIN PLAN (2-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_fin_plan(self) -> Dict:
        kredit = self.kredit_summa
        oz = self.oz_mablag
        jami = self.loyiha_qiymati if self.loyiha_qiymati > 0 else kredit + oz
        oz_pct = (oz / jami * 100) if jami > 0 else 0
        kredit_pct = (kredit / jami * 100) if jami > 0 else 0

        rows = [
            ["O'z mablag'lari", oz, f"{oz_pct:.1f}%"],
            ["Bank krediti", kredit, f"{kredit_pct:.1f}%"],
            ["JAMI moliyalashtirish", jami, "100%"],
        ]
        return {
            "title": "Moliyalashtirish rejasi",
            "ilova": "2-ILOVA",
            "headers": ["Manba", "Summa (so'm)", "Ulush"],
            "rows": rows,
            "data": {"jami": jami},
        }

    # ─────────────────────────────────────────────────────
    # 4. DEPRECIATION (4-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_depreciation(self) -> Dict:
        asset_value = self.asosiy_vositalar
        # Faoliyat turiga qarab amortizatsiya stavkasi
        dep_rate = self.cost_structure.get("amortizatsiya_stavka", 0.15)
        is_majburiy = self.cost_structure.get("amortizatsiya_majburiy", True)

        if is_majburiy or asset_value > 0:
            yearly_dep = asset_value * dep_rate
        else:
            yearly_dep = 0

        yearly = []
        for y in range(self.MODEL_YEARS):
            remaining = asset_value - sum(yearly)
            dep_this_year = min(yearly_dep, remaining) if remaining > 0 else 0
            yearly.append(dep_this_year)

        acc_list = []
        acc = 0
        for d in yearly:
            acc += d
            acc_list.append(acc)

        stavka_str = f"{dep_rate*100:.0f}%"
        rows = [
            ["Asosiy vositalar", asset_value, stavka_str] + yearly,
            ["Jami amortizatsiya", "", ""] + yearly,
            ["Yig'ilgan amortizatsiya", "", ""] + acc_list,
        ]
        return {
            "title": "AMORTIZATSIYA HISOB-KITOBI",
            "ilova": "4-ILOVA",
            "headers": ["Ko'rsatkich", "Qiymat (so'm)", "Stavka"] + self.YEAR_LABELS,
            "rows": rows,
            "data": {"yearly": yearly[0] if yearly else 0, "yearly_list": yearly, "accumulated": acc_list},
        }

    # ─────────────────────────────────────────────────────
    # 5. LABOUR (5-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_labour(self) -> Dict:
        dir_oylik = self.direktor_soni * self.rahbar_oylik
        dir_yillik = dir_oylik * 12
        ish_oylik = self.xodim_soni * self.ishchi_oylik
        ish_yillik = ish_oylik * 12
        yangi_oylik = self.yangi_xodim_soni * self.yangi_ishchi_oylik
        yangi_yillik = yangi_oylik * 12

        jami_oylik = dir_oylik + ish_oylik + yangi_oylik
        jami_yillik = jami_oylik * 12
        ijtimoiy = jami_yillik * 0.12
        jami_xarajat = jami_yillik + ijtimoiy

        admin_yillik = dir_yillik
        ishlab_chiq_yillik = ish_yillik + yangi_yillik
        admin_ijtimoiy = admin_yillik * 0.12
        ishlab_ijtimoiy = ishlab_chiq_yillik * 0.12

        rows = [
            ["Rahbariyat", "", "", "", ""],
            ["Direktor", self.direktor_soni, self.rahbar_oylik, dir_oylik, dir_yillik],
            ["Jami rahbariyat", self.direktor_soni, "", dir_oylik, dir_yillik],
            ["Ijtimoiy soliq (12%)", "", "12%", "", admin_ijtimoiy],
            ["JAMI rahbariyat", "", "", "", dir_yillik + admin_ijtimoiy],
            ["", "", "", "", ""],
            ["Ishlab chiqarish xodimlari", "", "", "", ""],
            ["Ishchilar", self.xodim_soni, self.ishchi_oylik, ish_oylik, ish_yillik],
            ["Xizmat ko'rsatuvchilar", self.yangi_xodim_soni, self.yangi_ishchi_oylik, yangi_oylik, yangi_yillik],
            ["Jami ishlab chiqarish", self.xodim_soni + self.yangi_xodim_soni, "", ish_oylik + yangi_oylik, ishlab_chiq_yillik],
            ["Ijtimoiy soliq (12%)", "", "12%", "", ishlab_ijtimoiy],
            ["JAMI ishlab chiqarish", "", "", "", ishlab_chiq_yillik + ishlab_ijtimoiy],
            ["", "", "", "", ""],
            ["JAMI ISH HAQI FONDI", self.direktor_soni + self.xodim_soni + self.yangi_xodim_soni, "", jami_oylik, jami_yillik],
            ["Ijtimoiy soliq (12%)", "", "12%", "", ijtimoiy],
            ["YALPI JAMI", "", "", "", jami_xarajat],
        ]
        return {
            "title": "ISH HAQI XARAJATLARI",
            "ilova": "5-ILOVA",
            "headers": ["Lavozim", "Soni", "Oylik maosh", "Oylik jami", "Yillik jami"],
            "rows": rows,
            "data": {
                "admin_yillik": dir_yillik,
                "admin_ijtimoiy": admin_ijtimoiy,
                "admin_jami": dir_yillik + admin_ijtimoiy,
                "ishlab_yillik": ishlab_chiq_yillik,
                "ishlab_ijtimoiy": ishlab_ijtimoiy,
                "ishlab_jami": ishlab_chiq_yillik + ishlab_ijtimoiy,
                "jami_fond": jami_yillik,
                "ijtimoiy": ijtimoiy,
                "jami_xarajat": jami_xarajat,
            },
        }

    # ─────────────────────────────────────────────────────
    # 6. PROD PLAN (6-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_prod_plan(self) -> Dict:
        max_hajm = self.hajm
        narx = self.narx
        max_revenue = max_hajm * narx

        yearly_hajm = []
        yearly_revenue = []
        for i in range(self.MODEL_YEARS):
            cap = self.CAPACITIES[i]
            vol = max_hajm * cap
            rev = vol * narx
            yearly_hajm.append(vol)
            yearly_revenue.append(rev)

        # Yangi 4 ta ustunli gorizontal format
        headers = ["Mahsulot nomi (xizmat turi)", "Ishlab chiqarish hajmi", "Sotish narxi", "Tushgan daromad (jami)"]
        
        mahsulot_str = self.mahsulot.strip() if self.mahsulot else ""
        prefix = f"{mahsulot_str} — " if mahsulot_str else ""
        
        rows = [
            [f"{prefix}MAKSIMAL QUVVAT (100%)", max_hajm, narx, max_revenue],
        ]
        
        for i in range(self.MODEL_YEARS):
            rows.append([
                f"{prefix}{i+1}-yil reja ({int(self.CAPACITIES[i]*100)}%)",
                yearly_hajm[i],
                narx,
                yearly_revenue[i]
            ])

        title_text = f"{mahsulot_str.upper()} — XIZMAT KO'RSATISH VA SOTISH REJASI" if mahsulot_str else "XIZMAT KO'RSATISH VA SOTISH REJASI"

        return {
            "title": title_text,
            "ilova": "6-ILOVA",
            "headers": headers,
            "rows": rows,
            "key": "prod_plan",
            "data": {
                "max_hajm": max_hajm,
                "narx": narx,
                "yearly_hajm": yearly_hajm,
                "yearly_revenue": yearly_revenue,
            },
        }

    def _calc_prod_summary(self) -> Dict:
        """6-ILOVA uchun asosiy ma'lumotlar jadvali (tepasi uchun)."""
        headers = [
            "Ishlab chiqariladigan mahsulot nomi",
            "Yillik ishlab chiqarish hajmi",
            "O'lchov birligi",
            "Bitta mahsulotning sotish narxi",
            "1 yillik savdo tushumi"
        ]
        
        jami_tushum = self.hajm * self.narx
        
        rows = [
            [self.mahsulot, self.hajm, self.olchov, self.narx, jami_tushum]
        ]
        
        mahsulot_str = self.mahsulot.strip() if self.mahsulot else ""
        title_text = f"{mahsulot_str.upper()} — XIZMAT KO'RSATISH VA SOTISH REJASI" if mahsulot_str else "XIZMAT KO'RSATISH VA SOTISH REJASI"

        return {
            "title": title_text,
            "ilova": "6-ILOVA",
            "key": "prod_summary",
            "headers": headers,
            "rows": rows,
            "data": {},
        }

    # ─────────────────────────────────────────────────────
    # 7. LOANS (8-9-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_loans(self) -> Dict:
        self.kredit_natija = hisob_kredit(
            self.kredit_summa,
            self.foiz,
            self.muddat_oy,
            self.imtiyoz_oy,
            self.kredit_turi,
        )

        # Yillik aggregatsiya
        yillik = []
        for y in range(1, self.MODEL_YEARS + 1):
            start_m = (y - 1) * 12 + 1
            end_m = y * 12
            asosiy = sum(t.asosiy_qarz for t in self.kredit_natija.jadval if start_m <= t.oy <= end_m)
            foiz_t = sum(t.foiz_tolov for t in self.kredit_natija.jadval if start_m <= t.oy <= end_m)
            qoldiq_list = [t.qoldiq for t in self.kredit_natija.jadval if start_m <= t.oy <= end_m]
            qoldiq = qoldiq_list[-1] if qoldiq_list else 0

            yillik.append({
                "yil": y,
                "asosiy_qarz": asosiy,
                "foiz_tolov": foiz_t,
                "jami_tolov": asosiy + foiz_t,
                "qoldiq": qoldiq,
            })
        self.yillik_kredit = yillik

        rows_monthly = []
        for t in self.kredit_natija.jadval:
            if t.oy <= self.MODEL_YEARS * 12:
                rows_monthly.append([
                    f"{t.oy}-oy",
                    t.asosiy_qarz,
                    t.foiz_tolov,
                    t.oylik_tolov,
                    t.qoldiq,
                ])
        
        # Yillik jamlarni qo'shish
        rows_monthly.append(["", "", "", "", ""])
        rows_monthly.append(["YILLIK TO'LOVLAR", "", "", "", ""])
        for yk in yillik:
            rows_monthly.append([
                f"{yk['yil']}-yil jami",
                yk["asosiy_qarz"],
                yk["foiz_tolov"],
                yk["jami_tolov"],
                yk["qoldiq"],
            ])

        rows_monthly.append([
            "UMUMIY JAMI",
            sum(yk["asosiy_qarz"] for yk in yillik),
            sum(yk["foiz_tolov"] for yk in yillik),
            sum(yk["jami_tolov"] for yk in yillik),
            0,
        ])

        return {
            "title": "KREDIT TO'LOV JADVALI (Oyma-oy)",
            "ilova": "8-9-ILOVA",
            "headers": ["Davr", "Asosiy qarz (so'm)", "Foiz to'lov (so'm)", "Jami to'lov (so'm)", "Qoldiq (so'm)"],
            "rows": rows_monthly,
            "data": {
                "yillik": yillik,
                "natija": self.kredit_natija,
                "jami_foiz": self.kredit_natija.jami_foiz,
                "jami_tolov": self.kredit_natija.jami_tolov,
            },
        }

    # ─────────────────────────────────────────────────────
    # 8. TAXES (7-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_taxes(self) -> Dict:
        revenues = self.t_prod_plan["data"]["yearly_revenue"]
        yearly_taxes = []

        if self.soliq_turi == "mchj":
            headers = ["Ko'rsatkich", "Stavka"] + self.YEAR_LABELS
            qqs_list = [rev * 12 / 112 for rev in revenues]
            rows = [
                ["QQS (12%)", "12%"] + qqs_list,
            ]
            for i in range(self.MODEL_YEARS):
                yearly_taxes.append({
                    "qqs": qqs_list[i],
                    "aylanma": 0,
                    "foyda_soliq": 0,
                    "jami": qqs_list[i],
                })
        else:
            headers = ["Ko'rsatkich", "Stavka"] + self.YEAR_LABELS
            yagona_list = [rev * 0.04 for rev in revenues]
            rows = [
                ["Yagona soliq (YTT)", "4%"] + yagona_list,
            ]
            for i in range(self.MODEL_YEARS):
                yearly_taxes.append({
                    "qqs": 0,
                    "aylanma": yagona_list[i],
                    "foyda_soliq": 0,
                    "jami": yagona_list[i],
                })

        ijtimoiy = self.t_labour["data"]["ijtimoiy"]
        rows.append(["Ijtimoiy soliq (12%)", "12%"] + [ijtimoiy] * self.MODEL_YEARS)
        jami_row = []
        for i in range(self.MODEL_YEARS):
            j = yearly_taxes[i]["jami"] + ijtimoiy
            jami_row.append(j)
        rows.append(["JAMI SOLIQLAR", ""] + jami_row)

        self.yearly_taxes = yearly_taxes
        return {
            "title": "SOLIQ VA BOJLAR",
            "ilova": "7-ILOVA",
            "headers": headers,
            "rows": rows,
            "data": {"yearly": yearly_taxes, "ijtimoiy_yillik": ijtimoiy},
        }

    # ─────────────────────────────────────────────────────
    # 9. COST SOLD / TANNARX (11-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_cost_sold(self) -> Dict:
        dep_yearly_list = self.t_depreciation["data"]["yearly_list"]
        labour_ishlab = self.t_labour["data"]["ishlab_jami"]
        revenues = self.t_prod_plan["data"]["yearly_revenue"]
        kommunal = self._yillik_kommunal()

        # ═══ Faoliyat turiga qarab xarajat ulushlarini olish ═══
        cs = self.cost_structure
        xomashyo_ulush = cs["xomashyo_ulushi"]
        ish_haqi_ulush = cs["ish_haqi_ulushi"]
        energiya_ulush = cs["energiya_ulushi"]
        marketing_ulush = cs["marketing_ulushi"]
        transport_ulush = cs["transport_ulushi"]
        ijara_ulush = cs["ijara_ulushi"]
        boshqa_ulush = cs["boshqa_ulushi"]
        asosiy_xarajat_nomi = cs["asosiy_xarajat_nomi"]

        yearly_cogs = []

        for i in range(self.MODEL_YEARS):
            cap = self.CAPACITIES[i]
            rev = revenues[i]
            dep = dep_yearly_list[i] if i < len(dep_yearly_list) else 0

            # Xomashyo/tovar — foydalanuvchi kiritgan yoki ulush bo'yicha
            if self.faoliyat_turi == "ishlab_chiqarish" and self.xomashyo_narx > 0:
                xomashyo = self.xomashyo_narx * self.hajm * cap
            elif self.faoliyat_turi == "savdo" and self.tovar_xaridi > 0:
                xomashyo = self.tovar_xaridi * self.hajm * cap
            elif self.faoliyat_turi == "qishloq_xojaligi" and self.urug_yem_narx > 0:
                xomashyo = self.urug_yem_narx * cap
            else:
                xomashyo = rev * xomashyo_ulush

            # Ish haqi
            ishchi = labour_ishlab if labour_ishlab > 0 else rev * ish_haqi_ulush

            # Energiya / kommunal
            if self.energiya_oylik > 0:
                komm = self.energiya_oylik * 12
            elif self.kommunal_oylik_input > 0:
                komm = self.kommunal_oylik_input * 12
            elif kommunal > 0:
                komm = kommunal
            else:
                komm = rev * energiya_ulush

            # Transport (qishloq xo'jaligi va savdo uchun)
            if self.transport_xarajat > 0:
                transport = self.transport_xarajat * 12
            else:
                transport = rev * transport_ulush

            # Ijara (savdo va xizmat uchun)
            if self.dokon_ijarasi > 0:
                ijara = self.dokon_ijarasi * 12
            elif self.joy_ijarasi > 0:
                ijara = self.joy_ijarasi * 12
            elif self.yer_ijarasi > 0:
                ijara = self.yer_ijarasi
            else:
                ijara = rev * ijara_ulush

            tannarx = xomashyo + ishchi + dep + komm + transport + ijara

            yearly_cogs.append({
                "xomashyo": xomashyo,
                "ish_haqi": ishchi,
                "amortizatsiya": dep,
                "kommunal": komm,
                "transport": transport,
                "ijara": ijara,
                "jami": tannarx,
            })

        rows = [
            ["Rivojlanish quvvati", "%"] + self.CAPACITIES_STR,
            [asosiy_xarajat_nomi, "so'm"] + [c["xomashyo"] for c in yearly_cogs],
            ["Ishlab chiqarish ish haqi", "so'm"] + [c["ish_haqi"] for c in yearly_cogs],
            ["Amortizatsiya", "so'm"] + [c["amortizatsiya"] for c in yearly_cogs],
            ["Kommunal xarajatlar", "so'm"] + [c["kommunal"] for c in yearly_cogs],
        ]
        if any(c["transport"] > 0 for c in yearly_cogs):
            rows.append(["Transport xarajatlari", "so'm"] + [c["transport"] for c in yearly_cogs])
        if any(c["ijara"] > 0 for c in yearly_cogs):
            rows.append(["Ijara xarajatlari", "so'm"] + [c["ijara"] for c in yearly_cogs])
        rows.append(["TANNARX", "so'm"] + [c["jami"] for c in yearly_cogs])

        admin_jami = self.t_labour["data"]["admin_jami"]
        marketing = [rev * marketing_ulush for rev in revenues]
        texnik = [self.asosiy_vositalar * 0.001] * self.MODEL_YEARS
        boshqa = [rev * boshqa_ulush for rev in revenues]
        davr = [admin_jami + marketing[i] + texnik[i] + boshqa[i] for i in range(self.MODEL_YEARS)]
        
        # Kredit foizlari
        kredit_foizlari = []
        for i in range(self.MODEL_YEARS):
            foiz = self.yillik_kredit[i]["foiz_tolov"] if i < len(self.yillik_kredit) else 0
            kredit_foizlari.append(foiz)

        rows.extend([
            ["", ""] + [""] * self.MODEL_YEARS,
            ["Ma'muriyat xarajatlari", "so'm"] + [admin_jami] * self.MODEL_YEARS,
            ["Marketing xarajatlar", "so'm"] + marketing,
            ["Texnik xizmat", "so'm"] + texnik,
            ["Boshqa xarajatlar", "so'm"] + boshqa,
            ["Davr xarajatlari", "so'm"] + davr,
            ["Operatsion xarajatlar", "so'm"] + [yearly_cogs[i]["jami"] + davr[i] for i in range(self.MODEL_YEARS)],
            ["Kredit foizlari", "so'm"] + kredit_foizlari,
            ["SOTILGAN MAHSULOTLARNING XARAJATLARI (TANNARX)", "so'm"] + [yearly_cogs[i]["jami"] + davr[i] + kredit_foizlari[i] for i in range(self.MODEL_YEARS)],
        ])

        self.yearly_cogs = yearly_cogs
        self.yearly_davr = davr
        self.yearly_marketing = marketing
        self.yearly_admin = [admin_jami] * self.MODEL_YEARS
        self.yearly_boshqa = boshqa

        return {
            "title": "TO'LIQ YILLIK XARAJATLAR (TANNARX)",
            "ilova": "11-ILOVA",
            "headers": ["Xarajat moddalari", "Birlik"] + self.YEAR_LABELS,
            "rows": rows,
            "data": {
                "yearly_cogs": yearly_cogs,
                "yearly_davr": davr,
                "yearly_marketing": marketing,
                "yearly_admin": [admin_jami] * self.MODEL_YEARS,
                "yearly_boshqa": boshqa,
            },
        }

    # ─────────────────────────────────────────────────────
    # 9.5. COST TOTAL (10-ILOVA) - TO'LIQ QUVVATLI ISHLAB CHIQARISH XARAJATLARI
    # ─────────────────────────────────────────────────────
    def _calc_cost_total(self) -> Dict:
        """10-ILOVA To'liq quvvatli ishlab chiqarish xarajatlari jadvallarini generatsiya qiladi."""
        # Eng oxirgi yil (to'liq quvvatdagi) xarajatlarni olamiz
        last_year_idx = min(self.MODEL_YEARS - 1, len(self.yearly_cogs) - 1)
        cogs = self.yearly_cogs[last_year_idx]
        
        # O'zgaruvchan (Variable) vs Doimiy (Fixed) qilib ajratish qoidasi
        # Xomashyo, energiya, transport = 100% o'zgaruvchan
        # Ish haqi = 80% doimiy, 20% o'zgaruvchan
        # Amortizatsiya, Ijara, Admin, Boshqa = 100% doimiy
        
        admin = self.yearly_admin[last_year_idx]
        marketing = self.yearly_marketing[last_year_idx]
        boshqa_davr = self.yearly_boshqa[last_year_idx]
        texnik = self.asosiy_vositalar * 0.001
        
        xomashyo = cogs["xomashyo"]
        ish_haqi = cogs["ish_haqi"]
        amort = cogs["amortizatsiya"]
        komm = cogs["kommunal"]
        transport = cogs["transport"]
        ijara = cogs["ijara"]
        
        rows = []
        jami_fixed = 0
        jami_var = 0
        
        def add_expense(nomi, full_val, fixed_ratio=1.0):
            nonlocal jami_fixed, jami_var
            f = full_val * fixed_ratio
            v = full_val * (1 - fixed_ratio)
            jami_fixed += f
            jami_var += v
            if full_val > 0:
                rows.append([nomi, full_val, f, f"{fixed_ratio*100:.0f}%", v, f"{(1-fixed_ratio)*100:.0f}%"])

        add_expense(self.cost_structure["asosiy_xarajat_nomi"], xomashyo, fixed_ratio=0.0)
        add_expense("Ishlab chiqarish xodimlari ish haqi", ish_haqi, fixed_ratio=0.8)
        add_expense("Amortizatsiya", amort, fixed_ratio=1.0)
        add_expense("Kommunal xarajatlar", komm, fixed_ratio=0.0)
        add_expense("Transport xarajatlari", transport, fixed_ratio=0.0)
        add_expense("Ijara xarajatlari", ijara, fixed_ratio=1.0)
        
        rows.append(["TO'G'RIDAN TO'G'RI XARAJATLAR", cogs["jami"], jami_fixed, "", jami_var, ""])
        rows.append(["", "", "", "", "", ""])
        
        prev_fixed, prev_var = jami_fixed, jami_var
        
        add_expense("Ma'muriyat xodimlari ish haqi", admin, fixed_ratio=1.0)
        add_expense("Boshqa ko'zda tutilmagan xarajatlar", boshqa_davr, fixed_ratio=0.5)
        add_expense("Asosiy vositalarga texnik xizmat", texnik, fixed_ratio=0.7)
        add_expense("Marketing xarajatlari", marketing, fixed_ratio=0.7)
        
        rows.append(["", "", "", "", "", ""])
        rows.append(["JAMI XARAJATLAR", cogs["jami"] + admin + boshqa_davr + texnik + marketing, jami_fixed, f"{jami_fixed/(jami_fixed+jami_var)*100:.1f}%" if (jami_fixed+jami_var)>0 else "", jami_var, f"{jami_var/(jami_fixed+jami_var)*100:.1f}%" if (jami_fixed+jami_var)>0 else ""])
        
        max_revenue = self.hajm * self.narx
        rows.append(["TO'LIQ QUVVATDA SOTISH", max_revenue, "", "", "", ""])
        
        zararsiz = jami_fixed / (1 - (jami_var / max_revenue)) if max_revenue > 0 and jami_var < max_revenue else 0
        rows.append(["ZARARSIZLANISH NUQTASI (so'm)", zararsiz, "", "", "", ""])
        
        return {
            "title": "TO'LIQ QUVVATLI BO'LGAN ISHLAB CHIQARISH XARAJATLARI (1-yil uchun)",
            "ilova": "10-ILOVA",
            "headers": ["XARAJATLAR", "TO'LIQ XARAJATLAR (so'm)", "DOIMIY xarajat", "Ulush", "O'ZGARUVCHAN xarajat", "Ulush"],
            "rows": rows,
            "data": {},
        }

    # ─────────────────────────────────────────────────────
    # 10. PROF LOSS (12-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_prof_loss(self) -> Dict:
        revenues = self.t_prod_plan["data"]["yearly_revenue"]
        is_mchj = self.soliq_turi == "mchj"

        pnl_rows = []
        yearly_pnl = []

        for i in range(self.MODEL_YEARS):
            rev = revenues[i]
            qqs = self.yearly_taxes[i]["qqs"] if is_mchj else 0
            net_rev = rev - qqs
            cogs = self.yearly_cogs[i]["jami"]
            gross = net_rev - cogs

            admin = self.yearly_admin[i]
            marketing = self.yearly_marketing[i]
            boshqa = self.yearly_boshqa[i]
            davr_total = admin + marketing + boshqa

            operating = gross - davr_total

            foiz_year = self.yillik_kredit[i]["foiz_tolov"] if i < len(self.yillik_kredit) else 0
            ebt = operating - foiz_year

            if is_mchj:
                soliq = max(0, ebt) * 0.12
            else:
                soliq = rev * 0.04

            net_income = ebt - soliq

            yearly_pnl.append({
                "daromad": rev,
                "qqs": qqs,
                "sof_daromad": net_rev,
                "tannarx": cogs,
                "yalpi_foyda": gross,
                "admin": admin,
                "marketing": marketing,
                "boshqa": boshqa,
                "davr_xarajat": davr_total,
                "operatsion_foyda": operating,
                "foiz": foiz_year,
                "ebt": ebt,
                "soliq": soliq,
                "sof_foyda": net_income,
            })

        self.yearly_pnl = yearly_pnl

        row_list = [
            ("Sotishdan tushgan daromad", [p["daromad"] for p in yearly_pnl]),
        ]
        if is_mchj:
            row_list.append(("QQS (12%)", [p["qqs"] for p in yearly_pnl]))
        row_list.extend([
            ("Sof sotishdan tushgan daromad", [p["sof_daromad"] for p in yearly_pnl]),
            ("Tannarx (xizmatlar)", [p["tannarx"] for p in yearly_pnl]),
            ("Umumiy daromad (yalpi foyda)", [p["yalpi_foyda"] for p in yearly_pnl]),
            ("Ma'muriy xarajatlar", [p["admin"] for p in yearly_pnl]),
            ("Marketing xarajatlar", [p["marketing"] for p in yearly_pnl]),
            ("Boshqa xarajatlar", [p["boshqa"] for p in yearly_pnl]),
            ("Operatsion foyda", [p["operatsion_foyda"] for p in yearly_pnl]),
            ("Kredit foizlari", [p["foiz"] for p in yearly_pnl]),
            ("Soliq to'laguncha foyda", [p["ebt"] for p in yearly_pnl]),
            ("Soliqlar", [p["soliq"] for p in yearly_pnl]),
            ("SOF FOYDA (ZARAR)", [p["sof_foyda"] for p in yearly_pnl]),
        ])

        rows = [[label, "so'm"] + vals for label, vals in row_list]

        rentabellik = []
        for p in yearly_pnl:
            r = (p["sof_foyda"] / p["daromad"] * 100) if p["daromad"] > 0 else 0
            rentabellik.append(f"{r:.1f}%")
        rows.append(["Sof rentabellik", "%"] + rentabellik)

        return {
            "title": "KUTILAYOTGAN FOYDA VA ZARARLAR TO'G'RISIDA HISOBOT",
            "ilova": "12-ILOVA",
            "headers": ["Ko'rsatgichlar", "Birlik"] + self.YEAR_LABELS,
            "rows": rows,
            "data": {"yearly": yearly_pnl},
        }

    # ─────────────────────────────────────────────────────
    # 11. CASH FLOW (13-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_cash_flow(self) -> Dict:
        investment = self.loyiha_qiymati
        dep = self.t_depreciation["data"]["yearly"]
        yearly_cf = []
        cumulative = -investment

        for i in range(self.MODEL_YEARS):
            p = self.yearly_pnl[i]
            rev = p["daromad"]
            qqs = p["qqs"]
            net_sales = rev - qqs
            cogs = p["tannarx"]
            gross_cash = net_sales - cogs

            amort = dep
            marketing = p["marketing"]
            admin = p["admin"]
            boshqa = p["boshqa"]
            operating_cf = gross_cash + amort - marketing - admin - boshqa

            foiz = p["foiz"]
            soliq = p["soliq"]
            principal = self.yillik_kredit[i]["asosiy_qarz"] if i < len(self.yillik_kredit) else 0

            net_cf = operating_cf - foiz - soliq - principal
            cumulative += net_cf

            yearly_cf.append({
                "daromad": rev,
                "qqs": qqs,
                "sof_tushum": net_sales,
                "tannarx": cogs,
                "yalpi_tushum": gross_cash,
                "amortizatsiya": amort,
                "marketing": marketing,
                "admin": admin,
                "boshqa": boshqa,
                "operatsion_cf": operating_cf,
                "foiz": foiz,
                "soliq": soliq,
                "asosiy_qarz": principal,
                "sof_cf": net_cf,
                "kumulyativ": cumulative,
            })

        self.yearly_cf = yearly_cf

        row_defs = [
            ("Sotishdan tushgan tushum", [c["daromad"] for c in yearly_cf]),
        ]
        if self.soliq_turi == "mchj":
            row_defs.append(("QQS", [c["qqs"] for c in yearly_cf]))
        row_defs.extend([
            ("Sotishdan tushgan naqd pul", [c["sof_tushum"] for c in yearly_cf]),
            ("Xizmat xarajatlari (tannarx)", [c["tannarx"] for c in yearly_cf]),
            ("Yalpi pul tushumi", [c["yalpi_tushum"] for c in yearly_cf]),
            ("Amortizatsiya (+)", [c["amortizatsiya"] for c in yearly_cf]),
            ("Marketing xarajatlar", [c["marketing"] for c in yearly_cf]),
            ("Ma'muriy xarajatlar", [c["admin"] for c in yearly_cf]),
            ("Boshqa xarajatlar", [c["boshqa"] for c in yearly_cf]),
            ("Operatsion pul oqimi", [c["operatsion_cf"] for c in yearly_cf]),
        ])
        
        # 0-yil uchun Investitsiya hisobini qo'shib jadvallash (Lekin 0-yil yo'q qilinayotgani sababli asosan CashFlow-da qoladi, Investment-ni ko'rsatish shart emas yillarga solganda)
        # CF dagi Investitsiya qatorini -investment shaklida 1-yil o'rniga emas, oldin chiqaramiz:
        
        row_defs.extend([
            ("Foiz to'lovlari", [c["foiz"] for c in yearly_cf]),
            ("Soliqlar", [c["soliq"] for c in yearly_cf]),
            ("Asosiy qarz qaytarish", [c["asosiy_qarz"] for c in yearly_cf]),
            ("SOF PUL OQIMI", [c["sof_cf"] for c in yearly_cf]),
            ("KUMULYATIV PUL OQIMI", [c["kumulyativ"] for c in yearly_cf]),
        ])

        headers = ["Ko'rsatgichlar"] + self.YEAR_LABELS
        rows = [[label] + vals for label, vals in row_defs]

        # Jadval boshida Investitsiya qatorini qo'shsak bo'ladi (1-yildan deb hisoblab):
        rows.insert(0, ["Investitsiyalar", -investment] + [""]*(self.MODEL_YEARS-1))

        return {
            "title": "PUL OQIMI (CASH FLOW)",
            "ilova": "13-ILOVA",
            "headers": headers,
            "rows": rows,
            "data": {"yearly": yearly_cf, "investment": investment},
        }

    # ─────────────────────────────────────────────────────
    # 12. NPV (14-ILOVA)
    # ─────────────────────────────────────────────────────
    def _calc_npv(self) -> Dict:
        investment = self.loyiha_qiymati
        cf_list = [-investment] + [c["sof_cf"] for c in self.yearly_cf]
        r = self.discount_rate

        npv_val = calculate_npv(r, cf_list)
        irr_val = calculate_irr(cf_list)

        if investment > 0:
            pi = (npv_val + investment) / investment
            roi = (sum(c["sof_cf"] for c in self.yearly_cf) / investment * 100) / self.MODEL_YEARS
        else:
            pi = 0
            roi = 0

        payback = 0
        temp = -investment
        for c in self.yearly_cf:
            if temp < 0 and temp + c["sof_cf"] >= 0:
                payback = self.yearly_cf.index(c) + 1
                if c["sof_cf"] > 0:
                    payback = self.yearly_cf.index(c) + abs(temp) / c["sof_cf"]
                break
            temp += c["sof_cf"]
        if payback == 0 and temp < 0:
            payback = self.MODEL_YEARS + 1

        disc_factors = [1 / ((1 + r / 100) ** t) for t in range(self.MODEL_YEARS + 1)]
        pv_list = [cf_list[t] * disc_factors[t] for t in range(len(cf_list))]

        npv_rows = []
        npv_rows.append(["Investitsion xarajatlar", cf_list[0], "", ""])
        for i in range(1, len(cf_list)):
            npv_rows.append([f"{i}-yil", cf_list[i], f"{disc_factors[i]:.6f}", pv_list[i]])
        npv_rows.append(["", "", "", ""])
        
        jjq = sum(pv_list[1:])
        sjq = npv_val
        npv_rows.append(["Jami joriy qiymat (JJQ)", "", "", jjq])
        npv_rows.append(["Investitsion xarajatlar (IX)", "", "", -investment])
        npv_rows.append(["SOF JORIY QIYMAT (SJQ=JJQ-IX)", "", "", sjq])
        npv_rows.append(["Rentabellik indeksi (IR)", "", "", f"{pi:.4f}"])
        npv_rows.append(["Ichki daromad darajasi (IRR)", "", "", f"{irr_val}%" if irr_val else "—"])
        npv_rows.append(["Investitsiyalarni qaytarish muddati", "", "", f"{payback:.1f} yil" if payback <= self.MODEL_YEARS else "7+ yil"])

        warning_msg = None
        if sjq < 0 or roi < 0 or (irr_val is not None and irr_val < r):
            warning_msg = "DIQQAT: Loyiha o'zini oqlamaydi (NPV salbiy). Rentabellikni oshirish uchun mahsulot/xizmat narxini ko'taring yoki xarajatlarni qisqartiring."

        self.indicators = {
            "npv": round(npv_val, 2),
            "irr": irr_val,
            "pi": round(pi, 4),
            "roi": round(roi, 2),
            "payback": round(payback, 2) if payback <= self.MODEL_YEARS else None,
            "loyiha_qiymati": self.loyiha_qiymati,
            "oz_mablag": self.oz_mablag,
            "kredit": self.kredit_summa,
            "jami_daromad": sum(self.t_prod_plan["data"]["yearly_revenue"]),
            "jami_sof_foyda": sum(p["sof_foyda"] for p in self.yearly_pnl),
            "discount_rate": self.discount_rate,
            "warning": warning_msg
        }

        return {
            "title": "LOYIHANING IQTISODIY SAMARADORLIK KO'RSATKICHLARI",
            "ilova": "14-ILOVA",
            "headers": ["Ko'rsatkich", "Sof pul oqimi", f"{r}% chegirma koeffitsienti", "Joriy qiymat"],
            "rows": npv_rows,
            "data": self.indicators,
        }

    def _yillik_kommunal(self) -> float:
        elektr = self.elektr * 900 * 12
        gaz = self.gaz * 1500 * 12
        suv = self.suv * 3000 * 12
        oqava = self.oqava * 2000 * 12
        return elektr + gaz + suv + oqava

    # ─────────────────────────────────────────────────────
    # 13. KOMMUNIKATSIYA VA INFRATUZILMA
    # ─────────────────────────────────────────────────────
    def _calc_kommunal(self) -> Dict:
        elektr = self.elektr * 900
        gaz = self.gaz * 1500
        suv = self.suv * 3000
        oqava = self.oqava * 2000
        jami_oylik = elektr + gaz + suv + oqava
        
        rows = [
            ["Elektr energiyasi", "kVT", self.elektr, 900, elektr, elektr * 12],
            ["Tabiiy gaz", "m3", self.gaz, 1500, gaz, gaz * 12],
            ["Ichimlik suvi", "m3", self.suv, 3000, suv, suv * 12],
            ["Oqava suv (Kanalizatsiya)", "m3", self.oqava, 2000, oqava, oqava * 12],
            ["JAMI", "", "", "", jami_oylik, jami_oylik * 12]
        ]
        
        return {
            "title": "KOMMUNIKATSIYA VA INFRATUZILMA XARAJATLARI",
            "ilova": "KOMMUNAL",
            "headers": ["Xarajat turi", "O'lchov birligi", "Miqdori (oylik)", "Tarif (so'm)", "Oylik xarajat (so'm)", "Yillik xarajat (so'm)"],
            "rows": rows,
            "data": {},
        }

    def get_all_tables(self) -> List[Dict]:
        """Barcha jadvallarni tartibda qaytaradi."""
        return [
            self.t_proj_cost,
            self.t_fin_plan,
            self.t_share_costs,
            self.t_depreciation,
            self.t_labour,
            self.t_kommunal,
            self.t_prod_summary,
            self.t_prod_plan,
            self.t_loans,
            self.t_taxes,
            self.t_cost_total,
            self.t_cost_sold,
            self.t_prof_loss,
            self.t_cash_flow,
            self.t_npv,
        ]

    def get_context(self) -> Dict[str, Any]:
        """Word template uchun context lug'ati."""
        ind = self.indicators
        ctx = {
            "loyiha_nomi": self.loyiha_nomi,
            "tashabbuskor": self.tashabbuskor,
            "manzil": self.manzil,
            "bank": self.bank,
            "stir": self.stir,
            "jshshir": self.jshshir,
            "faoliyat": self.faoliyat,
            "faoliyat_turi": self.faoliyat_turi,
            "faoliyat_turi_nomi": self.cost_structure["nomi"],
            "mulk": self.mulk,
            "fio": self.fio,
            "pasport": self.pasport,
            "berilgan_vaqti": self.berilgan_vaqti,
            "mahsulot": self.mahsulot,
            "olchov": self.olchov,
            "loyiha_qiymati": self.loyiha_qiymati,
            "oz_mablag": self.oz_mablag,
            "kredit": self.kredit_summa,
            "muddat": self.muddat_oy,
            "imtiyoz": self.imtiyoz_oy,
            "foiz": self.foiz,
            "hajm": self.hajm,
            "narx": self.narx,
            "npv": ind["npv"],
            "irr": ind["irr"],
            "pi": ind["pi"],
            "roi": ind["roi"],
            "payback": ind["payback"],
            "discount_rate": self.discount_rate,
            "soliq_turi": self.soliq_turi,
            "kredit_turi": self.kredit_turi,
            "yillik_daromad": ind["jami_daromad"] / self.MODEL_YEARS,
            "yillik_sof_foyda": ind["jami_sof_foyda"] / self.MODEL_YEARS,
            "direktor": self.direktor_soni,
            "xodim": self.xodim_soni,
            "yangi_xodim": self.yangi_xodim_soni,
            "rahbar_oylik": self.rahbar_oylik,
            "ishchi_oylik": self.ishchi_oylik,
            "yangi_ishchi_oylik": self.yangi_ishchi_oylik,
            "elektr": self.elektr,
            "gaz": self.gaz,
            "suv": self.suv,
            "oqava": self.oqava,
            "warning": ind["warning"] if ind.get("warning") else ""
        }
        ctx.update(self._raw)
        return ctx
