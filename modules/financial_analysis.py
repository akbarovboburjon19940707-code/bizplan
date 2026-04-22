"""
Moliyaviy Tahlil Moduli — Enterprise Edition
=============================================
Excel modelini to'liq kodga ko'chirilgan versiyasi.
7 yillik model, barcha moliyaviy hisob-kitoblar (CAPEX, OPEX, P&L, CashFlow).
"""
from typing import List, Dict, Any, Optional
import math
from .credit_calculator import hisob_kredit, KreditNatija


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (ValueError, TypeError):
        return default


def calculate_npv(discount_rate: float, cash_flows: List[float]) -> float:
    r = discount_rate / 100
    return sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows))


def calculate_irr(cash_flows: List[float], max_iter: int = 1000) -> Optional[float]:
    if not cash_flows or len(cash_flows) < 2:
        return None
    
    # Newton-Raphson approximation
    guess = 0.1
    for _ in range(max_iter):
        npv_val = sum(cf / ((1 + guess) ** t) for t, cf in enumerate(cash_flows))
        dnpv = sum(-t * cf / ((1 + guess) ** (t + 1)) for t, cf in enumerate(cash_flows))
        if abs(dnpv) < 1e-12: break
        new_guess = guess - npv_val / dnpv
        if abs(new_guess - guess) < 1e-6:
            return round(new_guess * 100, 2)
        guess = new_guess
    
    # Fallback to Bisection
    low, high = -0.99, 10.0
    for _ in range(max_iter):
        mid = (low + high) / 2
        npv_val = sum(cf / ((1 + mid) ** t) for t, cf in enumerate(cash_flows))
        if abs(npv_val) < 1e-6: return round(mid * 100, 2)
        if npv_val > 0: low = mid
        else: high = mid
    return round(mid * 100, 2)


class FinancialModel:
    def __init__(self, form_data: Dict[str, Any]):
        self.form = form_data
        self.muddat_oy = int(safe_float(form_data.get("muddat", 36)))
        self.muddat_yil = min(max(math.ceil(self.muddat_oy / 12), 1), 7)
        self.years = list(range(1, self.muddat_yil + 1))
        
        # 1. Investitsiya (CAPEX)
        self.loyiha_qiymati = safe_float(form_data.get("loyiha_qiymati"))
        self.oz_mablag = safe_float(form_data.get("oz_mablag"))
        self.kredit_summa = safe_float(form_data.get("kredit"))
        
        # 2. Kredit hisoblash
        self.kredit_natija = hisob_kredit(
            self.kredit_summa,
            safe_float(form_data.get("foiz")),
            self.muddat_oy,
            int(safe_float(form_data.get("imtiyoz", 0))),
            form_data.get("kredit_turi", "annuitet")
        )
        
        # 3. Yillik kredit to'lovlari (Loans Sheet logic)
        self.yillik_kredit = self._calculate_yearly_loans()
        
        # 4. Amortizatsiya (Depreciate Sheet)
        # Excel'da: C5 / 7 yil qilingan (odatda 15% stavka)
        self.yillik_amort = [self.loyiha_qiymati * 0.15] * self.muddat_yil
        
        # 5. Ish haqi (Labour Sheet)
        self.yillik_ish_haqi = self._calculate_yearly_labour()
        
        # 6. Kommunal va boshqa xarajatlar (CostTotal)
        self.yillik_kommunal = self._calculate_yearly_utilities()
        
        # 7. Sotish rejasi (ProdPlan)
        self.yillik_daromad = self._calculate_yearly_revenue()
        
        # 8. To'liq moliyaviy jadval (P&L va CashFlow)
        self.model_data = self._build_model()

    def _calculate_yearly_loans(self) -> List[Dict]:
        """Kredit jadvalini yillarga bo'lib beradi."""
        results = []
        for y in self.years:
            start_month = (y - 1) * 12 + 1
            end_month = y * 12
            
            asosiy_qarz = sum(t.asosiy_qarz for t in self.kredit_natija.jadval if start_month <= t.oy <= end_month)
            foiz_tolov = sum(t.foiz_tolov for t in self.kredit_natija.jadval if start_month <= t.oy <= end_month)
            
            results.append({
                "yil": y,
                "asosiy_qarz": asosiy_qarz,
                "foiz_tolov": foiz_tolov,
                "jami_tolov": asosiy_qarz + foiz_tolov
            })
        return results

    def _calculate_yearly_labour(self) -> List[float]:
        ishchi_soni = int(safe_float(self.form.get("xodim", 0)))
        yangi_soni = int(safe_float(self.form.get("yangi_xodim", 0)))
        dir_soni = int(safe_float(self.form.get("direktor", 1)))
        
        ishchi_oylik = safe_float(self.form.get("ishchi_oylik"))
        rahbar_oylik = safe_float(self.form.get("rahbar_oylik"))
        yangi_oylik = safe_float(self.form.get("yangi_ishchi_oylik"))
        
        oylik_fond = (dir_soni * rahbar_oylik) + (ishchi_soni * ishchi_oylik) + (yangi_soni * yangi_oylik)
        yillik_fond = oylik_fond * 12
        # Ijtimoiy soliq 12%
        yillik_jami = yillik_fond * 1.12
        return [yillik_jami] * self.muddat_yil

    def _calculate_yearly_utilities(self) -> List[float]:
        elektr = safe_float(self.form.get("elektr")) * 900 * 12
        gaz = safe_float(self.form.get("gaz")) * 1500 * 12
        suv = safe_float(self.form.get("suv")) * 3000 * 12
        oqava = safe_float(self.form.get("oqava")) * 2000 * 12
        
        yillik_util = elektr + gaz + suv + oqava
        # Boshqa xarajatlar uchun +10%
        return [yillik_util * 1.1] * self.muddat_yil

    def _calculate_yearly_revenue(self) -> List[float]:
        hajm = safe_float(self.form.get("hajm"))
        narx = safe_float(self.form.get("narx"))
        max_revenue = hajm * narx
        
        # Excel kabi quvvatlarni oshirib borish: 1-yil 88%, 2-yil 90%, ... 100%
        capacities = [0.88, 0.90, 0.93, 0.95, 0.97, 0.99, 1.00]
        revenues = []
        for i in range(self.muddat_yil):
            cap = capacities[i] if i < len(capacities) else 1.0
            revenues.append(max_revenue * cap)
        return revenues

    def _build_model(self) -> Dict[str, List]:
        """P&L va CashFlow jadvallarini yig'ish."""
        pnls = []
        cashflows = []
        
        cumulative_cashflow = -self.loyiha_qiymati
        
        for i, y in enumerate(self.years):
            rev = self.yillik_daromad[i]
            opex = self.yillik_ish_haqi[i] + self.yillik_kommunal[i]
            amort = self.yillik_amort[i]
            interest = self.yillik_kredit[i]["foiz_tolov"]
            principal = self.yillik_kredit[i]["asosiy_qarz"]
            
            ebitda = rev - opex
            ebit = ebitda - amort
            ebt = ebit - interest
            
            # Soliqlar (masalan 4% aylanmadan yoki 15% foydadan — modelga qarab)
            # Excelda 4% (yoki soddalashtirilgan) deb olinadi odatda
            tax = ebt * 0.15 if ebt > 0 else 0
            net_income = ebt - tax
            
            pnls.append({
                "yil": y,
                "daromad": rev,
                "xarajat": opex,
                "amort": amort,
                "foiz": interest,
                "soliq": tax,
                "sof_foyda": net_income
            })
            
            # Cash Flow
            # CF = Net Income + Depreciation - Principal Repayment
            operatsion_cf = net_income + amort - principal
            # 0-yil (investitsiya) hisobga olingan holda
            cumulative_cashflow += operatsion_cf
            
            cashflows.append({
                "yil": y,
                "income": net_income,
                "amort": amort,
                "principal": principal,
                "net_cf": operatsion_cf,
                "cum_cf": cumulative_cashflow
            })
            
        # Global indikatorlar
        # NPV uchun cash flow list: [-Investment, Year1_CF, Year2_CF, ...]
        cf_list = [-self.loyiha_qiymati] + [c["net_cf"] for c in cashflows]
        disc_rate = safe_float(self.form.get("foiz"), 15.0) # Kredit foizi discount rate sifatida
        
        npv_val = calculate_npv(disc_rate, cf_list)
        irr_val = calculate_irr(cf_list)
        pi = (npv_val + self.loyiha_qiymati) / self.loyiha_qiymati if self.loyiha_qiymati > 0 else 0
        roi = (sum(c["income"] for c in cashflows) / self.loyiha_qiymati * 100) / self.muddat_yil if self.loyiha_qiymati > 0 else 0
        
        # Oqlash muddati (Payback)
        payback = 0
        temp_cum = -self.loyiha_qiymati
        for c in cashflows:
            if temp_cum < 0 and temp_cum + c["net_cf"] >= 0:
                payback = c["yil"] - 1 + (abs(temp_cum) / c["net_cf"])
                break
            temp_cum += c["net_cf"]
        if payback == 0 and temp_cum < 0: payback = self.muddat_yil + 1

        return {
            "pnls": pnls,
            "cashflows": cashflows,
            "indicators": {
                "npv": round(npv_val, 2),
                "irr": irr_val,
                "pi": round(pi, 2),
                "roi": round(roi, 2),
                "payback": round(payback, 2),
                "loyiha_qiymati": self.loyiha_qiymati,
                "oz_mablag": self.oz_mablag,
                "kredit": self.kredit_summa,
                "jami_daromad": sum(self.yillik_daromad),
                "jami_sof_foyda": sum(p["sof_foyda"] for p in pnls)
            }
        }

    def get_context(self) -> Dict[str, Any]:
        """Word template uchun tayyor context lug'ati."""
        ind = self.model_data["indicators"]
        ctx = {
            "loyiha_qiymati": ind["loyiha_qiymati"],
            "oz_mablag": ind["oz_mablag"],
            "kredit": ind["kredit"],
            "muddat": self.muddat_oy,
            "imtiyoz": int(safe_float(self.form.get("imtiyoz", 0))),
            "foiz": safe_float(self.form.get("foiz")),
            "npv": ind["npv"],
            "irr": ind["irr"],
            "pi": ind["pi"],
            "roi": ind["roi"],
            "payback": ind["payback"],
            "yillik_daromad": ind["jami_daromad"] / self.muddat_yil,
            "yillik_sof_foyda": ind["jami_sof_foyda"] / self.muddat_yil,
        }
        # Qo'shimcha matnli ma'lumotlar
        ctx.update(self.form)
        return ctx
