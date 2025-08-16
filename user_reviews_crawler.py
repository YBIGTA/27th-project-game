import pandas as pd
import requests
import time
import random
import csv
import os
from urllib.parse import quote
import json
from datetime import datetime, timedelta
import sys
import re
from bs4 import BeautifulSoup

# HTTP 요청 헤더 (차단 회피용)
HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.7,ko;q=0.3",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
]

def get_random_headers():
    """랜덤한 헤더 반환 (차단 회피)"""
    return random.choice(HEADERS_LIST)

def sleep_jitter(min_s=1.0, max_s=2.0):
    """요청 사이에 랜덤 지연"""
    time.sleep(random.uniform(min_s, max_s))

def print_progress_bar(current, total, start_time, prefix="진행중", length=30, fill="█"):
    """프로그레스 바와 시간 정보 출력"""
    percent = current / total
    filled_length = int(length * percent)
    bar = fill * filled_length + '-' * (length - filled_length)
    
    # 경과 시간 및 예상 완료 시간 계산
    elapsed_time = time.time() - start_time
    if current > 0:
        estimated_total = elapsed_time / current * total
        remaining_time = estimated_total - elapsed_time
        eta = datetime.now() + timedelta(seconds=remaining_time)
        eta_str = eta.strftime("%H:%M:%S")
    else:
        remaining_time = 0
        eta_str = "--:--:--"
    
    elapsed_str = str(timedelta(seconds=int(elapsed_time)))
    remaining_str = str(timedelta(seconds=int(remaining_time)))
    
    print(f'\r{prefix} |{bar}| {current}/{total} ({percent:.1%}) '
          f'[경과: {elapsed_str}, 남은시간: {remaining_str}, 완료예정: {eta_str}]', end='')
    
    if current == total:
        print()  # 완료시 줄바꿈

def format_time_duration(seconds):
    """초를 시:분:초 형태로 포맷"""
    return str(timedelta(seconds=int(seconds)))

def get_unique_steamids(csv_file):
    """CSV 파일에서 고유한 author_steamid 목록 추출"""
    try:
        df = pd.read_csv(csv_file)
        if 'author_steamid' not in df.columns:
            print("❌ CSV 파일에 'author_steamid' 컬럼이 없습니다.")
            return []
        
        # null 값 제거하고 고유값만 추출
        unique_steamids = df['author_steamid'].dropna().unique().tolist()
        print(f"✅ {len(unique_steamids)}개의 고유한 Steam ID를 찾았습니다.")
        return unique_steamids
    except Exception as e:
        print(f"❌ CSV 파일 읽기 실패: {e}")
        return []

def get_processed_steamids(output_file):
    """이미 처리된 Steam ID 목록 가져오기"""
    processed_ids = set()
    try:
        if os.path.exists(output_file):
            df = pd.read_csv(output_file)
            if 'steamid' in df.columns:
                processed_ids = set(df['steamid'].dropna().unique())
                print(f"📄 기존 파일에서 {len(processed_ids)}개의 처리된 Steam ID를 발견했습니다.")
    except Exception as e:
        print(f"⚠️ 기존 파일 읽기 실패: {e}")
    
    return processed_ids

def check_steam_response_health(response_time, success_rate, consecutive_failures):
    """Steam 응답 상태 확인 및 경고"""
    warnings = []
    
    if response_time > 10:
        warnings.append(f"⚠️ 응답 시간이 느려졌습니다: {response_time:.1f}초")
    
    if success_rate < 50:
        warnings.append(f"⚠️ 성공률이 낮습니다: {success_rate:.1f}%")
    
    if consecutive_failures >= 3:
        warnings.append(f"🚨 연속 실패 {consecutive_failures}회 - Steam에서 차단했을 가능성")
    
    if consecutive_failures >= 5:
        warnings.append("🛑 5회 연속 실패 - 장시간 대기를 권장합니다")
        return "CRITICAL"
    elif consecutive_failures >= 3:
        return "WARNING" 
    elif warnings:
        return "CAUTION"
    
    return "HEALTHY"



def get_user_games_library(steamid):
    """Steam 게임 라이브러리 정보 수집 (현재 접근 제한으로 인해 비활성화)"""
    print("  ⚠️ 게임 라이브러리 수집이 비활성화되었습니다. (Steam 접근 제한)")
    return []
    
    # 아래 코드는 Steam 정책 변화로 인해 주석처리됨:
    # - Steam API GetOwnedGames: 401 Unauthorized 오류  
    # - 프로필 페이지: 로그인 필요 또는 비공개 설정
    # - 대부분 사용자가 게임 라이브러리를 비공개로 설정
    
    """
    games_info = []
    
    # try:
    #     # 1. 먼저 Steam API로 시도 (API 키 없이도 공개 라이브러리는 접근 가능)
    #     api_url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?steamid={steamid}&format=json&include_appinfo=true&include_played_free_games=true"
        
        response = requests.get(api_url, headers=get_random_headers(), timeout=15)
        if response.status_code == 200:
            data = response.json()
            if 'response' in data and 'games' in data['response']:
                games = data['response']['games']
                print(f"  🎮 Steam API에서 {len(games)}개 게임 정보를 가져왔습니다!")
                
                for game in games:
                    game_data = {
                        'steamid': steamid,
                        'appid': game.get('appid'),
                        'game_name': game.get('name', 'Unknown Game'),
                        'playtime_forever': game.get('playtime_forever', 0),  # 이미 분 단위
                        'playtime_2weeks': game.get('playtime_2weeks', 0),
                        'last_played': game.get('rtime_last_played', 0),
                        'data_source': 'steam_api'
                    }
                    games_info.append(game_data)
                
                return games_info
            else:
                print("  ⚠️ Steam API: 게임 데이터 없음 (비공개 라이브러리)")
        else:
            print(f"  ⚠️ Steam API 호출 실패 (상태코드: {response.status_code})")
        
        # 2. API 실패 시 프로필 페이지에서 시도
        print("  🔄 프로필 페이지에서 게임 정보 수집 시도...")
        games_url = f"https://steamcommunity.com/profiles/{steamid}/games/?tab=all"
        
        response = requests.get(games_url, headers=get_random_headers(), timeout=15)
        
        if response.status_code != 200:
            print(f"  ⚠️ 게임 라이브러리 페이지 접근 실패 (상태코드: {response.status_code})")
            return games_info
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 프로필이 비공개인지 확인
        if soup.find(string=re.compile("This profile is private|프로필이 비공개입니다")):
            print("  🔒 비공개 프로필입니다.")
            return games_info
        
        # 게임 목록이 비공개인지 확인
        if soup.find(string=re.compile("game details are private|게임 세부 정보가 비공개입니다")):
            print("  🔒 게임 목록이 비공개입니다.")
            return games_info
        
        # JavaScript로 로드되는 데이터인 경우 JSON 스크립트 찾기
        script_tags = soup.find_all('script')
        games_data = None
        
        for script in script_tags:
            if script.string and 'rgGames' in script.string:
                # rgGames 배열에서 게임 데이터 추출
                script_content = script.string
                start = script_content.find('rgGames = ') + len('rgGames = ')
                end = script_content.find(';', start)
                
                if start > len('rgGames = ') - 1 and end > start:
                    games_json = script_content[start:end]
                    try:
                        games_data = json.loads(games_json)
                        break
                    except:
                        continue
        
        if games_data:
            print(f"  🎮 {len(games_data)}개 게임을 소유하고 있습니다.")
            
            for game in games_data:
                # JavaScript 데이터에서 정보 추출
                game_info = {
                    'steamid': steamid,
                    'appid': game.get('appid'),
                    'game_name': game.get('name', f"Game_{game.get('appid')}"),
                    'playtime_forever': game.get('hours_forever', '0').replace(',', ''),  # 시간을 분으로 변환
                    'playtime_2weeks': game.get('hours', '0').replace(',', ''),  # 최근 플레이 시간
                    'last_played': game.get('last_played', 0),
                    'data_source': 'profile_page_js'
                }
                
                # 시간을 분으로 변환
                try:
                    hours_forever = float(game_info['playtime_forever'])
                    game_info['playtime_forever'] = int(hours_forever * 60)
                except:
                    game_info['playtime_forever'] = 0
                
                try:
                    hours_2weeks = float(game_info['playtime_2weeks'])
                    game_info['playtime_2weeks'] = int(hours_2weeks * 60)
                except:
                    game_info['playtime_2weeks'] = 0
                
                games_info.append(game_info)
        else:
            # JavaScript 데이터를 못 찾은 경우 HTML에서 기본 정보 추출
            game_elements = soup.find_all('div', class_='gameListRow')
            
            if game_elements:
                print(f"  🎮 약 {len(game_elements)}개 게임 정보를 찾았습니다. (기본 파싱)")
                
                for game_elem in game_elements:
                    game_name_elem = game_elem.find('h5')
                    game_name = game_name_elem.get_text(strip=True) if game_name_elem else "Unknown Game"
                    
                    # AppID 추출 시도
                    appid = None
                    game_link = game_elem.find('a')
                    if game_link:
                        href = game_link.get('href', '')
                        appid_match = re.search(r'/app/(\d+)/', href)
                        appid = int(appid_match.group(1)) if appid_match else None
                    
                    # 플레이 시간 추출 시도
                    playtime_elem = game_elem.find('h5', class_='ellipsis')
                    playtime_text = playtime_elem.get_text() if playtime_elem else "0 hrs"
                    playtime_match = re.search(r'([\d,]+\.?\d*)', playtime_text.replace(',', ''))
                    playtime_hours = float(playtime_match.group(1)) if playtime_match else 0
                    
                    game_info = {
                        'steamid': steamid,
                        'appid': appid,
                        'game_name': game_name,
                        'playtime_forever': int(playtime_hours * 60),  # 분으로 변환
                        'playtime_2weeks': 0,
                        'last_played': 0,
                        'data_source': 'profile_page_html'
                    }
                    
                    games_info.append(game_info)
            else:
                print("  ⚠️ 게임 정보를 찾을 수 없습니다.")
        
    # except Exception as e:
    #     print(f"  ❌ 게임 라이브러리 크롤링 실패: {e}")
    # 
    # return games_info
    """

def get_user_reviews_from_profile(steamid):
    """Steam 프로필 페이지에서 사용자가 작성한 모든 리뷰 수집 (페이지네이션 포함!)"""
    all_reviews = []
    seen_appids = set()  # 중복 검사용
    page_num = 1
    
    while True:
        try:
            # Steam 프로필 리뷰 페이지 (p=페이지번호로 페이지네이션)
            if page_num == 1:
                reviews_url = f"https://steamcommunity.com/profiles/{steamid}/reviews/"
            else:
                reviews_url = f"https://steamcommunity.com/profiles/{steamid}/reviews/?p={page_num}"
            
            print(f"    📄 페이지 {page_num} 수집 중...")
            
            response = requests.get(reviews_url, headers=get_random_headers(), timeout=15)
            if response.status_code != 200:
                print(f"  ⚠️ 리뷰 페이지 접근 실패 (상태코드: {response.status_code})")
                break
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 프로필이 비공개인지 확인 (첫 페이지에서만)
            if page_num == 1 and soup.find(string=re.compile("This profile is private|프로필이 비공개입니다")):
                print("  🔒 비공개 프로필입니다.")
                break
            
            # 이 페이지의 리뷰 컨테이너 찾기
            review_containers = soup.find_all('div', class_='review_box')
            
            # 이 페이지에 리뷰가 없으면 종료
            if not review_containers:
                if page_num == 1:
                    print("  📝 작성된 리뷰가 없습니다.")
                else:
                    print(f"    ✅ 페이지 {page_num}: 더 이상 리뷰가 없습니다. (수집 완료)")
                break
            
            print(f"    📝 페이지 {page_num}: {len(review_containers)}개 리뷰 발견")
            
            # 이 페이지에서 새로운 리뷰가 있는지 확인
            new_reviews_found = 0
            
            # 이 페이지의 모든 리뷰 처리
            for review_container in review_containers:
                try:
                    # 게임 정보 추출 (실제 HTML 구조에 맞게)
                    appid = None
                    game_name = "Unknown Game"
                    
                    leftcol = review_container.find('div', class_='leftcol')
                    if leftcol:
                        game_link = leftcol.find('a', href=re.compile(r'/app/\d+'))
                        if game_link:
                            app_url = game_link.get('href', '')
                            appid_match = re.search(r'/app/(\d+)', app_url)
                            if appid_match:
                                appid = int(appid_match.group(1))
                                
                                # 중복 검사
                                if appid in seen_appids:
                                    continue  # 이미 수집한 리뷰면 건너뛰기
                                
                                seen_appids.add(appid)
                                new_reviews_found += 1
                                
                                # AppID로 게임 이름 가져오기
                                try:
                                    store_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&format=json"
                                    store_response = requests.get(store_url, headers=get_random_headers(), timeout=5)
                                    if store_response.status_code == 200:
                                        store_data = store_response.json()
                                        if str(appid) in store_data and store_data[str(appid)]['success']:
                                            game_name = store_data[str(appid)]['data'].get('name', f"Game_{appid}")
                                        else:
                                            game_name = f"Game_{appid}"
                                    else:
                                        game_name = f"Game_{appid}"
                                except:
                                    game_name = f"Game_{appid}"
                                
                                # 실제 리뷰 데이터 추출
                                review_text = "리뷰 텍스트 추출 중..."
                                voted_up = True
                                votes_up = 0
                                playtime_minutes = 0
                                review_date = ""
                                
                                # rightcol에서 리뷰 텍스트 추출
                                rightcol = review_container.find('div', class_='rightcol')
                                if rightcol:
                                    # content 클래스에서 리뷰 텍스트 찾기
                                    content_elem = rightcol.find('div', class_='content')
                                    if content_elem:
                                        review_text = content_elem.get_text(strip=True)
                                
                                # 추천/비추천 정보 추출
                                if rightcol:
                                    # "Recommended" 또는 "Not Recommended" 텍스트 찾기
                                    recommendation_text = rightcol.find(string=re.compile(r'Recommended|Not Recommended'))
                                    if recommendation_text:
                                        # 정확한 텍스트 비교로 추천/비추천 구분
                                        voted_up = recommendation_text.strip() == "Recommended"
                                        # print(f"      🔍 추천 여부: {recommendation_text.strip()}")
                                
                                # 투표 수 추출 (새로운 방법: class="header"에서 추출)
                                header_elem = review_container.find('div', class_='header')
                                if header_elem:
                                    header_text = header_elem.get_text()
                                    # "1명이 이 평가가 유용하다고 함" 또는 "1 person found this review helpful"에서 숫자 추출
                                    votes_match = re.search(r'(\d+)', header_text)
                                    if votes_match:
                                        votes_up = int(votes_match.group(1))
                                        # print(f"      🔍 도움됨: {votes_up}명")
                                    else:
                                        votes_up = 0  # 숫자가 없으면 0
                                else:
                                    votes_up = 0  # header가 없으면 0
                                
                                # 리뷰 날짜 추출
                                if rightcol:
                                    # "Posted" 패턴 찾기 (월만 있는 경우도 포함)
                                    date_text = rightcol.find(string=re.compile(r'Posted.*'))
                                    if date_text:
                                        review_date = date_text.strip()
                                        # print(f"      🔍 날짜: {review_date}")
                                
                                # 플레이 시간 추출
                                hours_elem = rightcol.find('div', class_='hours') if rightcol else None
                                if hours_elem:
                                    hours_text = hours_elem.get_text()
                                    hours_match = re.search(r'([\d,]+\.?\d*)', hours_text.replace(',', ''))
                                    if hours_match:
                                        playtime_hours = float(hours_match.group(1))
                                        playtime_minutes = int(playtime_hours * 60)
                                
                                # 리뷰 데이터 구성
                                review_data = {
                                    'steamid': steamid,
                                    'appid': appid,
                                    'game_name': game_name,
                                    'review_text': review_text,
                                    'voted_up': voted_up,
                                    'votes_up': votes_up,
                                    'playtime_forever': playtime_minutes,
                                    'review_date': review_date,
                                }
                                
                                all_reviews.append(review_data)
                    
                except Exception as e:
                    print(f"      ⚠️ 개별 리뷰 파싱 실패: {e}")
                    continue
            
            # 새로운 리뷰가 없으면 페이지네이션 중단
            if new_reviews_found == 0:
                print(f"    ✅ 페이지 {page_num}: 새로운 리뷰가 없습니다. 수집 완료!")
                break
            
            # 이 페이지에 10개 미만의 리뷰가 있으면 마지막 페이지임 (최적화)
            if len(review_containers) < 10:
                print(f"    ✅ 페이지 {page_num}: {len(review_containers)}개 리뷰 (마지막 페이지). 수집 완료!")
                break
            
            # 다음 페이지로
            page_num += 1
            time.sleep(0.5)
            
            # 안전장치: 최대 100페이지
            if page_num > 100:
                print(f"    ⚠️ 최대 페이지 수 도달. 수집 중단.")
                break
        
        except Exception as e:
            print(f"    ❌ 페이지 {page_num} 수집 실패: {e}")
            break
    
    print(f"  ✅ 총 {len(all_reviews)}개 리뷰 파싱 완료 ({page_num-1}페이지 수집)")
    return all_reviews



def save_reviews_to_csv(all_reviews, output_file):
    """수집된 리뷰를 CSV 파일로 저장"""
    if not all_reviews:
        print("\n❌ 저장할 리뷰가 없습니다.")
        return
    
    try:
        df = pd.DataFrame(all_reviews)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ {len(all_reviews)}개 리뷰를 {output_file}에 저장했습니다.")
    except Exception as e:
        print(f"\n❌ CSV 저장 실패: {e}")

def save_games_library_to_csv(all_games, output_file):
    """수집된 게임 라이브러리 정보를 CSV 파일로 저장"""
    if not all_games:
        print("\n❌ 저장할 게임 정보가 없습니다.")
        return
    
    try:
        df = pd.DataFrame(all_games)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ {len(all_games)}개 게임 정보를 {output_file}에 저장했습니다.")
    except Exception as e:
        print(f"\n❌ 게임 정보 CSV 저장 실패: {e}")

def get_processed_steamids_for_games(output_file):
    """이미 게임 정보가 수집된 Steam ID 목록 가져오기"""
    processed_ids = set()
    try:
        if os.path.exists(output_file):
            df = pd.read_csv(output_file)
            if 'steamid' in df.columns:
                processed_ids = set(df['steamid'].dropna().unique())
                print(f"📄 기존 게임 정보 파일에서 {len(processed_ids)}개의 처리된 Steam ID를 발견했습니다.")
    except Exception as e:
        print(f"⚠️ 기존 게임 정보 파일 읽기 실패: {e}")
    
    return processed_ids

def log_progress_stats(current_user, total_users, total_reviews_found, failed_users, start_time):
    """진행 통계 출력"""
    elapsed = time.time() - start_time
    success_rate = ((current_user - failed_users) / current_user * 100) if current_user > 0 else 0
    avg_reviews_per_user = total_reviews_found / (current_user - failed_users) if (current_user - failed_users) > 0 else 0
    
    print(f"\n📊 현재 통계:")
    print(f"   • 처리된 사용자: {current_user}/{total_users}")
    print(f"   • 수집된 리뷰: {total_reviews_found}개")
    print(f"   • 성공률: {success_rate:.1f}%")
    print(f"   • 사용자당 평균 리뷰: {avg_reviews_per_user:.1f}개")
    print(f"   • 실패한 사용자: {failed_users}명")
    print(f"   • 경과 시간: {format_time_duration(elapsed)}")
    print("=" * 50)

def main():
    # 설정
    input_csv = "data/steam_reviews.csv"  # 입력 CSV 파일
    output_csv = "data/user_all_reviews.csv"  # 출력 CSV 파일
    games_library_csv = "data/user_games_library.csv"  # 게임 라이브러리 정보 CSV 파일
    
    # 기능 설정
    COLLECT_REVIEWS = True  # 리뷰 수집 여부
    COLLECT_GAMES_LIBRARY = False  # 게임 라이브러리 정보 수집 비활성화 (접근 제한으로 인해)
    
    # 안전 모드 설정
    SAFE_MODE = True  # True: 더 긴 지연시간, False: 빠른 처리
    MAX_USERS_PER_SESSION = 10000  # 한 번에 처리할 최대 사용자 수
    
    # 출력 디렉토리 생성
    os.makedirs("outputs", exist_ok=True)
    
    print("🚀 Steam 사용자 리뷰 크롤링 시작")
    print("=" * 50)
    
    # 1. CSV에서 고유한 Steam ID 추출
    steam_ids = get_unique_steamids(input_csv)
    
    if not steam_ids:
        print("❌ 처리할 Steam ID가 없습니다.")
        return
    
    # 2. 이미 처리된 Steam ID 확인 (중간부터 재시작 기능)
    if COLLECT_REVIEWS:
        processed_ids_reviews = get_processed_steamids(output_csv)
    else:
        processed_ids_reviews = set()
    
    # if COLLECT_GAMES_LIBRARY:
    #     processed_ids_games = get_processed_steamids_for_games(games_library_csv)
    # else:
    processed_ids_games = set()
    
    # 리뷰만 수집하므로 리뷰 처리된 사용자만 확인
    processed_ids = processed_ids_reviews
    
    remaining_ids = [sid for sid in steam_ids if sid not in processed_ids]
    
    if processed_ids:
        print(f"🔄 이어서 시작: {len(processed_ids)}개 완료, {len(remaining_ids)}개 남음")
        
        # 기존 데이터 로드
        all_reviews = []
        all_games = []
        
        if COLLECT_REVIEWS:
            try:
                existing_df = pd.read_csv(output_csv)
                all_reviews = existing_df.to_dict('records')
                print(f"📁 기존 리뷰 데이터 로드: {len(all_reviews)}개")
            except:
                all_reviews = []
        
        # if COLLECT_GAMES_LIBRARY:
        #     try:
        #         existing_games_df = pd.read_csv(games_library_csv)
        #         all_games = existing_games_df.to_dict('records')
        #         print(f"📁 기존 게임 데이터 로드: {len(all_games)}개")
        #     except:
        #         all_games = []
        all_games = []  # 게임 라이브러리 수집 비활성화
    else:
        all_reviews = []
        all_games = []
        print(f"🆕 새로 시작: {len(remaining_ids)}개 사용자 처리 예정")
    
    # 안전을 위해 처리할 사용자 수 제한
    if len(remaining_ids) > MAX_USERS_PER_SESSION:
        current_batch = remaining_ids[:MAX_USERS_PER_SESSION]
        print(f"⚠️ 안전을 위해 이번 세션에서는 {MAX_USERS_PER_SESSION}명만 처리합니다.")
        print(f"   남은 {len(remaining_ids) - MAX_USERS_PER_SESSION}명은 다음 실행에서 처리됩니다.")
        print(f"   💡 팁: 5만명 이상은 위험하니 여러 번 나누어 실행하세요!")
    else:
        current_batch = remaining_ids
    
    if not current_batch:
        print("✅ 모든 사용자가 이미 처리되었습니다!")
        return
    
    # 진행 상황 추적 변수들
    failed_users = 0
    consecutive_failures = 0
    last_request_time = 0
    start_time = time.time()
    
    # 안전 모드 설정 출력 (지연시간 단축!)
    delay_min, delay_max = (1.5, 3.0) if SAFE_MODE else (0.8, 1.5)
    print(f"\n🛡️ 안전 모드: {'ON' if SAFE_MODE else 'OFF'}")
    print(f"⏱️ 요청 간격: {delay_min}-{delay_max}초")
    print(f"🎯 이번 세션 처리 대상: {len(current_batch)}명")
    
    # 수집 모드 표시
    collection_modes = []
    if COLLECT_REVIEWS:
        collection_modes.append("리뷰(프로필 페이지 - BeautifulSoup)")
    if COLLECT_GAMES_LIBRARY:
        collection_modes.append("게임 라이브러리(Steam 공개 API)")
    print(f"📋 수집 모드: {', '.join(collection_modes)}")
    
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 3. 각 Steam ID에 대해 리뷰 수집
    for i, steamid in enumerate(current_batch, 1):
        # 프로그레스 바 출력
        print_progress_bar(i-1, len(current_batch), start_time, "사용자 처리")
        
        print(f"\n[{i}/{len(current_batch)}] Steam ID: {steamid}")
        print(f"⏱️  현재 시간: {datetime.now().strftime('%H:%M:%S')}")
        
        user_reviews = []
        user_games = []
        request_start_time = time.time()
        
        try:
            # 1. 리뷰 수집 (프로필 페이지에서 직접!)
            if COLLECT_REVIEWS:
                user_reviews = get_user_reviews_from_profile(steamid)
                
                if user_reviews:
                    all_reviews.extend(user_reviews)
                    print(f"  ✅ 리뷰: {len(user_reviews)}개 수집 성공!")
                else:
                    print(f"  ⚠️ 리뷰를 찾을 수 없습니다.")
            
            # 2. 게임 라이브러리 정보 수집 (비활성화됨)
            # if COLLECT_GAMES_LIBRARY:
            #     user_games = get_user_games_library(steamid)
            #     
            #     if user_games:
            #         all_games.extend(user_games)
            #         total_playtime = sum(game['playtime_forever'] for game in user_games)
            #         print(f"  ✅ 게임 라이브러리: {len(user_games)}개 게임, 총 플레이시간 {total_playtime}분")
            #     else:
            #         print(f"  ⚠️ 게임 라이브러리 정보를 가져올 수 없습니다.")
            
            # 성공 여부 판단 (리뷰만 수집)
            success = (user_reviews if COLLECT_REVIEWS else True)
            
            if success:
                consecutive_failures = 0  # 성공 시 연속 실패 카운트 리셋
            else:
                failed_users += 1
                consecutive_failures += 1
                
        except Exception as e:
            print(f"\n  ❌ 사용자 {steamid} 처리 중 오류: {e}")
            failed_users += 1
            consecutive_failures += 1
        
        # 응답 시간 체크
        request_time = time.time() - request_start_time
        current_success_rate = ((i - failed_users) / i * 100) if i > 0 else 0
        
        # Steam 응답 상태 확인
        health_status = check_steam_response_health(request_time, current_success_rate, consecutive_failures)
        
        if health_status == "CRITICAL":
            print(f"\n🚨 CRITICAL: 연속 {consecutive_failures}회 실패!")
            print("💤 5분간 대기 후 계속 진행합니다...")
            time.sleep(300)  # 5분 대기
            consecutive_failures = 0
        elif health_status == "WARNING":
            print(f"\n⚠️ WARNING: 연속 {consecutive_failures}회 실패, 추가 지연")
            sleep_jitter(10.0, 20.0)  # 추가 지연
        
        # 중간 저장 (10명마다)
        if i % 10 == 0:
            if COLLECT_REVIEWS:
                save_reviews_to_csv(all_reviews, output_csv)
            # if COLLECT_GAMES_LIBRARY:
            #     save_games_library_to_csv(all_games, games_library_csv)
            log_progress_stats(i, len(current_batch), len(all_reviews), failed_users, start_time)
        
        # 5명마다 간단한 통계 출력
        elif i % 5 == 0:
            success_rate = ((i - failed_users) / i * 100) if i > 0 else 0
            stats_parts = []
            if COLLECT_REVIEWS:
                stats_parts.append(f"리뷰 {len(all_reviews)}개")
            # if COLLECT_GAMES_LIBRARY:
            #     stats_parts.append(f"게임 {len(all_games)}개")
            print(f"  📊 중간 통계: {', '.join(stats_parts)}, 성공률 {success_rate:.1f}%")
        
        # 요청 제한을 위한 지연 (안전 모드에 따라 조정)
        sleep_jitter(delay_min, delay_max)
    
    # 최종 프로그레스 바 완료
    print_progress_bar(len(current_batch), len(current_batch), start_time, "사용자 처리")
    
    # 4. 최종 저장
    if COLLECT_REVIEWS:
        save_reviews_to_csv(all_reviews, output_csv)
    # if COLLECT_GAMES_LIBRARY:
    #     save_games_library_to_csv(all_games, games_library_csv)
    
    # 최종 통계 출력
    total_time = time.time() - start_time
    end_time = datetime.now()
    
    print("\n" + "🎉" * 25)
    print("🎉 크롤링 완료! 최종 결과 🎉")
    print("🎉" * 25)
    
    # 결과 파일 정보
    if COLLECT_REVIEWS:
        print(f"📁 리뷰 결과 파일: {output_csv}")
    # if COLLECT_GAMES_LIBRARY:
    #     print(f"📁 게임 라이브러리 파일: {games_library_csv}")
    
    print(f"📊 처리된 사용자: {len(current_batch)}명")
    
    # 수집 결과 통계
    if COLLECT_REVIEWS:
        print(f"🔍 수집된 리뷰: {len(all_reviews)}개")
        avg_reviews = (len(all_reviews) / (len(current_batch) - failed_users)) if (len(current_batch) - failed_users) > 0 else 0
        print(f"⚡ 사용자당 평균 리뷰: {avg_reviews:.1f}개")
    
    # if COLLECT_GAMES_LIBRARY:
    #     print(f"🎮 수집된 게임 정보: {len(all_games)}개")
    #     avg_games = (len(all_games) / (len(current_batch) - failed_users)) if (len(current_batch) - failed_users) > 0 else 0
    #     print(f"⚡ 사용자당 평균 게임: {avg_games:.1f}개")
    #     
    #     if all_games:
    #         total_playtime = sum(game['playtime_forever'] for game in all_games)
    #         avg_playtime = total_playtime / len(all_games) if all_games else 0
    #         print(f"🕹️ 총 플레이시간: {total_playtime:,}분 ({total_playtime/60:.1f}시간)")
    #         print(f"🕹️ 게임당 평균 플레이시간: {avg_playtime:.1f}분")
    
    print(f"✅ 성공한 사용자: {len(current_batch) - failed_users}명")
    print(f"❌ 실패한 사용자: {failed_users}명")
    print(f"📈 성공률: {((len(current_batch) - failed_users) / len(current_batch) * 100):.1f}%")
    print(f"⏱️  총 소요 시간: {format_time_duration(total_time)}")
    print(f"🕐 시작 시간: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🕐 완료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 남은 작업 안내
    if len(remaining_ids) > len(current_batch):
        remaining_count = len(remaining_ids) - len(current_batch)
        print(f"\n📌 안내: 아직 {remaining_count}명의 사용자가 남아있습니다.")
        print("   프로그램을 다시 실행하면 중간부터 이어서 진행됩니다.")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
