# ī�װ����� ƼĿ ������ ���� 

# 카테고리와 티커 데이터 정의

# 카테고리 옵션
CATEGORY_OPTIONS = ['지수', '한국주식', '미국주식', '해외선물', '코인']

# 카테고리별 심볼 데이터
SYMBOLS_BY_CATEGORY = {
    '지수': [
        {'value': '^KS11', 'label': 'KOSPI'},
        {'value': '^KQ11', 'label': 'KOSDAQ'},
        {'value': '^GSPC', 'label': 'S&P 500'},
        {'value': '^DJI', 'label': 'Dow Jones'},
        {'value': '^IXIC', 'label': 'NASDAQ'},
        {'value': '^N225', 'label': 'Nikkei 225'},
        {'value': '^HSI', 'label': 'Hang Seng'},
        {'value': '^FTSE', 'label': 'FTSE 100'},
        {'value': '^GDAXI', 'label': 'DAX'}
    ],
    '한국주식': [
        {'value': '005930.KS', 'label': '삼성전자'},
        {'value': '000660.KS', 'label': 'SK하이닉스'},
        {'value': '035420.KS', 'label': 'NAVER'},
        {'value': '035720.KS', 'label': '카카오'},
        {'value': '051910.KS', 'label': 'LG화학'},
        {'value': '005380.KS', 'label': '현대차'},
        {'value': '006400.KS', 'label': '삼성SDI'},
        {'value': '000270.KS', 'label': '기아'},
        {'value': '068270.KS', 'label': '셀트리온'},
        {'value': '207940.KS', 'label': '삼성바이오로직스'},
        {'value': '323410.KS', 'label': '카카오뱅크'},
        {'value': '005490.KS', 'label': 'POSCO홀딩스'},
        {'value': '003550.KS', 'label': 'LG'},
        {'value': '009150.KS', 'label': '삼성전기'},
        {'value': '018260.KS', 'label': '삼성에스디에스'},
        {'value': '015760.KS', 'label': '한국전력'},
        {'value': '034730.KS', 'label': 'SK'},
        {'value': '096770.KS', 'label': 'SK이노베이션'},
        {'value': '066570.KS', 'label': 'LG전자'},
        {'value': '017670.KS', 'label': 'SK텔레콤'}
    ],
    '미국주식': [
        {'value': 'AAPL', 'label': 'Apple'},
        {'value': 'MSFT', 'label': 'Microsoft'},
        {'value': 'GOOGL', 'label': 'Alphabet (Google)'},
        {'value': 'AMZN', 'label': 'Amazon'},
        {'value': 'META', 'label': 'Meta (Facebook)'},
        {'value': 'NVDA', 'label': 'NVIDIA'},
        {'value': 'TSLA', 'label': 'Tesla'},
        {'value': 'NFLX', 'label': 'Netflix'},
        {'value': 'JPM', 'label': 'JPMorgan Chase'},
        {'value': 'V', 'label': 'Visa'},
        {'value': 'WMT', 'label': 'Walmart'},
        {'value': 'BAC', 'label': 'Bank of America'},
        {'value': 'PG', 'label': 'Procter & Gamble'},
        {'value': 'DIS', 'label': 'Disney'},
        {'value': 'KO', 'label': 'Coca-Cola'}
    ],
    '해외선물': [
        {'value': 'GC=F', 'label': '금(Gold)'},
        {'value': 'SI=F', 'label': '은(Silver)'},
        {'value': 'CL=F', 'label': '원유(Crude Oil)'},
        {'value': 'NG=F', 'label': '천연가스(Natural Gas)'},
        {'value': 'ZC=F', 'label': '옥수수(Corn)'},
        {'value': 'ZW=F', 'label': '밀(Wheat)'},
        {'value': 'NQ=F', 'label': '나스닥 선물(NASDAQ)'},
        {'value': 'ES=F', 'label': 'S&P 500 선물'},
        {'value': 'YM=F', 'label': '다우 선물(Dow)'}
    ],
    '코인': [
        {'value': 'BTC-USD', 'label': '비트코인(BTC)'},
        {'value': 'ETH-USD', 'label': '이더리움(ETH)'},
        {'value': 'XRP-USD', 'label': '리플(XRP)'},
        {'value': 'SOL-USD', 'label': '솔라나(SOL)'},
        {'value': 'ADA-USD', 'label': '카르다노(ADA)'}
    ]
}

# 기본 카테고리와 티커
DEFAULT_CATEGORY = '코인'
DEFAULT_TICKER = 'BTC-USD' 
