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

import eyed3


class Song:
    def __init__(self, name: str, artist: str, album: str, track_num: int, link: str):
        self.name = name
        self.artist = artist
        self.album = album
        self.track_num = track_num
        self.link = link

    def __hash__(self):
        return hash(self.track_num)


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
        onetrust_close_btn = wait.until(expected_conditions.presence_of_element_located((By.CLASS_NAME, 'onetrust-close-btn-handler')))
        onetrust_close_btn.click()
        js_scroll = "document.querySelectorAll('[data-overlayscrollbars-viewport=\"scrollbarHidden overflowXHidden overflowYScroll\"]')[1].scrollBy(0, 300)"
        time.sleep(1)

        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        self.playlist_name = soup.find("meta", {"name": "twitter:title"})["content"]
        self.song_count = int(soup.find("meta", {"name": "music:song_count"})["content"])
        pbar = tqdm(total=self.song_count, desc="Fetching songs from Spotify")

        songs = set()
        while True:
            prev_song_count = len(songs)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            for track_row in soup.find_all("div", {"data-testid": "tracklist-row"}):
                try:
                    track_num_div = track_row.find("div", {"aria-colindex": "1"})
                    name_artist_div = track_row.find("div", {"aria-colindex": "2"}).find("div")
                    album_div = track_row.find("div", {"aria-colindex": "3"})
                except AttributeError:
                    break
                name = name_artist_div.find("div", {"dir": "auto"}).text
                artist = name_artist_div.find("a", {"dir": "auto"}).text
                album = album_div.find("a", {"dir": "auto"}).text
                track_num = int(track_num_div.find("span", {"data-encore-id": "text"}).text)

                if track_num > len(songs):
                    songs.add(Song(name, artist, album, track_num, ""))
            new_song_count = len(songs) - prev_song_count
            pbar.update(new_song_count)
            self.driver.execute_script(js_scroll)
            time.sleep(0.5)

            if not new_song_count:
                break

        self.songs = list(songs)

    def get_songs(self) -> list[Song]:
        return self.songs

    def get_playlist_name(self) -> str:
        return self.playlist_name


class YoutubeDownloader:
    def __init__(self, songs: list[Song], d, name):
        self.driver = d
        self.songs = songs
        self.playlist_name = name

    def get_songs_to_download(self):
        for song in tqdm(list(filter(lambda s: not os.path.exists(get_path(s.name, s.artist, self.playlist_name)), self.songs)), desc="Fetching YouTube links"):
            link = self.get_song_link(song)
            song.link = link

    def get_song_link(self, song: Song) -> str:
        self.driver.set_page_load_timeout(15)
        base_url = "https://www.youtube.com/results?search_query="
        search_term = f"{song.name} - {song.artist}"
        url = base_url + search_term.replace(" ", "+")
        try:
            self.driver.get(url)
            wait = WebDriverWait(self.driver, 15)
            wait.until(expected_conditions.presence_of_element_located((By.ID, "video-title")))
        except:
            with open("failed.txt", "a") as f:
                f.write(f"{song.name} - {song.artist}\n")
            print(f"Failed to find {song.name} - {song.artist}")
            return ""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        first_result = soup.find("a", {"id": "video-title"})
        video_base_url = "https://www.youtube.com"
        return video_base_url + first_result["href"]

    def download_songs(self):
        for song in tqdm(self.songs, desc="Downloading songs"):
            if song.link:
                self.download_song(song)

    def download_song(self, song: Song):
        path = get_path(song.name, song.artist, self.playlist_name)
        success = self.download_youtube_song(song.link, path)
        if success:
            self.set_song_metadata(path, song)

    def download_youtube_song(self, url, output_path):
        if os.path.exists(output_path):
            return
        folder = os.path.dirname(output_path)
        temp_video_path = os.path.join(folder, 'temp_video.mp4')
        yt = YouTube(url)
        # Download the video
        try:
            yt.streams.first().download(output_path=folder, filename='temp_video.mp4')
        except:
            with open("failed.txt", "a") as f:
                f.write(f"{url},{output_path}\n")
            print(f"Failed to download {url}")
            return False
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
        return True

    def set_song_metadata(self, path: str, song: Song):
        audiofile = eyed3.load(path)
        if audiofile.tag is not None:
            if song.name:
                audiofile.tag.title = song.name
            if song.artist:
                audiofile.tag.artist = song.artist
            if song.album:
                audiofile.tag.album = song.album
            if song.track_num:
                audiofile.tag.track_num = song.track_num
            audiofile.tag.save()


def get_path(name: str, artist: str, playlist_name: str) -> str:
    destination = os.path.join(rf"C:\Users\alper\Music", playlist_name)
    os.makedirs(destination, exist_ok=True)
    not_allowed = ["<", ">", ":", "\"", "/", "\\", "|", "?", "*"]
    filename = f"{name} - {artist}.mp3"
    for char in not_allowed:
        filename = filename.replace(char, "")
    return os.path.join(destination, filename)


def main(playlist_link: str):
    user_data_dir = r"C:\Users\alper\AppData\Local\Google\Chrome\User Data"

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--silent")
    # chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    # chrome_options.add_argument(f"--profile-directory=Default")
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
