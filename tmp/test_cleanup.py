import os
from src.services.data_service import DataService
from src.utils.file_ops import backup_file, _cleanup_old_temp_files

def test():
    data_dir = os.path.join(os.getcwd(), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # 1. Test backup_file is disabled
    test_file = os.path.join(data_dir, 'test_file.txt')
    with open(test_file, 'w') as f:
        f.write("test")
        
    res = backup_file(test_file)
    print(f"backup_file result: {res}")
    
    bak_files = [f for f in os.listdir(data_dir) if f.startswith('test_file') and f.endswith('.bak')]
    if bak_files:
        print("❌ FAIL: backup file was created!")
    else:
        print("✅ PASS: backup file was NOT created.")
        
    # 2. Test cleanup function
    dummy_bak = os.path.join(data_dir, 'dummy.bak')
    dummy_tmp = os.path.join(data_dir, 'dummy.tmp')
    
    with open(dummy_bak, 'w') as f: f.write("bak")
    with open(dummy_tmp, 'w') as f: f.write("tmp")
    
    print("Files exist before cleanup:", os.path.exists(dummy_bak), os.path.exists(dummy_tmp))
    print("Running cleanup...")
    _cleanup_old_temp_files(data_dir)
    print("Files exist after cleanup:", os.path.exists(dummy_bak), os.path.exists(dummy_tmp))
    
    if not os.path.exists(dummy_bak) and not os.path.exists(dummy_tmp):
        print("✅ PASS: Cleanup successfully deleted .bak and .tmp files.")
    else:
        print("❌ FAIL: Cleanup did not delete the files.")
        
    # Clean up test file
    if os.path.exists(test_file): os.remove(test_file)

if __name__ == '__main__':
    test()
