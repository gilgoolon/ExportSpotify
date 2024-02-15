import argparse
import time

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By

from tqdm import tqdm


class SpotifyFetcher:
    def __init__(self, link: str):
        self.playlist_link = link
        self.user_data_dir = r"C:\Users\alper\AppData\Local\Google\Chrome\User Data"

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument(f"user-data-dir={self.user_data_dir}")
        self.driver = webdriver.Chrome(
            'C:/Program Files/ChromeDriver/chromedriver.exe', options=chrome_options
        )

        self.playlist_response = None
        self.songs = []
        self.playlist_name = None
        self.song_count = None

    def fetch_playlist(self):
        self.driver.get(self.playlist_link)

        wait = WebDriverWait(self.driver, 15)
        main_view_container = wait.until(expected_conditions.presence_of_element_located((By.CLASS_NAME, 'main-view'
                                                                                                         '-container')))
        grid = main_view_container.find_element(By.CLASS_NAME, "os-viewport-native-scrollbars-invisible")
        time.sleep(1)

        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        #   <meta content="82" name="music:song_count"/>
        #   <meta content="My Rock" name="twitter:title"/>
        self.playlist_name = soup.find("meta", {"name": "twitter:title"})["content"]
        self.song_count = int(soup.find("meta", {"name": "music:song_count"})["content"])
        pbar = tqdm(total=self.song_count, desc="Fetching songs from Spotify")

        songs = set()
        while True:
            prev_song_count = len(songs)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            with open("playlist.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            for track_row in soup.find_all("div", {"data-testid": "tracklist-row"}):
                try:
                    name_artist_div = track_row.find("div", {"aria-colindex": "2"}).find("div")
                except AttributeError:
                    break
                name = name_artist_div.find("div").text
                artist = name_artist_div.find("a").text
                songs.add((name, artist))
            new_song_count = len(songs) - prev_song_count
            # print(f"Loaded {new_song_count} new songs. Total so far: {len(songs)}")
            pbar.update(new_song_count)
            self.driver.execute_script("arguments[0].scrollBy(0, 500);", grid)
            time.sleep(0.5)

            if not new_song_count:
                break

        self.songs = list(songs)

    def get_songs(self) -> list[tuple[str, str]]:
        return self.songs


def main(playlist_link: str):
    fetcher = SpotifyFetcher(playlist_link)
    fetcher.fetch_playlist()
    songs = fetcher.get_songs()
    print(songs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download all songs from a Spotify playlist as an MP3')
    parser.add_argument("source", nargs=1, help="The link to the Spotify playlist")
    source = parser.parse_args().source[0]
    main(source)
