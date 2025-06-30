import os

# UTF-8 코드페이지로 전환
os.system("chcp 65001 > NUL")

# 크롬과 크롬드라이버 강제 종료
os.system("taskkill /f /im chrome.exe")
os.system("taskkill /f /im chromedriver.exe")
