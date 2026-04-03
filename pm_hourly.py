import os
import csv
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone, timedelta

def get_beijing_time():
    # 创建北京时间时区 (UTC+8)
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8)

def fetch_waqi_data():
    # [修复1. 凭据硬编码风险] - 已经使用环境变量读取 Token
    token = os.environ.get("WAQI_TOKEN")
    if not token:
        raise ValueError("未找到 WAQI_TOKEN 环境变量")

    url = f"https://api.waqi.info/feed/@466/?token={token}"
    
    # [修复4. 缺少网络重试机制] - 设置带有退避策略的重试
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # [修复5. 未设置 User-Agent] - 添加标准的 User-Agent Headers 防止被阻截
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = session.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    # [修复3. 时间解析与数据容错] 检查反序列化失败问题
    try:
        result = response.json()
    except ValueError as e:
        raise ValueError("API 响应不是有效的 JSON 格式") from e
    
    if result.get("status") != "ok":
        error_msg = result.get("data", "未知错误")
        raise RuntimeError(f"API 请求失败: {error_msg}")
        
    return result.get("data", {})

def save_data(data):
    # [需求: 爬取的数据时间为北京时间]
    now = get_beijing_time()
    
    # [需求: 按月建文件夹，按天存 CSV]
    month_folder = now.strftime("%Y-%m")
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # 构建目录: data/2026-04/
    dir_path = os.path.join("data", month_folder)
    os.makedirs(dir_path, exist_ok=True)
    
    # 构建CSV文件路径: data/2026-04/huairou_pm_2026-04-03.csv
    file_path = os.path.join(dir_path, f"huairou_pm_{date_str}.csv")
    
    # 从 data 里面提取字段并容错
    aqi = data.get("aqi", "")
    iaqi = data.get("iaqi", {})
    # 获取服务端给的发布时间，为空则用记录时间补充
    fetch_time = data.get("time", {}).get("s", f"{date_str} {time_str}")
    
    pm25 = iaqi.get("pm25", {}).get("v", "")
    pm10 = iaqi.get("pm10", {}).get("v", "")
    o3 = iaqi.get("o3", {}).get("v", "")
    no2 = iaqi.get("no2", {}).get("v", "")
    so2 = iaqi.get("so2", {}).get("v", "")
    co = iaqi.get("co", {}).get("v", "")
    temp = iaqi.get("t", {}).get("v", "")
    humidity = iaqi.get("h", {}).get("v", "")
    wind = iaqi.get("w", {}).get("v", "")

    # 定义 CSV 表头和数据行
    headers = [
        "record_time", "publish_time", "aqi", "pm25", "pm10", 
        "o3", "no2", "so2", "co", "temperature", "humidity", "wind"
    ]
    row = [
        f"{date_str} {time_str}", fetch_time, aqi, pm25, pm10, 
        o3, no2, so2, co, temp, humidity, wind
    ]

    file_exists = os.path.exists(file_path)
    
    # 使用 utf-8-sig (BOM) 防止 Excel 打开 CSV 中文乱码
    file_exists = os.path.exists(file_path)
    with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)
        
    print(f"[{date_str} {time_str}] 数据抓取保存成功(北京时间)！AQI: {aqi}，文件: {file_path}")

if __name__ == "__main__":
    # [修复2. 异常处理过宽] - 细分和处理具体的异常类型
    try:
        data = fetch_waqi_data()
        save_data(data)
    except requests.exceptions.RequestException as e:
        print(f"网络请求或重试失败: {e}")
        exit(1)
    except ValueError as e:
        print(f"数据解析错误: {e}")
        exit(1)
    except RuntimeError as e:
        print(f"API服务端返回错误: {e}")
        exit(1)
    except Exception as e:
        print(f"发生意外系统错误: {e}")
        exit(1)

