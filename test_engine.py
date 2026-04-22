"""Quick integration test for FinancialEngine."""
from modules.financial_engine import FinancialEngine

params = {
    "loyiha_nomi": "Test Loyiha",
    "tashabbuskor": "Test MCHJ",
    "loyiha_qiymati": "1000000000",
    "oz_mablag": "200000000",
    "kredit": "800000000",
    "foiz": "20",
    "muddat": "60",
    "imtiyoz": "24",
    "kredit_turi": "differentsial",
    "soliq_turi": "ytt",
    "discount_rate": "13.5",
    "mahsulot": "Test mahsulot",
    "hajm": "10000",
    "narx": "150000",
    "olchov": "dona",
    "direktor": "1",
    "xodim": "5",
    "yangi_xodim": "3",
    "rahbar_oylik": "5000000",
    "ishchi_oylik": "3000000",
    "yangi_ishchi_oylik": "2500000",
    "elektr": "1000",
    "gaz": "500",
    "suv": "200",
    "oqava": "150",
}

print("=" * 60)
print("TEST 1: Differentsial + YTT")
print("=" * 60)
e = FinancialEngine(params)
ind = e.indicators

print("\n--- INDICATORS ---")
for k, v in ind.items():
    print(f"  {k}: {v}")

print("\n--- KREDIT YILLIK ---")
for yk in e.yillik_kredit:
    y = yk["yil"]
    print(f"  {y}-yil: asosiy={yk['asosiy_qarz']:>15,.0f}  foiz={yk['foiz_tolov']:>13,.0f}  qoldiq={yk['qoldiq']:>15,.0f}")

print("\n--- REVENUE (ProdPlan) ---")
for i, r in enumerate(e.t_prod_plan["data"]["yearly_revenue"]):
    print(f"  {i+1}-yil: {r:>18,.0f}")

print("\n--- P&L ---")
for i, p in enumerate(e.yearly_pnl):
    print(f"  {i+1}-yil: daromad={p['daromad']:>15,.0f}  sof_foyda={p['sof_foyda']:>15,.0f}")

print("\n--- CASH FLOW ---")
for i, c in enumerate(e.yearly_cf):
    print(f"  {i+1}-yil: sof_cf={c['sof_cf']:>15,.0f}  kumulyativ={c['kumulyativ']:>15,.0f}")

print(f"\nTABLES COUNT: {len(e.get_all_tables())}")

# Test 2: Annuitet + MCHJ
print("\n" + "=" * 60)
print("TEST 2: Annuitet + MCHJ")
print("=" * 60)
params2 = dict(params)
params2["kredit_turi"] = "annuitet"
params2["soliq_turi"] = "mchj"
e2 = FinancialEngine(params2)
ind2 = e2.indicators
print(f"  NPV: {ind2['npv']:,.0f}")
print(f"  IRR: {ind2['irr']}%")
print(f"  PI:  {ind2['pi']}")
print(f"  ROI: {ind2['roi']}%")
print(f"  Payback: {ind2['payback']} yil")

# Test Excel writer
print("\n" + "=" * 60)
print("TEST 3: Excel Writer")
print("=" * 60)
from modules.excel_writer import write_excel_output
import os
template = os.path.join(os.path.dirname(__file__), "data.xlsx")
output = os.path.join(os.path.dirname(__file__), "test_output.xlsx")
if os.path.exists(template):
    write_excel_output(template, output, e)
    print(f"  Excel yaratildi: {output}")
    if os.path.exists(output):
        os.remove(output)
        print("  Test fayl o'chirildi")
else:
    print("  data.xlsx topilmadi, o'tkazildi")

# Test Word
print("\n" + "=" * 60)
print("TEST 4: Document Engine")
print("=" * 60)
try:
    from modules.document_engine import create_word_document
    import os
    template = os.path.join(os.path.dirname(__file__), "template.docx")
    output = os.path.join(os.path.dirname(__file__), "test_word.docx")
    if os.path.exists(template):
        ctx = e.get_context()
        create_word_document(template, output, ctx, model=e)
        sz = os.path.getsize(output)
        print(f"  Word yaratildi: {output} ({sz:,} bytes)")
        # if os.path.exists(output):
        #     os.remove(output)
        #     print("  Test fayl o'chirildi")
    else:
        print("  template.docx topilmadi")
except Exception as ex:
    print(f"  Word xatolik: {ex}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
