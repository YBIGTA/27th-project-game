import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os
from collections import defaultdict



def get_game_name_from_community_page(appid):
    """
    Steam Community 페이지에서 게임 이름 가져오기
    """
    try:
        url = f"https://steamcommunity.com/app/{appid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        response = requests.get(url, headers=headers, timeout=8)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 페이지 제목에서 게임 이름 추출
            title_elem = soup.find('title')
            if title_elem:
                title_text = title_elem.get_text()
                if " on Steam" in title_text:
                    game_name = title_text.replace(" on Steam", "").strip()
                    if game_name and game_name != "Steam":
                        return game_name, True
            
            # 대안: 페이지 내 게임 이름 찾기
            game_name_elem = soup.find('div', class_='apphub_AppName')
            if game_name_elem:
                game_name = game_name_elem.get_text().strip()
                if game_name:
                    return game_name, True
        
        return None, False
        
    except Exception as e:
        return None, False

def fix_game_names_comprehensive(csv_file):
    """
    종합적인 game_name 수정 프로그램
    
    방법 1: AppID 중복 활용 (가장 빠름)
    방법 2: Steam Community 페이지 (모든 남은 항목 처리)
    """
    
    print("🔧 종합적인 game_name 수정 프로그램")
    print("=" * 60)
    
    # 1. CSV 파일 읽기
    try:
        df = pd.read_csv(csv_file)
        print(f"✅ CSV 파일 로드 완료: {len(df)}개 행")
    except Exception as e:
        print(f"❌ CSV 파일 읽기 실패: {e}")
        return
    
    # 2. 문제가 있는 game_name 찾기
    problematic_mask = df['game_name'].str.startswith('Game_', na=False)
    problematic_count = problematic_mask.sum()
    
    print(f"\n📊 현재 상태 분석:")
    print(f"   • 총 행 수: {len(df):,}개")
    print(f"   • 문제가 있는 game_name: {problematic_count:,}개")
    
    if problematic_count == 0:
        print("🎉 모든 game_name이 정상입니다!")
        return
    
    # 3. 방법 1: AppID 중복 활용 (가장 빠름)
    print(f"\n🚀 방법 1: AppID 중복 활용으로 수정 중...")
    
    appid_to_names = defaultdict(set)
    normal_mask = ~problematic_mask
    normal_df = df[normal_mask]
    
    for _, row in normal_df.iterrows():
        appid = row['appid']
        game_name = row['game_name']
        if pd.notna(appid) and pd.notna(game_name) and game_name != "":
            appid_to_names[appid].add(game_name)
    
    # 중복으로 수정 가능한 항목 찾기
    duplicate_fixes = {}
    for appid in df[problematic_mask]['appid'].unique():
        if pd.notna(appid) and appid in appid_to_names:
            normal_names = list(appid_to_names[appid])
            if normal_names:
                selected_name = min(normal_names, key=len)
                duplicate_fixes[appid] = selected_name
    
    # 중복으로 수정 실행
    if duplicate_fixes:
        print(f"   • 중복으로 수정 가능한 AppID: {len(duplicate_fixes):,}개")
        for appid, correct_name in duplicate_fixes.items():
            mask = (df['appid'] == appid) & problematic_mask
            rows_to_fix = mask.sum()
            df.loc[mask, 'game_name'] = correct_name
            print(f"     • AppID {appid}: '{correct_name}'로 {rows_to_fix}개 행 수정")
    else:
        print("   • 중복으로 수정 가능한 항목이 없습니다.")
    

    
    # 4. 방법 2: Steam Community 페이지로 모든 남은 항목 처리
    print(f"\n🌐 방법 2: Steam Community 페이지로 모든 남은 항목 처리 중...")
    
    problematic_mask = df['game_name'].str.startswith('Game_', na=False)
    remaining_appids = df[problematic_mask]['appid'].unique()
    remaining_appids = [aid for aid in remaining_appids if pd.notna(aid)]
    
    if len(remaining_appids) > 0:
        print(f"   • 남은 문제 AppID: {len(remaining_appids):,}개")
        
        community_fixes = {}
        community_success = 0
        community_fail = 0
        
        for i, appid in enumerate(remaining_appids, 1):  # 모든 남은 항목 시도
            print(f"     • 진행률: {i}/{len(remaining_appids)} ({i/len(remaining_appids)*100:.1f}%)")
            print(f"       AppID {appid} 확인 중...", end=" ")
            
            game_name, success = get_game_name_from_community_page(appid)
            
            if success and game_name:
                community_fixes[appid] = game_name
                community_success += 1
                print(f"✅ '{game_name}'")
            else:
                community_fail += 1
                print(f"❌ 실패")
            
            # 10개마다 자동 저장
            if i % 10 == 0:
                try:
                    # 현재까지 수정된 항목들을 임시로 적용
                    temp_df = df.copy()
                    for temp_appid, temp_name in community_fixes.items():
                        temp_mask = (temp_df['appid'] == temp_appid) & problematic_mask
                        temp_df.loc[temp_mask, 'game_name'] = temp_name
                    
                    temp_df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                    print(f"     💾 {i}개 완료, 중간 저장 완료")
                except Exception as e:
                    print(f"     ⚠️ 중간 저장 실패: {e}")
                
                time.sleep(3)  # 저장 후 잠시 대기
            else:
                time.sleep(1)  # 기본 대기 시간
        
        # Community로 수정 실행
        if community_fixes:
            print(f"   • Community로 수정 가능한 AppID: {len(community_fixes):,}개")
            for appid, correct_name in community_fixes.items():
                mask = (df['appid'] == appid) & problematic_mask
                rows_to_fix = mask.sum()
                df.loc[mask, 'game_name'] = correct_name
                print(f"     • AppID {appid}: '{correct_name}'로 {rows_to_fix}개 행 수정")
        
        print(f"   • Community 결과: 성공 {community_success}개, 실패 {community_fail}개")
    
    # 5. 최종 결과 확인
    problematic_after = df['game_name'].str.startswith('Game_', na=False).sum()
    print(f"\n🎯 최종 결과:")
    print(f"   • 수정 전 문제 행: {problematic_count:,}개")
    print(f"   • 수정 후 문제 행: {problematic_after:,}개")
    print(f"   • 해결된 문제: {problematic_count - problematic_after:,}개")
    
    # 6. 백업 파일 생성
    backup_file = csv_file.replace('.csv', '_backup_before_comprehensive_fix.csv')
    try:
        df_backup = pd.read_csv(csv_file)
        df_backup.to_csv(backup_file, index=False, encoding='utf-8-sig')
        print(f"   • 백업 파일 생성: {backup_file}")
    except Exception as e:
        print(f"   • ⚠️ 백업 파일 생성 실패: {e}")
    
    # 7. 최종 수정된 파일 저장
    try:
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"   • 최종 수정된 파일 저장: {csv_file}")
    except Exception as e:
        print(f"   • ❌ 파일 저장 실패: {e}")
        return
    
    if problematic_after == 0:
        print("🎉 모든 game_name 문제가 해결되었습니다!")
    else:
        print(f"⚠️ 아직 {problematic_after:,}개의 문제가 남아있습니다.")
        print("   • 이는 Steam Community 페이지에서도 정보를 찾을 수 없는 AppID입니다.")
        print("   • 이는 삭제된 게임이거나 비공개 게임일 수 있습니다.")
    
    return df

def main():
    """메인 함수"""
    print("🔧 종합적인 Steam 리뷰 CSV의 game_name 수정 프로그램")
    print("=" * 60)
    
    # CSV 파일 경로
    csv_file = "data/user_all_reviews.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ 파일을 찾을 수 없습니다: {csv_file}")
        print("💡 'data/user_all_reviews.csv' 파일이 있는지 확인해주세요.")
        return
    
    # 파일 크기 확인
    file_size = os.path.getsize(csv_file) / (1024 * 1024)  # MB
    print(f"📁 대상 파일: {csv_file}")
    print(f"📏 파일 크기: {file_size:.1f} MB")
    
    # 사용자 확인 (자동 실행)
    print(f"\n⚠️ 주의사항:")
    print(f"   • 이 프로그램은 기존 파일을 수정합니다")
    print(f"   • 백업 파일이 자동으로 생성됩니다")
    print(f"   • 2가지 방법을 순차적으로 시도합니다:")
    print(f"     1️⃣ AppID 중복 활용 (가장 빠름)")
    print(f"     2️⃣ Steam Community 페이지 (모든 남은 항목 처리)")
    print(f"   • 10개마다 자동 중간 저장됩니다")
    print(f"   • 자동 실행 모드로 진행합니다...")
    
    # 수정 실행
    try:
        result_df = fix_game_names_comprehensive(csv_file)
        if result_df is not None:
            print(f"\n🎉 종합적인 game_name 수정이 완료되었습니다!")
        else:
            print(f"\n❌ game_name 수정에 실패했습니다.")
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
