import os

def fix_variable():
    file_path = r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\src\fetchers\mavi_whap.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = content.replace('"{message_body}"', '"{chunk}"')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed variable name in prompt.")

if __name__ == "__main__":
    fix_variable()
