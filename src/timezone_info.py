from datetime import datetime, timedelta


AIRPORT_TIME_DIFF_FROM_KST = {
    # =========================================================
    # 기준: KST(한국 UTC+9) 대비 현지 시간 차이
    # 예: -1 = 한국보다 1시간 느림 / +1 = 한국보다 1시간 빠름
    # 주의: 유럽·북미 일부는 2026년 6월 기준 여름시간(DST) 반영
    # =========================================================

    # Korea / Domestic
    "ICN": 0,
    "GMP": 0,
    "PUS": 0,
    "CJU": 0,
    "TAE": 0,
    "CJJ": 0,
    "MWX": 0,
    "KWJ": 0,
    "RSU": 0,
    "USN": 0,
    "WJU": 0,
    "YNY": 0,

    # Japan
    "NRT": 0,
    "HND": 0,
    "KIX": 0,
    "ITM": 0,
    "NGO": 0,
    "FUK": 0,
    "CTS": 0,
    "OKA": 0,
    "KMJ": 0,
    "KOJ": 0,
    "KMQ": 0,
    "KIJ": 0,
    "SDJ": 0,
    "HIJ": 0,
    "OKJ": 0,
    "TAK": 0,
    "MYJ": 0,
    "OIT": 0,
    "KKJ": 0,
    "HSG": 0,
    "ASJ": 0,
    "YGJ": 0,
    "IWK": 0,
    "TKS": 0,
    "MMY": 0,
    "ISG": 0,

    # China / Hong Kong / Macau / Taiwan
    "PEK": -1,
    "PKX": -1,
    "PVG": -1,
    "SHA": -1,
    "CAN": -1,
    "SZX": -1,
    "XMN": -1,
    "FOC": -1,
    "HGH": -1,
    "NKG": -1,
    "TAO": -1,
    "YNT": -1,
    "DLC": -1,
    "SHE": -1,
    "HRB": -1,
    "CGQ": -1,
    "TSN": -1,
    "CKG": -1,
    "CTU": -1,
    "TFU": -1,
    "KMG": -1,
    "WUH": -1,
    "CSX": -1,
    "CGO": -1,
    "XIY": -1,
    "TYN": -1,
    "HFE": -1,
    "WUX": -1,
    "YIW": -1,
    "NGB": -1,
    "HAK": -1,
    "SYX": -1,
    "URC": -1,
    "LHW": -1,
    "NNG": -1,
    "KHN": -1,
    "WNZ": -1,
    "HET": -1,
    "JJN": -1,
    "INC": -1,

    "HKG": -1,
    "MFM": -1,

    "TPE": -1,
    "TSA": -1,
    "KHH": -1,
    "RMQ": -1,

    # Mongolia
    "UBN": -1,
    "ULN": -1,

    # Southeast Asia - UTC+8
    "SIN": -1,
    "KUL": -1,
    "PEN": -1,
    "BKI": -1,
    "KCH": -1,

    "MNL": -1,
    "CEB": -1,
    "CRK": -1,
    "KLO": -1,
    "DVO": -1,
    "TAG": -1,

    "BWN": -1,

    "DPS": -1,

    # Southeast Asia - UTC+7
    "BKK": -2,
    "DMK": -2,
    "HKT": -2,
    "CNX": -2,
    "KBV": -2,

    "HAN": -2,
    "SGN": -2,
    "DAD": -2,
    "CXR": -2,
    "PQC": -2,
    "HPH": -2,

    "PNH": -2,
    "REP": -2,
    "SAI": -2,

    "VTE": -2,
    "LPQ": -2,

    "CGK": -2,
    "SUB": -2,
    "JOG": -2,
    "LOP": -1,

    # Myanmar
    "RGN": -2.5,
    "MDL": -2.5,

    # South Asia
    "DAC": -3,
    "KTM": -3.25,

    "DEL": -3.5,
    "BOM": -3.5,
    "MAA": -3.5,
    "BLR": -3.5,
    "HYD": -3.5,
    "CCU": -3.5,
    "AMD": -3.5,
    "COK": -3.5,

    "CMB": -3.5,
    "MLE": -4,

    "ISB": -4,
    "LHE": -4,
    "KHI": -4,

    # Central Asia
    "TAS": -4,
    "SKD": -4,
    "ALA": -4,
    "NQZ": -4,
    "CIT": -4,
    "FRU": -3,
    "OSS": -3,
    "DYU": -4,
    "ASB": -4,

    # Middle East / West Asia
    "DXB": -5,
    "AUH": -5,
    "SHJ": -5,
    "MCT": -5,

    "DOH": -6,
    "BAH": -6,
    "KWI": -6,
    "RUH": -6,
    "JED": -6,
    "DMM": -6,
    "MED": -6,

    "IST": -6,
    "SAW": -6,
    "ESB": -6,
    "AYT": -6,

    "TLV": -6,
    "AMM": -6,
    "BEY": -6,

    "IKA": -5.5,
    "THR": -5.5,

    "GYD": -5,
    "EVN": -5,
    "TBS": -5,

    # Russia / Far East / Siberia / Moscow area
    "VVO": 1,
    "KHV": 1,
    "UUS": 2,
    "PKC": 3,
    "YKS": 0,
    "IKT": -1,
    "OVB": -2,
    "KJA": -2,
    "SVX": -4,
    "SVO": -6,
    "DME": -6,
    "VKO": -6,
    "LED": -6,

    # Europe - UK / Ireland / Portugal, summer time 기준 UTC+1
    "LHR": -8,
    "LGW": -8,
    "STN": -8,
    "MAN": -8,
    "EDI": -8,
    "DUB": -8,
    "LIS": -8,
    "OPO": -8,

    # Europe - Central Europe, summer time 기준 UTC+2
    "CDG": -7,
    "ORY": -7,
    "FRA": -7,
    "MUC": -7,
    "DUS": -7,
    "BER": -7,
    "HAM": -7,
    "STR": -7,

    "AMS": -7,
    "BRU": -7,
    "ZRH": -7,
    "GVA": -7,
    "VIE": -7,
    "PRG": -7,
    "BUD": -7,
    "WAW": -7,
    "KRK": -7,

    "CPH": -7,
    "ARN": -7,
    "OSL": -7,

    "FCO": -7,
    "MXP": -7,
    "LIN": -7,
    "VCE": -7,
    "BCN": -7,
    "MAD": -7,
    "PMI": -7,

    # Europe - Eastern Europe / Greece / Finland, summer time 기준 UTC+3
    "HEL": -6,
    "RIX": -6,
    "TLL": -6,
    "VNO": -6,
    "ATH": -6,
    "SKG": -6,
    "OTP": -6,
    "SOF": -6,
    "LCA": -6,

    # Africa
    "CAI": -6,
    "ADD": -6,
    "NBO": -6,
    "JNB": -7,
    "CPT": -7,
    "CMN": -8,
    "RAK": -8,
    "TUN": -8,
    "ALG": -8,
    "MRU": -5,
    "SEZ": -5,

    # North America - Pacific Time, summer time 기준 UTC-7
    "LAX": -16,
    "SFO": -16,
    "SEA": -16,
    "SAN": -16,
    "LAS": -16,
    "PDX": -16,
    "YVR": -16,

    # North America - Mountain Time, summer time 기준 UTC-6
    "DEN": -15,
    "SLC": -15,
    "YYC": -15,
    "YEG": -15,
    "PHX": -16,

    # North America - Central Time, summer time 기준 UTC-5
    "ORD": -14,
    "DFW": -14,
    "IAH": -14,
    "MSP": -14,
    "AUS": -14,
    "SAT": -14,
    "MEX": -15,
    "MTY": -15,

    # North America - Eastern Time, summer time 기준 UTC-4
    "JFK": -13,
    "EWR": -13,
    "BOS": -13,
    "IAD": -13,
    "DCA": -13,
    "ATL": -13,
    "DTW": -13,
    "MIA": -13,
    "MCO": -13,
    "TPA": -13,
    "CLT": -13,
    "PHL": -13,
    "YYZ": -13,
    "YUL": -13,
    "YOW": -13,

    # Hawaii / Alaska / Guam / Pacific Islands
    "HNL": -19,
    "ANC": -17,
    "GUM": 1,
    "SPN": 1,
    "ROR": 0,
    "PNI": 2,
    "TKK": 1,
    "MAJ": 3,

    # Oceania
    "SYD": 1,
    "MEL": 1,
    "BNE": 1,
    "OOL": 1,
    "PER": -1,
    "ADL": 0.5,
    "CBR": 1,
    "CNS": 1,
    "DRW": 0.5,

    "AKL": 3,
    "CHC": 3,
    "WLG": 3,
    "ZQN": 3,

    "NAN": 3,
    "SUV": 3,
    "PPT": -19,
    "POM": 1,
    }


def build_time_difference_summary(airport_code: str | None) -> str:
    if not airport_code:
        return "시차 정보를 확인할 수 없습니다."

    code = airport_code.upper()

    if code not in AIRPORT_TIME_DIFF_FROM_KST:
        return f"{code} 공항의 시차 정보가 아직 등록되어 있지 않습니다."

    diff = AIRPORT_TIME_DIFF_FROM_KST[code]

    if diff == 0:
        return f"{code} 기준 현지 시각은 한국과 같습니다."

    if diff < 0:
        return f"{code} 기준 현지 시각은 한국보다 {abs(diff)}시간 느립니다."

    return f"{code} 기준 현지 시각은 한국보다 {diff}시간 빠릅니다."


def convert_kst_to_destination_time(kst_datetime_text: str, airport_code: str | None) -> str:
    """
    예: 2026-06-12 09:35 + YYZ(-13)
    → 현지 예상 시각 2026-06-11 20:35
    """
    if not airport_code:
        return "현지 시각을 계산할 수 없습니다."

    code = airport_code.upper()

    if code not in AIRPORT_TIME_DIFF_FROM_KST:
        return f"{code} 공항의 현지 시각 계산 정보를 아직 등록하지 않았습니다."

    try:
        kst_dt = datetime.strptime(kst_datetime_text, "%Y-%m-%d %H:%M")
        destination_dt = kst_dt + timedelta(hours=AIRPORT_TIME_DIFF_FROM_KST[code])

        return (
            f"한국 출발 예정 시간 기준 현지 시각: "
            f"{destination_dt.strftime('%Y-%m-%d %H:%M')}"
        )

    except Exception:
        return "출발 시간 형식이 맞지 않아 현지 시각을 계산할 수 없습니다."