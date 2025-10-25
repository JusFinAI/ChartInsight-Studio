# inspect_dart_all_reports.py
import os, requests
DART_API_KEY = os.getenv('DART_API_KEY') or "<PUT_KEY_IF_LOCAL>"
BASE = "https://opendart.fss.or.kr/api"

def fetch(corp_code, year, reprt_code):
    url = f"{BASE}/fnlttSinglAcntAll.json"
    params = {"crtfc_key": DART_API_KEY, "corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": "CFS"}
    r = requests.get(url, params=params, timeout=30)
    try:
        data = r.json()
    except Exception as e:
        print("JSON parse error:", e); return []
    return data.get("list") or []

if __name__ == "__main__":
    corp = "00126380"   # 검사할 corp_code(8자리)
    years = [2025, 2024, 2023, 2022]
    reprts = ["11011","11014","11012","11013"]
    for year in years:
        for rcode in reprts:
            items = fetch(corp, year, rcode)
            print(f"{year}/{rcode} -> {len(items)} items")
            if items:
                ids = {}
                for it in items:
                    aid = it.get("account_id") or it.get("accountId") or "<no_id>"
                    ids.setdefault(aid, 0); ids[aid]+=1
                top = sorted(ids.items(), key=lambda x:-x[1])[:20]
                for k,v in top:
                    print(f"  {k}: {v}")
                # print one net-income sample if exists
                tgt = "ifrs-full_ProfitLossAttributableToOwnersOfParent"
                if tgt in ids:
                    for it in items:
                        if it.get("account_id")==tgt:
                            print("  sample:", {k:it.get(k) for k in ["bsns_year","reprt_code","account_id","thstrm_amount"]})
                            break
    print("Done")