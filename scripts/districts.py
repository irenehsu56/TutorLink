import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
import truststore

# 使用系統憑證信任設定
truststore.inject_into_ssl()

# HTML 使用的縣市 value
CITY_KEYS = [
    "taipei", "new-taipei", "keelung", "taoyuan",
    "hsinchu-city", "hsinchu-county", "yilan", "miaoli",
    "taichung", "changhua", "nantou", "yunlin",
    "chiayi-city", "chiayi-county", "tainan", "kaohsiung",
    "pingtung", "hualien", "taitung", "penghu",
    "kinmen", "lienchiang"
]

# 對應政府 API 的縣市名稱
CITY_NAMES = [
    "臺北市", "新北市", "基隆市", "桃園市",
    "新竹市", "新竹縣", "宜蘭縣", "苗栗縣",
    "臺中市", "彰化縣", "南投縣", "雲林縣",
    "嘉義市", "嘉義縣", "臺南市", "高雄市",
    "屏東縣", "花蓮縣", "臺東縣", "澎湖縣",
    "金門縣", "連江縣"
]


def get_xml(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return ET.fromstring(response.read())


# 先取得政府縣市代碼
county_root = get_xml(
    "https://api.nlsc.gov.tw/other/ListCounty"
)

county_codes = {}

for item in county_root.findall(".//countyItem"):
    name = item.findtext("countyname")
    code = item.findtext("countycode")

    if name and code:
        county_codes[name] = code

# 依縣市取得鄉鎮市區
district_data = {}

for key, city_name in zip(CITY_KEYS, CITY_NAMES):
    code = county_codes.get(city_name)

    if not code:
        raise ValueError(f"找不到縣市代碼：{city_name}")

    url = f"https://api.nlsc.gov.tw/other/ListTown1/{code}"
    root = get_xml(url)

    districts = []

    for item in root.findall(".//townItem"):
        name = item.findtext("townname")

        if name and name not in districts:
            districts.append(name)

    if not districts:
        raise ValueError(f"{city_name} 沒有取得行政區資料")

    district_data[key] = districts
    print(f"{city_name}：{len(districts)} 個行政區")

# 全部成功後才覆寫 JSON
# 取得 TutorLink 專案根目錄
BASE_DIR = Path(__file__).resolve().parent.parent

# 將行政區 JSON 儲存到 static/data/
output_path = BASE_DIR / "static" / "data" / "districts.json"
output_path.parent.mkdir(parents=True, exist_ok=True)

with output_path.open("w", encoding="utf-8") as file:
    json.dump(
        district_data,
        file,
        ensure_ascii=False,
        indent=4
    )

print("完成！已產生 districts.json")
