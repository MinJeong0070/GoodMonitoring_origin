import requests
from bs4 import BeautifulSoup

def get_naver_news_agency_ids():
    url = "https://news.naver.com/main/officeList.naver"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()  # 오류 시 예외 발생

    soup = BeautifulSoup(response.text, 'html.parser')

    agency_dict = {}

    # 언론사 목록은 a 태그로 구성됨
    for a in soup.select('a[href*="officeId="]'):
        href = a.get('href')
        name = a.get_text(strip=True)
        if not href or 'officeId=' not in href:
            continue

        office_id = href.split('officeId=')[-1].split('&')[0]
        agency_dict[name] = office_id

    return agency_dict

# 사용 예
if __name__ == "__main__":
    agencies = get_naver_news_agency_ids()
    for name, office_id in list(agencies.items()):  # 상위 10개 예시 출력
        print(f"{name}: {office_id}")
    print(len(agencies.items()))
