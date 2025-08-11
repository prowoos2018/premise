#!/usr/bin/env python3
# services/selenium_service.py

import time
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    UnexpectedAlertPresentException,
    NoAlertPresentException,
    TimeoutException
)
import platform


class PurchaseAutomator:
    def __init__(self, headless: bool = True):
        options = webdriver.ChromeOptions()

        # 브라우저 바이너리 위치 설정
        if platform.system() == "Darwin":
            options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        else:
            options.binary_location = "/usr/bin/google-chrome-stable"

        # Headless 설정
        if headless:
            options.add_argument("--headless")                      # 표준 헤드리스 모드
            options.add_argument("--disable-gpu")                   # GPU 사용 중지
            options.add_argument("--window-size=1920,1080")         # 뷰포트 크기 지정
            options.add_argument("--remote-debugging-port=9222")    # DevTools 포트 고정
        else:
            options.add_argument("--window-size=1920,1080")         # 화면 모드에서도 크기 지정

        # 공통 옵션
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        # 이미지 로딩 비활성화
        options.add_experimental_option(
            "prefs", {"profile.managed_default_content_settings.images": 2}
        )

        print("[PurchaseAutomator] ▶ 드라이버 설치 시작", flush=True)
        path = ChromeDriverManager().install()
        print(f"[PurchaseAutomator] ✔ 드라이버 설치 완료: {path}", flush=True)

        service = Service(path, service_args=["--read-timeout=300"])
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 30)
        print("[PurchaseAutomator] ▶ WebDriver 초기화 완료", flush=True)

    def purchase(self, name: str, phone: str, email: str) -> str:
        print("[purchase] ▶ 시작: 상품 페이지 접속", flush=True)
        self.driver.get("https://prewoos-youtube.imweb.me/class/?idx=2")
        print(f"[purchase] ✔ 페이지 로드 완료, URL={self.driver.current_url}", flush=True)

        # 1) 구매하기 클릭
        buy_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.buy.bg-brand._btn_buy")))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", buy_btn)
        self.driver.execute_script("arguments[0].click();", buy_btn)
        print("[purchase] ✔ 구매하기 클릭 성공", flush=True)

        # 2) 비회원 주문 클릭
        try:
            # 기존 셀렉터 시도
            guest_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn._guest_payment"))
            )
        except TimeoutException:
            # CSS가 바뀌었을 때를 대비해, 링크 텍스트로도 시도
            guest_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '비회원 주문')]"))
            )
        self.driver.execute_script("arguments[0].scrollIntoView(true);", guest_btn)
        self.driver.execute_script("arguments[0].click();", guest_btn)
        print("[purchase] ✔ 비회원 주문 클릭 성공", flush=True)

        # 3) order_no 대기 및 추출
        prev_url = self.driver.current_url
        self.wait.until(lambda d: d.current_url != prev_url)
        qs = parse_qs(urlparse(self.driver.current_url).query)
        order_no = qs.get("order_no", [None])[0]
        print(f"[purchase] ✔ order_no 추출: {order_no}", flush=True)

        # 4) 폼 입력
        name_input = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[placeholder='이름']")))
        name_input.send_keys(name)
        self.driver.find_element(By.CSS_SELECTOR, "input[placeholder='연락처']").send_keys(phone)
        self.driver.find_element(By.CSS_SELECTOR, "input[placeholder='이메일']").send_keys(email)
        print("[purchase] ✔ 폼 입력 완료", flush=True)
        time.sleep(3)  # 잠시 대기
         # —————— 수정된 동의 체크 로직 ——————
        print("[purchase] ▶ 필수 동의 체크 시작", flush=True)

        # 1) 개인정보 수집 및 이용 동의 클릭
        privacy_span = self.wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//label[contains(., '개인정보 수집 및 이용 동의')]//span[text()='개인정보 수집 및 이용 동의']"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", privacy_span)
        self.driver.execute_script("arguments[0].click();", privacy_span)
        privacy_input = self.driver.find_element(
            By.XPATH,
            "//label[contains(., '개인정보 수집 및 이용 동의')]//input[@type='checkbox']"
        )
        self.wait.until(lambda d: privacy_input.is_selected())
        print("[purchase] ✔ 개인정보 수집 및 이용 동의 체크 완료", flush=True)

         # 2) 구매조건 확인 및 결제진행에 동의 클릭
        agree_span = self.wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//label[contains(., '구매조건 확인 및 결제진행에 동의')]//span[text()='구매조건 확인 및 결제진행에 동의']"
        )))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", agree_span)
        self.driver.execute_script("arguments[0].click();", agree_span)
        agree_input = self.driver.find_element(
            By.XPATH,
            "//label[contains(., '구매조건 확인 및 결제진행에 동의')]//input[@type='checkbox']"
        )
        self.wait.until(lambda d: agree_input.is_selected())
        print("[purchase] ✔ 구매조건 확인 및 결제진행에 동의 체크 완료", flush=True)
        # ————————————————————————————
        time.sleep(3)  # 잠시 대기
        # 5) 결제하기 클릭
        pay_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", pay_btn)
        self.driver.execute_script("arguments[0].click();", pay_btn)
        print("[purchase] ✔ 결제하기 클릭 성공", flush=True)

        # 결제 완료 페이지 대기
        final_url = self.driver.current_url
        try:
            self.wait.until(lambda d: d.current_url != final_url)
            print(f"[purchase] ✔ 결제 완료 페이지 감지: {self.driver.current_url}", flush=True)
        except TimeoutException:
            print("[purchase] ⚠ 결제 완료 페이지 이동 타임아웃", flush=True)

        print("[purchase] 🎉 주문 프로세스 완료", flush=True)
        return order_no
    

    def submit_review(self, order_no: str, phone: str, name: str, review: str):
        print("[submit_review] ▶ 시작: 리뷰 작성 페이지 진입 및 비회원 조회", flush=True)

        # 1) 메인 페이지 진입
        self.driver.get("https://prewoos-youtube.imweb.me/")

        # 2) 로그인(비회원 주문배송조회) 버튼 클릭
        login_span = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span.text.fixed_transform"))
        )
        login_span.click()
        guest_btn = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.non_btn"))
        )
        guest_btn.click()

        # 3) 주문번호 및 연락처 입력
        order_input = self.wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "input[placeholder='주문번호']"))
        )
        order_input.clear()
        order_input.send_keys(order_no)
        phone_input = self.driver.find_element(
            By.CSS_SELECTOR, "input[placeholder='연락처']"
        )
        phone_input.clear()
        phone_input.send_keys(phone)

        # 4) 로그인 버튼 클릭
        login_btn = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.btn-primary.w100p.h45"))
        )
        login_btn.click()

        # 초기 Alert 수용
        try:
            alert = self.driver.switch_to.alert
            print(f"[submit_review] ⚠ 초기 Alert: {alert.text}", flush=True)
            alert.accept()
        except NoAlertPresentException:
            pass

        # 5) '구매확정' 클릭 처리 및 대기 후 '구매평 작성' 클릭
        start = time.time()
        while True:
            # 안전 타임슬립으로 페이지 안정화
            time.sleep(2)
            try:
                btn = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.css-10r0tpb"))
                )
                text = btn.text.strip()
            except TimeoutException:
                print("[submit_review] ⚠ 버튼 탐색 실패, 재시도", flush=True)
                continue

            if text == "구매확정":
                print("[submit_review] ▶ 구매확정 클릭", flush=True)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView(true);arguments[0].click();", btn
                )
                # 팝업 처리
                try:
                    WebDriverWait(self.driver, 5).until(EC.alert_is_present())
                    confirm_alert = self.driver.switch_to.alert
                    print(f"[submit_review] ✔ 구매확정 팝업: {confirm_alert.text}", flush=True)
                    confirm_alert.accept()
                except TimeoutException:
                    print("[submit_review] ⚠ 구매확정 팝업 없음", flush=True)
                continue  # 다시 '구매평 작성' 버튼 대기

            elif text == "구매평 작성":
                print("[submit_review] ▶ 구매평 작성 클릭", flush=True)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView(true);arguments[0].click();", btn
                )
                print("[submit_review] ✔ 리뷰작성 진입 성공", flush=True)
                break
            else:
                print(f"[submit_review] ⚠ 예상치 못한 버튼 텍스트: '{text}', 재시도", flush=True)
                if time.time() - start > 60:
                    print("[submit_review] ❌ 버튼 클릭 타임아웃", flush=True)
                    return
                continue

        # 6) 리뷰작성 폼 입력
        nick_input = self.wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='nick']"))
        )
        nick_input.clear(); nick_input.send_keys(name)
        pw_input = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']"))
        )
        pw_input.clear(); pw_input.send_keys("1345")

        # 7) 리뷰본문 입력 및 알림 처리
        start_body = time.time()
        while True:
            try:
                body = self.driver.find_element(By.ID, "review_modal_body")
                body.clear(); body.send_keys(review)
                print("[submit_review] ✔ 리뷰 폼 입력 완료", flush=True)
                break
            except UnexpectedAlertPresentException:
                alert = self.driver.switch_to.alert
                print(f"[submit_review] ⚠ 알림: {alert.text}", flush=True)
                alert.accept()
                time.sleep(1)
                continue
            except Exception as e:
                print(f"[submit_review] ⚠ 폼 입력 실패: {e}, 재시도", flush=True)
                if time.time() - start_body > 30:
                    print("[submit_review] ❌ 폼 입력 타임아웃", flush=True)
                    return
                time.sleep(1)

        # 8) 리뷰 등록 및 최종 팝업 수용
        submit_start = time.time()
        while True:
            try:
                submit_btn = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-lg.full-width.btn_submit"))
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView(true);arguments[0].click();", submit_btn
                )
                print("[submit_review] ▶ 리뷰 등록 클릭", flush=True)
                break
            except UnexpectedAlertPresentException:
                late_alert = self.driver.switch_to.alert
                print(f"[submit_review] ⚠ 알림: {late_alert.text}", flush=True)
                late_alert.accept()
                continue
            except TimeoutException:
                print("[submit_review] ⚠ 리뷰 등록 버튼 탐색 실패, 재시도", flush=True)
                if time.time() - submit_start > 30:
                    print("[submit_review] ❌ 리뷰 등록 타임아웃", flush=True)
                    return
                time.sleep(1)

        try:
            WebDriverWait(self.driver, 5).until(EC.alert_is_present())
            final_alert = self.driver.switch_to.alert
            final_alert.accept()
        except TimeoutException:
            pass

        # 9) 완료 모달 '확인' 클릭
        try:
            ok_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[text()='확인' and @data-dismiss='modal']"))
            )
            self.driver.execute_script("arguments[0].click();", ok_btn)
            print("[submit_review] ✔ 완료 모달 '확인' 클릭", flush=True)
        except TimeoutException:
            print("[submit_review] ⚠ 완료 모달 '확인' 없음", flush=True)

        # 함수 종료
        return

    def close(self):
        print("[PurchaseAutomator] ▶ WebDriver 종료", flush=True)
        self.driver.quit()
