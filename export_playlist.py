import argparse
import time

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By

from tqdm import tqdm

from pytube import YouTube
from moviepy.editor import *
import ffmpeg


class SpotifyFetcher:
    def __init__(self, link: str, d):
        self.playlist_link = link
        self.driver = d
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
                name = name_artist_div.find("div", {"dir": "auto"}).text
                artist = name_artist_div.find("a", {"dir": "auto"}).text
                songs.add((name, artist))
            new_song_count = len(songs) - prev_song_count
            pbar.update(new_song_count)
            self.driver.execute_script("arguments[0].scrollBy(0, 500);", grid)
            time.sleep(0.5)

            if not new_song_count:
                break

        self.songs = list(songs)

    def get_songs(self) -> list[tuple[str, str]]:
        return self.songs

    def get_playlist_name(self) -> str:
        return self.playlist_name


class YoutubeDownloader:
    def __init__(self, songs: list[tuple[str, str]], d, name):
        self.driver = d
        self.songs = songs
        self.songs_to_download = []
        self.destination = os.path.join(rf"C:\Users\alper\Music", name)
        os.makedirs(self.destination, exist_ok=True)

    def get_songs_to_download(self):
        for song in tqdm(self.songs, desc="Fetching YouTube links"):
            link = self.get_song_link(song)
            self.songs_to_download.append((*song, link))

    def get_song_link(self, song: tuple[str, str]) -> str:
        base_url = "https://www.youtube.com/results?search_query="
        name, artist = song
        search_term = f"{name} - {artist}"
        url = base_url + search_term.replace(" ", "+")
        self.driver.get(url)
        wait = WebDriverWait(self.driver, 15)
        wait.until(expected_conditions.presence_of_element_located((By.ID, "video-title")))
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        first_result = soup.find("a", {"id": "video-title"})
        video_base_url = "https://www.youtube.com"
        return video_base_url + first_result["href"]

    def download_songs(self):
        for song_link in tqdm(self.songs_to_download, desc="Downloading songs"):
            name, artist, link = song_link
            self.download_song(name, artist, link)

    def download_song(self, name: str, artist: str, link: str):
        filename = f"{name} - {artist}.mp3"
        path = os.path.join(self.destination, filename)
        self.download_youtube_song(link, path)

    def download_youtube_song(self, url, output_path):
        folder = os.path.dirname(output_path)
        temp_video_path = os.path.join(folder, 'temp_video.mp4')
        yt = YouTube(url)
        # Download the video
        yt.streams.first().download(output_path=folder, filename='temp_video.mp4')
        # Load the video file
        video = VideoFileClip(temp_video_path)
        # Extract audio from the video
        audio = video.audio
        # Write the audio to a new file
        audio.write_audiofile(output_path)
        # Close the video and audio files
        video.close()
        audio.close()
        # Delete the temporary video file
        os.remove(temp_video_path)


def main(playlist_link: str):
    user_data_dir = r"C:\Users\alper\AppData\Local\Google\Chrome\User Data"

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument(f"user-data-dir={user_data_dir}")
    driver = webdriver.Chrome(
        'C:/Program Files/ChromeDriver/chromedriver.exe', options=chrome_options
    )

    fetcher = SpotifyFetcher(playlist_link, driver)
    fetcher.fetch_playlist()
    songs = fetcher.get_songs()
    downloader = YoutubeDownloader(songs, driver, fetcher.get_playlist_name())
    downloader.get_songs_to_download()
    downloader.download_songs()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download all songs from a Spotify playlist as an MP3')
    parser.add_argument("source", nargs=1, help="The link to the Spotify playlist")
    source = parser.parse_args().source[0]
    main(source)
