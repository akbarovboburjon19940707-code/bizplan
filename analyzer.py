import re
import os

HTML_FILES = ["templates/index.html", "templates/landing.html", "templates/payment.html"]
JS_FILES = ["static/js/app.js", "static/js/payment.js"]

def analyze():
    # 1. Gather all IDs in HTML
    html_ids = set()
    html_classes = set()
    for h in HTML_FILES:
        if not os.path.exists(h): continue
        with open(h, 'r', encoding='utf-8') as f:
            content = f.read()
            html_ids.update(re.findall(r'id=["\']([^"\']+)["\']', content))
            classes = re.findall(r'class=["\']([^"\']+)["\']', content)
            for c in classes:
                html_classes.update(c.split())
                
    # 2. Gather all getElementById in JS
    js_ids_needed = set()
    js_classes_needed = set()
    for j in JS_FILES:
        if not os.path.exists(j): continue
        with open(j, 'r', encoding='utf-8') as f:
            content = f.read()
            js_ids_needed.update(re.findall(r'getElementById\([\'"]([^\'"]+)[\'"]\)', content))
            js_classes_needed.update(re.findall(r'querySelector\([\'"]\.([^\'"]+)[\'"]\)', content))
            js_classes_needed.update(re.findall(r'querySelectorAll\([\'"]\.([^\'"]+)[\'"]\)', content))
            
    # Check what JS requires but doesn't exist
    missing_ids = js_ids_needed - html_ids
    print("WARNING: IDs expected by JS but missing in HTML:", missing_ids)
    
if __name__ == "__main__":
    analyze()
