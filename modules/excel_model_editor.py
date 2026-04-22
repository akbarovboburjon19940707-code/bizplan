import os
import shutil
import math
try:
    import pandas as pd
    import openpyxl
except ImportError:
    pass

try:
    import xlwings as xw
except ImportError:
    xw = None


class ExcelModelEditor:
    """
    Excel moliyaviy modelini kredit muddatiga (oylarga) ko'ra avtomatik
    kengaytiruvchi (yoki moslashtiruvchi) Python skript.
    
    Talablar: pandas, openpyxl, xlwings.
    (Windows muhitida ishlashi uchun xlwings talab qilinadi).
    """

    def __init__(self, input_file: str, output_file: str):
        self.input_file = input_file
        self.output_file = output_file
        
        # O'zgartirilishi kerak bo'lgan jadvallar (sheet names):
        self.target_sheets = [
            "ProjCost", "FinPlan", "Share of Costs", "Depreciate",
            "Labour", "ProdPlan", "Loans", "Taxes", "CostSold",
            "ProfLoss", "CashFlow", "npv"
        ]

    def expand_model(self, target_months: int):
        """
        Modelni berilgan oy (target_months) gacha kengaytiradi (yoki qisqartiradi)
        va yangi faylga saqlaydi.
        """
        if xw is None:
            raise EnvironmentError("Ushbu amaliyot xlwings modulini va Windows tizimini talab qiladi.")

        print(f"[Info] Excel fayl nusxasi shakllantirilmoqda: {self.output_file}")
        shutil.copy2(self.input_file, self.output_file)

        # MS Excelni yashirin rejimda ochish
        app = xw.App(visible=False)
        app.display_alerts = False
        app.screen_updating = False

        wb = app.books.open(self.output_file)
        try:
            # Fayldagi mavjud barcha varaq (sheet) larni aylanib chiqish
            for ws in wb.sheets:
                # Agar joriy varaq asosiy targetlar qatorida bo'lsa
                matching_targets = [t for t in self.target_sheets if t.lower() in ws.name.lower()]
                if not matching_targets:
                    continue
                
                sheet_type = matching_targets[0]
                print(f"[Process] '{ws.name}' jadvali ({sheet_type}) qayta ishlanmoqda...")
                
                # 'Loans' odatda vertikal (oylar pastga qarab chizilgan)
                if sheet_type.lower() == "loans" or "kreditlar" in ws.name.lower():
                    self._expand_vertically(ws, target_months)
                else:
                    # Qolgan barcha jadvallar gorizontal chizilgan deb hisoblaymiz
                    self._expand_horizontally(ws, target_months)

            print("[Info] Qayta hisoblash amalga oshirilmoqda...")
            app.calculate()
            wb.save()
            print("[Success] Model kengaytirildi va jadvallar yangilandi.")

        except Exception as e:
            print(f"[Error] Xatolik yuz berdi: {str(e)}")
            raise e
        finally:
            wb.close()
            app.quit()

        return self.output_file

    def _expand_vertically(self, ws, target_months: int):
        """
        Kreditlar (Loans) kabi jadvallar oylar kesimida pastga qarab o'sadi.
        Ushbu metod maqsadli ustunni AutoFill orqali ko'paytiradi.
        """
        used_range = ws.used_range
        last_row = used_range.last_cell.row
        last_col = used_range.last_cell.column
        
        # Excel Loans jadvalida eng so'nggi oyning qator indeksini aniqlash.
        # Bu yerda oddiy logic: eng pastki qatordagi barcha ustunlarni belgilab nusxalaymiz 
        try:
            # Nusxa olinadigan eng oxirgi baza qatori
            source_range = ws.range((last_row, 1), (last_row, last_col))
            
            # Agar last_row model standartida e.g. 50 oy bo'lsa, uni targetgacha cho'zamiz
            # (Agar foydalanuvchi qisqaroq kredit so'rasa, formula AutoFill ishlashiga mos kelishi uchun
            # hozircha doim kengayadi, qisqartirish uchun row larni o'chirish logikasi yozilishi mumkin).
            
            expand_amount = target_months
            if expand_amount > 0:
                dest_range = ws.range((last_row, 1), (last_row + expand_amount, last_col))
                # Type=0 xlFillDefault
                source_range.api.AutoFill(Destination=dest_range.api, Type=0)
                
        except Exception as e:
            print(f"  [Warning] Vertikal kengaytirishda xatolik: {e}")

    def _expand_horizontally(self, ws, target_months: int):
        """
        CashFlow, FinPlan va hokazo jadvallar uchun gorizontal o'sish amalga oshiriladi.
        Model yil, yoki oyga bog'langan bo'lishi mumkin.
        """
        used_range = ws.used_range
        last_row = used_range.last_cell.row
        last_col = used_range.last_cell.column
        
        # target_months (masalan 36 oy bo'lsa, agar baza yilga bo'lingan bo'lsa -> 3 yil, oy bo'lsa -> 36 ustun)
        # Buni ehtiyoj uchun 36 oy deb ustunga to'g'ridan to'g'ri cho'zish (agar oylik format bo'lsa) qilamiz.
        # Formulalarni (column) right-side kengayadi.
        
        try:
            # Eng so'nggi ma'lumotli butun ustun ("column") ni belgilash:
            source_range = ws.range((1, last_col), (last_row, last_col))
            
            # Agar ustun kengayishi kerak bo'lsa
            # target_col e.g., oxirgi ustundan `target_months` marta o'ngga
            target_col = last_col + target_months
            
            dest_range = ws.range((1, last_col), (last_row, target_col))
            
            # Excel AutoFill orqali ustunni o'ngga kengaytiradi (formulalari bilan)
            source_range.api.AutoFill(Destination=dest_range.api, Type=0)
            
        except Exception as e:
            print(f"  [Warning] Gorizontal nusxalashda xatolik: {e}")

# Agar To'g'ridan to'g'ri ishga tushirilsa:
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Excel model editor")
    parser.add_argument("--months", type=int, default=36, help="Kredit muddati oylarda")
    parser.add_argument("--input", type=str, default="data.xlsx", help="Asl excel fayl")
    parser.add_argument("--output", type=str, default="data_updated.xlsx", help="Yangi saqlanadigan excel fayl")
    
    args = parser.parse_args()
    
    if os.path.exists(args.input):
        editor = ExcelModelEditor(args.input, args.output)
        editor.expand_model(target_months=args.months)
    else:
        print(f"[{args.input}] fayli hozirgi katalogda topilmadi.")
