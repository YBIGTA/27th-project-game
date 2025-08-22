import asyncio
import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import timedelta

# ---- 유저 리뷰 크롤링 ----
async def fetch_user_reviews(session: ClientSession, steamid: str):
    """특정 유저의 모든 리뷰 크롤링"""
    url = f"https://steamcommunity.com/profiles/{steamid}/reviews/"
    reviews = []

    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                print(f"[❌] steamid {steamid} 응답 오류 {resp.status}")
                return []

            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            # 각 리뷰 블록 찾기
            review_blocks = soup.select(".review_box")
            for block in review_blocks:
                try:
                    app_link = block.select_one("a[href*='/app/']")
                    if not app_link:
                        continue

                    appid = app_link["href"].split("/app/")[1].split("/")[0]
                    game_title = app_link.text.strip()

                    voted_up = 1 if block.select_one(".title") and "Recommended" in block.select_one(".title").text else 0
                    playtime_el = block.select_one(".hours")
                    playtime = 0
                    if playtime_el:
                        txt = playtime_el.text.replace(",", "").strip()
                        if "hrs" in txt:
                            playtime = float(txt.split()[0]) * 60  # 시간을 분으로 변환

                    reviews.append({
                        "steamid": steamid,
                        "appid": appid,
                        "game_title": game_title,
                        "voted_up": voted_up,
                        "playtime_forever": playtime
                    })
                except Exception as e:
                    print(f"[⚠️] steamid {steamid} 리뷰 파싱 중 오류: {e}")
                    continue

    except Exception as e:
        print(f"[예외] steamid {steamid} 요청 실패: {e}")
        return []

    return reviews


# ---- 메인 ----
async def main_async(input_csv="./outputs/steam_reviews.csv",
                     out_csv="./outputs/user_all_reviews.csv",
                     test=False):

    df = pd.read_csv(input_csv)

    # 유저 ID 컬럼 통일
    if "author_steamid" in df.columns:
        df = df.rename(columns={"author_steamid": "steamid"})
    if "steamid" not in df.columns:
        raise ValueError("⚠️ 입력 CSV에 'steamid' 컬럼이 필요합니다!")

    unique_users = df["steamid"].drop_duplicates().tolist()

    if test:
        unique_users = unique_users[:50]
        print("🧪 테스트 모드 (50명만 실행)")

    total = len(unique_users)
    print(f"요청 대상 유저 수: {total}")

    all_results = []
    start_time = time.time()

    connector = aiohttp.TCPConnector(limit=10)  # 동시 요청 줄임
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for i, steamid in enumerate(unique_users, 1):
            tasks.append(fetch_user_reviews(session, steamid))

            if len(tasks) >= 10:
                responses = await asyncio.gather(*tasks)
                tasks = []
                for res in responses:
                    all_results.extend(res)

                if i % 100 == 0 or i == total:
                    elapsed = time.time() - start_time
                    per_item = elapsed / i
                    remaining = (total - i) * per_item
                    percent = (i / total) * 100
                    print(f"🌸 {i}/{total} ({percent:.2f}%) 완료")
                    print(f"⏱ 경과: {timedelta(seconds=int(elapsed))} | 예상 남은: {timedelta(seconds=int(remaining))}")

        # 남은 태스크 처리
        if tasks:
            responses = await asyncio.gather(*tasks)
            for res in responses:
                all_results.extend(res)

    out_df = pd.DataFrame(all_results)
    print("👉 최종 appid 고유 개수:", out_df["appid"].nunique())
    print("👉 최종 리뷰 개수:", len(out_df))

    out_df.to_csv(out_csv, index=False)
    print(f"✅ 저장 완료: {out_csv}")


def main():
    asyncio.run(main_async(test=False))

if __name__ == "__main__":
    main()
