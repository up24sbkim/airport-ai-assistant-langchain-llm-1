import html
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from src.agent import AirportToolAgent
from src.planner import build_airport_plan
from src.schemas import FlightInput
from src.travel_time_api import get_driving_and_transit_minutes

from src.flight_api import get_departure_flight_info
from src.flight_summary import (
    build_flight_summary,
    build_shortest_route,
)
from src.destination_info import (
    get_destination_weather_from_icn,
    build_destination_weather_summary,
)


load_dotenv()

st.set_page_config(
    page_title="공항가는날",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');

:root {
  --airport-background: #f5f8ff;
  --airport-foreground: #0f1c3f;
  --airport-card: #ffffff;
  --airport-primary: #1d6fef;
  --airport-primary-dark: #0f47b5;
  --airport-secondary: #e8f0fd;
  --airport-muted: #64748b;
  --airport-border: rgba(29, 111, 239, 0.14);
  --airport-input: #f0f5ff;
}

html, body, [class*="css"] {
  font-family: 'Noto Sans KR', sans-serif;
}

.stApp {
  background: var(--airport-background);
  color: var(--airport-foreground);
}

.block-container {
  max-width: 1060px;
  padding-top: 0;
  padding-bottom: 0;
}

header[data-testid="stHeader"] {
  background: transparent;
}

#MainMenu, footer {
  visibility: hidden;
}

.figma-hero {
  width: 100vw;
  margin-left: calc(50% - 50vw);
  min-height: 535px;
  color: white;
  background:
    radial-gradient(ellipse 44% 35% at 82% 25%, rgba(255,255,255,0.14), transparent 70%),
    radial-gradient(ellipse 58% 42% at 18% 72%, rgba(255,255,255,0.12), transparent 75%),
    linear-gradient(160deg, #0f2d6b 0%, #1d6fef 46%, #5ba3f5 76%, #c7deff 100%);
}

.figma-hero-inner {
  max-width: 1012px;
  margin: 0 auto;
  padding: 72px 24px 170px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 44px;
}

.brand-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: rgba(255,255,255,0.2);
  border: 1px solid rgba(255,255,255,0.14);
  backdrop-filter: blur(8px);
  font-size: 19px;
}

.brand-name {
  color: rgba(255,255,255,0.94);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.hero-copy {
  max-width: 610px;
}

.hero-copy h1 {
  color: white;
  margin: 0 0 15px;
  font-size: clamp(2.45rem, 5vw, 3.8rem);
  line-height: 1.16;
  letter-spacing: -0.055em;
  font-weight: 800;
}

.hero-copy p {
  margin: 0;
  color: #dbeafe;
  font-size: 17px;
  line-height: 1.75;
}

div[data-testid="stForm"] {
  position: relative;
  z-index: 3;
  margin-top: -154px;
  margin-bottom: 66px;
  padding: 28px 30px 30px;
  border: 1px solid rgba(255,255,255,0.9);
  border-radius: 18px;
  background: rgba(255,255,255,0.98);
  box-shadow: 0 24px 65px rgba(15, 45, 107, 0.22);
}

div[data-testid="stForm"] h3 {
  color: var(--airport-foreground);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin-bottom: 3px;
}

div[data-testid="stForm"] label {
  color: var(--airport-foreground);
  font-size: 13px;
  font-weight: 600;
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
  background: var(--airport-input);
  border-color: var(--airport-border);
  border-radius: 10px;
}

.stTextInput input {
  background: var(--airport-input);
}

.stTextInput input,
.stDateInput input {
  color: var(--airport-foreground) !important;
  -webkit-text-fill-color: var(--airport-foreground) !important;
  caret-color: var(--airport-primary) !important;
}

.stTextInput input::placeholder,
.stDateInput input::placeholder {
  color: #94a3b8 !important;
  -webkit-text-fill-color: #94a3b8 !important;
  opacity: 1 !important;
}

div[data-testid="stForm"] div[data-testid="stCaptionContainer"],
div[data-testid="stForm"] div[data-testid="stCaptionContainer"] p {
  color: var(--airport-muted) !important;
}

div[data-testid="stForm"] div[data-testid="stRadio"] label p,
div[data-testid="stForm"] div[data-testid="stRadio"] label span,
div[data-testid="stForm"] div[data-testid="stCheckbox"] label p,
div[data-testid="stForm"] div[data-testid="stCheckbox"] label span {
  color: var(--airport-foreground) !important;
  -webkit-text-fill-color: var(--airport-foreground) !important;
}

.stButton > button,
.stFormSubmitButton > button {
  min-height: 46px;
  border-radius: 11px;
  border: 0;
  font-weight: 700;
}

.stFormSubmitButton > button {
  color: white;
  background: linear-gradient(135deg, var(--airport-primary), var(--airport-primary-dark));
  box-shadow: 0 9px 22px rgba(29,111,239,0.22);
}

.feature-label {
  color: var(--airport-muted);
  text-align: center;
  margin: 0 0 26px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 72px;
}

.feature-card {
  min-height: 150px;
  padding: 21px;
  border: 1px solid var(--airport-border);
  border-radius: 17px;
  background: white;
  box-shadow: 0 6px 20px rgba(15,28,63,0.04);
}

.feature-icon {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: var(--airport-primary);
  background: var(--airport-secondary);
  font-size: 20px;
  margin-bottom: 14px;
}

.feature-card h4 {
  color: var(--airport-foreground);
  font-size: 14px;
  margin: 0 0 6px;
}

.feature-card p {
  color: var(--airport-muted);
  font-size: 12px;
  line-height: 1.65;
  margin: 0;
}

.dashboard-header {
  width: 100vw;
  margin-left: calc(50% - 50vw);
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid var(--airport-border);
  background: rgba(255,255,255,0.88);
  backdrop-filter: blur(14px);
}

.dashboard-header-inner {
  max-width: 1012px;
  height: 58px;
  padding: 0 24px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dashboard-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--airport-foreground);
  font-size: 13px;
  font-weight: 700;
}

.flight-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-radius: 999px;
  color: var(--airport-primary);
  background: var(--airport-secondary);
  font-size: 12px;
  font-weight: 700;
}

.summary-heading {
  padding-top: 42px;
  margin-bottom: 22px;
}

.summary-kicker {
  color: var(--airport-primary);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 7px;
}

.flight-main-title {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin-bottom: 10px;
}


.summary-heading h2 {
  color: var(--airport-foreground);
  margin: 0 0 6px;
  font-size: 24px;
  letter-spacing: -0.035em;
}

.summary-heading p {
  color: var(--airport-muted);
  margin: 0;
  font-size: 13px;
}

div[data-testid="stMetric"] {
  min-height: 170px;
  padding: 24px;
  border: 1px solid var(--airport-border);
  border-radius: 18px;
  background: white;
  box-shadow: 0 5px 18px rgba(15,28,63,0.04);
}

div[data-testid="stMetric"] label {
  color: var(--airport-muted);
  font-size: 13px;
  font-weight: 600;
}

div[data-testid="stMetricValue"] {
  color: var(--airport-foreground);
  font-size: 42px;
  font-weight: 800;
  letter-spacing: -0.04em;
}

div[data-testid="column"]:first-child div[data-testid="stMetric"] {
  color: white;
  border: 0;
  background: linear-gradient(135deg, var(--airport-primary), var(--airport-primary-dark));
  box-shadow: 0 13px 30px rgba(29,111,239,0.22);
}

div[data-testid="column"]:first-child div[data-testid="stMetric"] label,
div[data-testid="column"]:first-child div[data-testid="stMetricValue"],
div[data-testid="column"]:first-child div[data-testid="stMetricDelta"] {
  color: white;
}


/* 결과 화면 상단 시간 카드: 여백과 숫자를 살짝 줄임 */
div[data-testid="stMetric"] {
  min-height: 136px !important;
  padding: 18px 24px !important;
}

div[data-testid="stMetric"] > div {
  gap: 0.25rem !important;
}

div[data-testid="stMetric"] label {
  font-size: 14px !important;
}

div[data-testid="stMetricValue"] {
  font-size: 38px !important;
  line-height: 1.05 !important;
}

div[data-testid="stMetricDelta"] {
  font-size: 15px !important;
}

.flight-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 10px;
  margin-bottom: 14px;
}

.flight-card {
  position: relative;
  border: 1px solid #d9e5ff;
  border-radius: 14px;
  padding: 14px 16px;
  background: #f8fbff;
}

.warning-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 12px;
}

.warning-item {
  padding: 16px 18px;
  border-radius: 10px;
  background: #fffbe6;
  color: #9a6500;
  font-size: 0.98rem;
  line-height: 1.6;
  font-weight: 500;
}

.departure-time-card {
  padding-top: 28px;
}

.time-change-badge {
  position: absolute;
  top: 10px;
  right: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  color: white;
  font-size: 0.75rem;
  font-weight: 800;
  line-height: 1;
}

.delay-badge {
  background: #ef4444;
  box-shadow: 0 4px 10px rgba(239, 68, 68, 0.22);
}

.early-badge {
  background: #2563eb;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.22);
}

.flight-card-label {
  color: #5f6b85;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}

.flight-card-value {
  color: #10214d;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.35;
  word-break: keep-all;
}

.flight-subbox {
  margin-top: 10px;
  padding: 14px 16px;
  border: 1px solid #e3eaf8;
  border-radius: 14px;
  background: #ffffff;
}

.flight-subbox-title {
  color: #243b6b;
  font-size: 14px;
  font-weight: 800;
  margin-bottom: 7px;
}

.flight-subbox-value {
  color: var(--airport-foreground);
  font-size: 15px;
  line-height: 1.65;
}

@media (max-width: 1024px) {
  .flight-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .flight-grid {
    grid-template-columns: 1fr;
  }
}

div[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--airport-border);
  border-radius: 18px;
  background: white;
  box-shadow: 0 5px 18px rgba(15,28,63,0.04);
}

div[data-testid="stVerticalBlockBorderWrapper"] h3 {
  color: var(--airport-foreground);
  font-size: 15px;
  font-weight: 700;
}

.route-line {
  padding: 6px 0 18px;
}

.route-stop {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--airport-foreground);
  font-size: 14px;
  font-weight: 600;
}

.route-dot {
  width: 11px;
  height: 11px;
  border: 3px solid var(--airport-primary);
  border-radius: 50%;
  background: white;
}

.route-connector {
  width: 1px;
  height: 28px;
  margin: 4px 0 4px 5px;
  background: #bfdbfe;
}

.route-option {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 9px;
  padding: 12px 13px;
  border-radius: 12px;
  background: #f4f7fd;
  color: var(--airport-foreground);
  font-size: 13px;
}

.route-option span:last-child {
  color: var(--airport-muted);
}

.chat-shell {
  margin-top: 68px;
  margin-bottom: 68px;
}

.chat-intro {
  margin-bottom: 18px;
}

.chat-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-icon {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  color: var(--airport-primary);
  background: var(--airport-secondary);
}

.chat-intro h3 {
  color: var(--airport-foreground);
  margin: 0 0 2px;
  font-size: 17px;
}

.chat-intro p {
  color: var(--airport-muted);
  margin: 0;
  font-size: 12px;
}

.chat-window-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 3px 0 12px;
  padding: 6px 10px;
  border-radius: 999px;
  color: var(--airport-primary);
  background: var(--airport-secondary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.chat-empty-space {
  min-height: 12px;
}

.chat-panel {
  min-height: 270px;
  max-height: 440px;
  overflow-y: auto;
  margin-top: 14px;
  padding: 18px;
  border: 1px solid #bfd6ff;
  border-radius: 16px;
  background: #eef4ff;
}

.chat-row {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  margin-bottom: 16px;
}

.chat-row.user {
  flex-direction: row-reverse;
}

.chat-avatar {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: var(--airport-primary);
  font-size: 14px;
  font-weight: 700;
}

.chat-row.user .chat-avatar {
  color: var(--airport-primary);
  border: 1px solid #bfd6ff;
  background: white;
}

.chat-bubble {
  max-width: 78%;
  padding: 11px 15px;
  border: 1px solid #d7e5ff;
  border-radius: 16px;
  color: var(--airport-foreground);
  background: white;
  font-size: 13px;
  line-height: 1.65;
  white-space: normal;
}

.chat-row.user .chat-bubble {
  color: white;
  border-color: var(--airport-primary);
  background: var(--airport-primary);
}

.tool-trace {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e3eaf8;
  color: #64748b;
  font-size: 11px;
  line-height: 1.5;
}

.chat-row.user .tool-trace {
  display: none;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-intro) {
  padding: 22px 24px 18px;
  border-color: #bfd6ff;
  border-radius: 19px;
  background: white;
  box-shadow: 0 12px 32px rgba(29,111,239,0.08);
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-intro)
div[data-testid="stButton"] button {
  height: 72px;
  min-height: 72px;
  padding: 10px 12px;
  border: 1px solid #c7dbff;
  border-radius: 14px;
  color: #1d6fef;
  background: #f8fbff;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.45;
  text-align: center;
  white-space: pre-line;
  word-break: keep-all;
  box-shadow: 0 6px 18px rgba(29, 111, 239, 0.08);
  transition: all 0.16s ease;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-intro)
div[data-testid="stButton"] button:hover {
  color: white;
  border-color: #1d6fef;
  background: #1d6fef;
  box-shadow: 0 8px 22px rgba(29, 111, 239, 0.18);
  transform: translateY(-1px);
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-intro)
div[data-testid="stButton"] button:active {
  transform: translateY(0);
  box-shadow: 0 4px 12px rgba(29, 111, 239, 0.14);
}

/* 채팅 입력 영역 전체 박스 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"]) {
  position: static;
  margin: 16px 0 0;
  padding: 11px 14px;
  border: 1px solid #bfd6ff;
  border-radius: 17px;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(29, 111, 239, 0.08);
}

/* 입력창 + 버튼 정렬 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
div[data-testid="stHorizontalBlock"] {
  align-items: center;
}

/* 입력창 전체 wrapper */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
div[data-baseweb="input"] {
  margin: 0 !important;
}

/* 입력창 박스 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
div[data-baseweb="input"] > div {
  height: 52px;
  border: 1px solid #d7e5ff !important;
  border-radius: 15px !important;
  background: #f8fbff !important;
  box-shadow: none !important;
}

/* 포커스 상태 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
div[data-baseweb="input"] > div:focus-within {
  border: 1.5px solid #1d6fef !important;
  box-shadow: 0 0 0 3px rgba(29, 111, 239, 0.10) !important;
}

/* 입력창 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"]) input {
  height: 52px;
  padding-left: 15px !important;
  color: #0f1c3f;
  font-size: 14px;
}

/* placeholder */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"]) input::placeholder {
  color: #9aa8bd;
}

/* Press Enter 문구 숨김 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
div[data-testid="InputInstructions"] {
  display: none !important;
}

/* 전송 버튼 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"]) button {
  height: 52px;
  min-height: 52px;
  border-radius: 15px !important;
  color: white;
  background: linear-gradient(135deg, #1d6fef, #0f47b5);
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 7px 18px rgba(29, 111, 239, 0.22);
}

/* 전송 버튼 hover */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"]) button:hover {
  color: white;
  background: linear-gradient(135deg, #0f62e6, #0d3f9e);
}

/* Streamlit 기본 빨간/파란 outline 제거 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
input {
  outline: none !important;
  box-shadow: none !important;
}

div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
div[data-baseweb="input"] {
  border: none !important;
  box-shadow: none !important;
}

/* 입력창 내부 여백 정리 */
div[data-testid="stForm"]:has(input[aria-label="메시지 입력"])
div[data-baseweb="input"] > div {
  margin: 0 !important;
}

.footer-wrap {
  width: 100vw;
  margin-left: calc(50% - 50vw);
  padding: 28px 24px;
  border-top: 1px solid var(--airport-border);
  background: #eef2fb;
}

.footer-inner {
  max-width: 1012px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  gap: 18px;
  color: var(--airport-muted);
  font-size: 12px;
}

.footer-inner strong {
  color: var(--airport-foreground);
}

@media (max-width: 760px) {
  .figma-hero-inner {
    padding-top: 54px;
    padding-bottom: 150px;
  }

  div[data-testid="stForm"] {
    margin-top: -136px;
    padding: 22px 18px;
  }

  .feature-grid {
    grid-template-columns: 1fr 1fr;
  }

  .footer-inner {
    flex-direction: column;
    text-align: center;
  }
}

@media (max-width: 480px) {
  .feature-grid {
    grid-template-columns: 1fr;
  }

  .hero-copy h1 {
    font-size: 2.35rem;
  }
}


/* 직접 만든 항공편 요약 박스: Streamlit border container 대신 사용 */
.flight-summary-card {
  width: 100%;
  box-sizing: border-box;
  margin: 0 0 24px;
  padding: 20px 20px 26px;
  border: 1px solid var(--airport-border);
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 5px 18px rgba(15,28,63,0.04);
  overflow: visible;
}

.flight-summary-card h3 {
  margin: 0 0 18px;
  color: var(--airport-foreground);
  font-size: 15px;
  font-weight: 800;
}

.flight-summary-card .flight-subbox:last-child {
  margin-bottom: 0;
}

/* 직접 만든 주의사항 박스: Streamlit border container 대신 사용 */
.warning-section {
  width: 100%;
  box-sizing: border-box;
  margin: 0 0 24px;
  padding: 20px 16px 28px;
  border: 1px solid var(--airport-border);
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 5px 18px rgba(15,28,63,0.04);
  overflow: visible;
}

.warning-section h3 {
  margin: 0 0 18px;
  color: var(--airport-foreground);
  font-size: 15px;
  font-weight: 800;
}

.warning-section .warning-list {
  margin-bottom: 0;
  padding-bottom: 0;
}

.warning-section .warning-item:last-child {
  margin-bottom: 0;
}

/* Streamlit markdown 내부 카드 잘림 방지 */
div[data-testid="stMarkdown"] div {
  box-sizing: border-box;
}

div[data-testid="stMarkdown"] {
  overflow: visible !important;
}

/* 항공편 입력 폼: 전체 여백 정리 */
div[data-testid="stForm"]:not(:has(input[aria-label="메시지 입력"])) {
  overflow: visible !important;
  padding-bottom: 30px !important;
  margin-bottom: 66px !important;
}

/* 항공편 입력 폼: 이동수단 라디오를 다른 입력칸과 같은 높이로 정렬 */
div[data-testid="stForm"]:not(:has(input[aria-label="메시지 입력"]))
div[data-testid="stRadio"] {
  height: auto !important;
  min-height: 0 !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  overflow: visible !important;
}

/* 이동수단 라벨: 다른 입력 라벨과 동일하게 */
div[data-testid="stForm"]:not(:has(input[aria-label="메시지 입력"]))
div[data-testid="stRadio"] > label {
  display: block !important;
  margin: 0 0 6px !important;
  padding: 0 !important;
  height: auto !important;
  line-height: 1.3 !important;
}

/* 라디오 버튼 줄만 입력창처럼 보이게 */
div[data-testid="stForm"]:not(:has(input[aria-label="메시지 입력"]))
div[data-testid="stRadio"] div[role="radiogroup"] {
  height: 42px !important;
  min-height: 42px !important;
  padding: 0 12px !important;
  margin: 0 !important;
  display: flex !important;
  align-items: center !important;
  gap: 16px !important;
  border: none !important;
  border-radius: 10px !important;
  background: var(--airport-input) !important;
  box-sizing: border-box !important;
  overflow: visible !important;
}

/* 라디오 항목 정렬 */
div[data-testid="stForm"]:not(:has(input[aria-label="메시지 입력"]))
div[data-testid="stRadio"] div[role="radiogroup"] label {
  display: flex !important;
  align-items: center !important;
  margin: 0 !important;
  padding: 0 !important;
  height: auto !important;
  line-height: 1.2 !important;
}

</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)


@st.cache_resource
def get_airport_agent():
    return AirportToolAgent()


def clear_plan():
    st.session_state.pop("airport_plan", None)
    st.session_state.pop("flight_input", None)
    st.session_state.pop("flight_info", None)
    st.session_state.pop("flight_api_summary", None)
    st.session_state.pop("destination_weather_summary", None)


def render_hero():
    st.markdown(
        """
        <section class="figma-hero">
          <div class="figma-hero-inner">
            <div class="brand-row">
              <div class="brand-icon">✈</div>
              <div class="brand-name">공항가는날</div>
            </div>
            <div class="hero-copy">
              <h1>공항 가는 날</h1>
              <p>
                항공편만 입력하면 공항 가는 날 필요한 정보를<br/>
                한 번에 정리해드려요.
              </p>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_flight_form():
    with st.form("flight_form"):
        st.markdown("### 항공편 정보 입력")
        st.caption(
            "항공편 번호와 출발 날짜를 기준으로 출국 준비 계획을 계산합니다."
        )

        row1_left, row1_right = st.columns(2)
        with row1_left:
            flight_no = st.text_input(
                "항공편 번호",
                value="KE713",
                placeholder="예: KE 713",
            )

        with row1_right:
            departure_date = st.date_input("출발 날짜")

        row2_left, row2_right = st.columns(2)
        with row2_left:
            start_place = st.text_input(
              "출발 위치",
              value="서울 강남구 반포동",
              placeholder="예: 서울 강남구 반포동",
            )

        with row2_right:
             preferred_transport = st.radio(
              "이동수단",
              ["대중교통", "자동차"],
              horizontal=True,
              )

        has_baggage = st.checkbox(
            "위탁 수하물 있음",
            value=True,
        )

        submitted = st.form_submit_button(
            "✈  출국 준비 확인하기",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    searchday = departure_date.strftime("%Y%m%d")
    airport = "인천공항"

    with st.spinner("항공편 정보를 조회하는 중..."):
        flight_info = get_departure_flight_info(flight_no, searchday)

    if flight_info is None:
        st.error("항공편 정보를 찾을 수 없습니다. 항공편명과 출발일을 다시 확인해주세요.")
        return

    flight_api_summary = build_flight_summary(flight_info)

    with st.spinner("출발지에서 공항까지 이동 시간을 계산하는 중..."):
        travel_time_result = get_driving_and_transit_minutes(
            origin=start_place,
            terminal=flight_info.terminal,
        )

    driving_minutes = travel_time_result.get("driving")
    transit_minutes = travel_time_result.get("transit")

    if preferred_transport == "자동차":
        travel_minutes = driving_minutes or transit_minutes or 90
    else:
        travel_minutes = transit_minutes or driving_minutes or 90

    try:
        destination_weather = get_destination_weather_from_icn(flight_info)
        destination_weather_summary = build_destination_weather_summary(destination_weather)
    except Exception:
        destination_weather_summary = "도착지 정보를 불러오지 못했습니다."

    api_departure_time = (
        flight_info.scheduled_time[-5:]
        if flight_info.scheduled_time and len(flight_info.scheduled_time) >= 5
        else "00:00"
    )

    flight_input = FlightInput(
        flight_no=flight_info.flight_id,
        departure_date=str(departure_date),
        departure_time=api_departure_time,
        airport=airport,
        destination=flight_info.destination,
        start_place=start_place,
        travel_minutes=travel_minutes,
        has_checked_baggage=has_baggage,
    )

    st.session_state.flight_input = flight_input
    st.session_state.flight_info = flight_info
    st.session_state.flight_api_summary = flight_api_summary
    st.session_state.destination_weather_summary = destination_weather_summary
    st.session_state.travel_time_result = {
        "driving": driving_minutes,
        "transit": transit_minutes,
        "selected": preferred_transport,
        "selected_minutes": travel_minutes,
        }
    st.session_state.airport_plan = build_airport_plan(flight_input)

    st.rerun()


def render_features():
    features = [
        ("◷", "출발 시간 계산", "공항 도착과 출발지 출발 시간을 입력값에 맞춰 계산해드려요."),
        ("⌖", "이동 경로 안내", "출발 위치와 예상 이동 시간을 한눈에 확인할 수 있어요."),
        ("▣", "수하물 체크리스트", "기내·위탁 수하물에서 놓치기 쉬운 항목을 정리해드려요."),
        ("☀", "목적지 준비", "목적지에 도착하기 전 필요한 준비 항목을 확인해요."),
        ("✈", "항공편 준비", "출발 날짜와 항공편을 기준으로 준비 계획을 만들어요."),
        ("◉", "AI 공항 도우미", "주차, 터미널, 수하물 등 궁금한 내용을 문서에서 찾아요."),
    ]
    cards = "".join(
        f"""
        <div class="feature-card">
          <div class="feature-icon">{icon}</div>
          <h4>{title}</h4>
          <p>{description}</p>
        </div>
        """
        for icon, title, description in features
    )
    st.markdown(
        f"""
        <p class="feature-label">공항가는날이 준비해드리는 것들</p>
        <section class="feature-grid">{cards}</section>
        """,
        unsafe_allow_html=True,
    )
def calculate_time_change_minutes(
    scheduled_time: str | None,
    estimated_time: str | None,
) -> int | None:
    if not scheduled_time or not estimated_time:
        return None

    if scheduled_time == "확인 필요" or estimated_time == "확인 필요":
        return None

    if scheduled_time == estimated_time:
        return None

    try:
        scheduled_dt = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")
        estimated_dt = datetime.strptime(estimated_time, "%Y-%m-%d %H:%M")
        diff_minutes = int((estimated_dt - scheduled_dt).total_seconds() // 60)

        if diff_minutes == 0:
            return None

        return diff_minutes

    except Exception:
        return None

def render_dashboard_header(flight_input):
    st.markdown(
        f"""
        <header class="dashboard-header">
          <div class="dashboard-header-inner">
            <div class="dashboard-brand">
              <span>✈</span>
              <span>공항가는날</span>
            </div>
            <div class="flight-pill">
              <span>{flight_input.flight_no}</span>
              <span>{flight_input.departure_time} 출발</span>
            </div>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )
    if st.button("← 다시 입력", key="reset-plan"):
        clear_plan()
        st.rerun()



def _format_departure_time_html(scheduled_time: str, estimated_time: str) -> str:
    if not scheduled_time or scheduled_time == "확인 필요":
        return "확인 필요"

    if not estimated_time or estimated_time == "확인 필요" or scheduled_time == estimated_time:
        return html.escape(scheduled_time)

    try:
        scheduled_date = scheduled_time[:10]
        scheduled_clock = scheduled_time[11:16]
        estimated_date = estimated_time[:10]
        estimated_clock = estimated_time[11:16]

        if scheduled_date == estimated_date:
            return f"{html.escape(scheduled_date)} <s>{html.escape(scheduled_clock)}</s> {html.escape(estimated_clock)}"

        return f"<s>{html.escape(scheduled_time)}</s> {html.escape(estimated_time)}"
    except Exception:
        return f"<s>{html.escape(scheduled_time)}</s> {html.escape(estimated_time)}"


def _safe_text(value, default: str = "확인 필요") -> str:
    if value is None or value == "":
        return html.escape(default)
    return html.escape(str(value))

def render_dashboard(flight_input, plan):
    render_dashboard_header(flight_input)

    st.markdown(
        f"""
        <section class="summary-heading">
          <div class="summary-kicker flight-main-title">✈ {html.escape(flight_input.flight_no)}</div>
          <h2>{html.escape(flight_input.start_place)} → {html.escape(flight_input.airport)} → {html.escape(flight_input.destination)}</h2>
          <p>{html.escape(flight_input.departure_date)} · 출발 {html.escape(flight_input.departure_time)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    time_left, time_right = st.columns(2)
    with time_left:
        st.metric(
            "공항 도착 권장 시간",
            plan.airport_arrival_time,
            "출발 3시간 전",
        )
    with time_right:
        st.metric(
            "출발지 출발 권장 시간",
            plan.leave_home_time,
            f"이동 약 {flight_input.travel_minutes}분",
        )

    travel_time_result = st.session_state.get("travel_time_result", {})
    
    if travel_time_result:
        driving_minutes = travel_time_result.get("driving")
        transit_minutes = travel_time_result.get("transit")
        selected = travel_time_result.get("selected")
        
        driving_text = f"{driving_minutes}분" if driving_minutes else "확인 필요"
        transit_text = f"{transit_minutes}분" if transit_minutes else "확인 필요"
        
        st.caption(
            f"이동시간 자동 계산: 자동차 {driving_text} · "
            f"대중교통 {transit_text} · 선택 기준 {selected}"
        )

    flight_info = st.session_state.get("flight_info")
    destination_weather_summary = st.session_state.get("destination_weather_summary")

    if flight_info:
        display_terminal = (
            "제1여객터미널 출국 후 탑승동 이동"
            if flight_info.terminal == "탑승동"
            else flight_info.terminal
        )
        departure_time_display = _format_departure_time_html(
            flight_info.scheduled_time,
            flight_info.estimated_time,
        )
        time_change_minutes = calculate_time_change_minutes(
            flight_info.scheduled_time,
            flight_info.estimated_time,
            )
        if time_change_minutes is None:
            time_change_badge_html = ""
        elif time_change_minutes > 0:
            time_change_badge_html = (
                f'<div class="time-change-badge delay-badge">'
                f'{time_change_minutes}분 지연'
                f'</div>'
                )
        else:
            time_change_badge_html = (
                f'<div class="time-change-badge early-badge">'
                f'{abs(time_change_minutes)}분 단축'
                f'</div>'
                )
        
        shortest_route = build_shortest_route(flight_info)

        st.markdown(
            f"""
            <section class="flight-summary-card">
              <h3>✈ 실시간 항공편 출국 요약</h3>
              <div class="flight-grid">
                <div class="flight-card">
                  <div class="flight-card-label">항공편</div>
                  <div class="flight-card-value">{_safe_text(flight_info.flight_id)}</div>
                </div>
                <div class="flight-card">
                  <div class="flight-card-label">항공사</div>
                  <div class="flight-card-value">{_safe_text(flight_info.airline)}</div>
                </div>
                <div class="flight-card">
                  <div class="flight-card-label">터미널</div>
                  <div class="flight-card-value">{_safe_text(display_terminal)}</div>
                </div>
                <div class="flight-card">
                  <div class="flight-card-label">목적지</div>
                  <div class="flight-card-value">{_safe_text(flight_info.destination)}({_safe_text(flight_info.destination_code)})</div>
                </div>
                <div class="flight-card departure-time-card">
                  {time_change_badge_html}
                  <div class="flight-card-label">출발 예정 시간</div>
                  <div class="flight-card-value">{departure_time_display}</div>
                </div>
                <div class="flight-card">
                  <div class="flight-card-label">체크인 카운터</div>
                  <div class="flight-card-value">{_safe_text(flight_info.checkin_counter)}</div>
                </div>
                <div class="flight-card">
                  <div class="flight-card-label">탑승구</div>
                  <div class="flight-card-value">{_safe_text(flight_info.gate)}</div>
                </div>
                <div class="flight-card">
                  <div class="flight-card-label">운항 상태</div>
                  <div class="flight-card-value">{_safe_text(flight_info.status)}</div>
                </div>
              </div>
              <div class="flight-subbox">
                <div class="flight-subbox-title">최단이동경로</div>
                <div class="flight-subbox-value">{_safe_text(shortest_route)}</div>
              </div>
              <div class="flight-subbox">
                <div class="flight-subbox-title">출국심사 후 예상 이동시간</div>
                <div class="flight-subbox-value">약 15분</div>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    if destination_weather_summary:
        with st.container(border=True):
            st.markdown("### 🌍 도착지 정보")
            st.markdown(destination_weather_summary)

        flight_warnings = [
        "탑승구와 체크인 카운터는 당일 변경될 수 있습니다.",
        "수하물 무게와 크기는 항공사 규정을 다시 확인하세요.",
        "운항 상태가 '탑승마감' 또는 '출발'인 경우 실제 탑승 가능 여부를 항공사에 즉시 확인해야 합니다.",
        ]

        all_warnings = plan.warnings + flight_warnings

        warning_items_html = "".join(
            f'<div class="warning-item">{html.escape(warning)}</div>'
            for warning in all_warnings
            )

        st.markdown(
            f"""
            <section class="warning-section">
              <h3>⚠️ 주의사항</h3>
              <div class="warning-list">
                {warning_items_html}
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def render_chat_messages():
    tool_labels = {
        "search_airport_documents": "공항 문서 RAG",
        "search_official_airport_web": "인천공항 공식 웹 검색",
        "lookup_departure_flight": "실시간 항공편 조회",
        "lookup_travel_time": "이동시간 조회",
        "lookup_destination_info": "도착지 날씨·시차 조회",
        "calculate_airport_plan": "출국 계획 계산",
        "legacy_rag_fallback": "기본 RAG 안전 모드",
    }
    rows = []
    for message in st.session_state.messages:
        role = message["role"]
        safe_content = html.escape(message["content"]).replace(
            "\n",
            "<br/>",
        )
        if role == "user":
            avatar = "U"
            row_class = "chat-row user"
        else:
            avatar = "✈"
            row_class = "chat-row assistant"
        used_tools = message.get("used_tools", [])
        tool_trace = ""
        if role != "user" and used_tools:
            labels = [
                tool_labels.get(tool_name, tool_name)
                for tool_name in used_tools
            ]
            tool_trace = (
                '<div class="tool-trace">'
                f"Agent 사용 도구: {html.escape(' → '.join(labels))}"
                "</div>"
            )
        elif role != "user" and message.get("agent_mode"):
            tool_trace = (
                '<div class="tool-trace">'
                "Agent 사용 도구: 없음 (직접 응답)"
                "</div>"
            )
        rows.append(
            f'<div class="{row_class}">'
            f'<div class="chat-avatar">{avatar}</div>'
            f'<div class="chat-bubble">{safe_content}{tool_trace}</div>'
            "</div>"
        )

    st.markdown(
        '<div class="chat-panel">' + "".join(rows) + "</div>",
        unsafe_allow_html=True,
    )


def render_chatbot(agent):
    st.markdown('<div class="chat-shell"></div>', unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "안녕하세요. 공항 이용, 전화번호, 수하물, "
                    "터미널 정보를 물어보세요."
                ),
            }
        ]

    question = None
    with st.container(border=True):
        st.markdown(
            """
            <div class="chat-intro">
              <div class="chat-title-row">
                <div class="chat-icon">◉</div>
                <div>
                  <h3>공항 AI 도우미</h3>
                  <p>질문에 맞는 공항 문서, 항공편, 이동시간, 웹 검색 도구를 선택해 안내해드려요.</p>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        quick_questions = [
            ("고객센터\n전화번호 알려줘", "인천공항 고객센터 전화번호 알려줘"),
            ("보조배터리\n위탁수하물 가능해?", "보조배터리 위탁수하물 가능해?"),
            ("액체류 기내 반입\n기준 알려줘", "액체류 기내 반입 기준 알려줘"),
            ("주차는\n어디에 해?", "인천공항 주차는 어디에 해?"),
        ]
        quick_columns = st.columns(4)
        for index, (button_label, real_question) in enumerate(quick_questions):
            if quick_columns[index].button(
                button_label,
                key=f"quick-question-{index}",
                use_container_width=True,
            ):
                question = real_question

        render_chat_messages()
        st.markdown(
            '<div class="chat-empty-space"></div>',
            unsafe_allow_html=True,
        )
        with st.form("chat-form", clear_on_submit=True):
            input_column, button_column = st.columns([8, 1], gap="small")
            with input_column:
                typed_question = st.text_input(
                    "메시지 입력",
                    placeholder="인천공항에 대해 궁금한 내용을 입력하세요",
                    label_visibility="collapsed",
                )
            with button_column:
                sent = st.form_submit_button(
                    "전송",
                    type="primary",
                    use_container_width=True,
                )
        if sent and typed_question.strip():
            question = typed_question.strip()

    if not question:
        return

    st.session_state.messages.append(
        {"role": "user", "content": question}
    )
    with st.spinner("Agent가 필요한 도구를 선택하는 중..."):
        flight_context = st.session_state.get("flight_api_summary", "")
        result = agent.ask(
            question,
            flight_context=flight_context,
            chat_history=st.session_state.messages[:-1],
        )
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "used_tools": result.get("used_tools", []),
            "agent_mode": result.get("agent_mode", False),
        }
    )
    st.session_state.last_sources = result["sources"]
    st.rerun()


def render_footer():
    st.markdown(
        """
        <footer class="footer-wrap">
          <div class="footer-inner">
            <strong>✈ 공항가는날</strong>
            <span>제공되는 정보는 참고용이며 실제 출국 전에는 공항과 항공사 공식 안내를 확인하세요.</span>
          </div>
        </footer>
        """,
        unsafe_allow_html=True,
    )


airport_agent = get_airport_agent()

try:
    if "airport_plan" in st.session_state:
        render_dashboard(
            st.session_state.flight_input,
            st.session_state.airport_plan,
        )
    else:
        render_hero()
        render_flight_form()
        render_features()

    render_chatbot(airport_agent)
    render_footer()
except Exception as exc:
    st.error(f"화면을 구성하는 중 오류가 발생했습니다: {exc}")
