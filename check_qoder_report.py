import os
import time
import json

# 监控文件路径
RESULT_FILE = r"D:\project\hotclaw\RESULT.md"
STATE_FILE = r"D:\project\hotclaw\.qoder\report_state.json"

def check_qoder_report():
    """检查 Qoder 报告是否有更新"""
    if not os.path.exists(RESULT_FILE):
        return None
    
    # 读取当前文件修改时间
    current_mtime = os.path.getmtime(RESULT_FILE)
    
    # 读取上次状态
    last_mtime = 0
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
                last_mtime = state.get('last_mtime', 0)
        except:
            pass
    
    # 检查是否有更新
    if current_mtime > last_mtime:
        # 读取报告内容
        with open(RESULT_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 保存新状态
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'last_mtime': current_mtime, 'last_check': time.time()}, f)
        
        return content
    
    return None

if __name__ == "__main__":
    result = check_qoder_report()
    if result:
        print("=== QODER 报告有更新 ===")
        print(result)
    else:
        print("NO_UPDATE")
