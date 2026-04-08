
# Find line number of _enable_mousewheel_scrolling
filename = r"c:\Users\YUSUF ÇİNAR\Desktop\projelerim\maviLojistik\src\gui\masaustu_uygulama.py"
try:
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "_enable_mousewheel_scrolling" in line and "def" in line:
            print(f"Found at line {i+1}: {line.strip()}")
except Exception as e:
    print(f"Error: {e}")
