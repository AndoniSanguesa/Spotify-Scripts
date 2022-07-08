from bs4 import BeautifulSoup
import requests
import time
import pickle
import os
from requests.exceptions import ReadTimeout
from urllib3.exceptions import ReadTimeoutError
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import datetime
from Levenshtein import ratio
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
app_redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
user_name = os.getenv("SPOTIFY_USER_NAME")

scope = "playlist-modify-private playlist-read-private playlist-modify-public user-library-read user-library-modify user-read-playback-position"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(redirect_uri=app_redirect_uri, scope=scope, client_id=client_id, client_secret=client_secret))

ARTIST_PLAYLIST_FILE = 'spotify_artist_playlist_dict.pickle'
PLAYLIST_IDS_FILE = 'playlist_ids.pickle'
MAX_EXPLICIT_MIX_PERCENT = 0.03



def save_playlist_ids(playlist_ids):
    with open(PLAYLIST_IDS_FILE, 'wb') as f:
        pickle.dump([time.time(), playlist_ids], f)
    print("Playlist ids saved to " + PLAYLIST_IDS_FILE + "!")

def get_spotify_playlist_ids():
    print("Scraping everynoise.com for playlist ids...")
    base_url = 'https://everynoise.com/worldbrowser.cgi'

    start_scrape_time = time.time()

    global_html = requests.get(base_url).text

    soup = BeautifulSoup(global_html, 'html.parser')

    country_divs = soup.find_all('div', class_='countryname')

    country_hrefs = []

    playlist_ids = set()

    for div in country_divs:
        country_hrefs.append(div.find('a')['href'])

    if '' in country_hrefs:
        country_hrefs.remove('')

    for href in country_hrefs:
        country_code = href.split("=")[-1]
        print("Scraping country: " + country_code)
        country_html = requests.get(base_url + href)
        soup = BeautifulSoup(country_html.text, 'html.parser')
        playlist_divs = soup.find_all('div', class_='playlists')
        cat_cnt = 0
        for div in playlist_divs:
            playlist_hrefs = div.find_all('a')

            for href in playlist_hrefs:
                playlist_ids.add(href['href'])
            cat_cnt += 1

    end_scrape_time = time.time()

    print("Scraped " + str(len(playlist_ids)) + " playlists in " + str(end_scrape_time - start_scrape_time) + " seconds")

    save_playlist_ids(playlist_ids)

    return playlist_ids


def is_playlist_bad(playlist_id):
    playlist_tracks = sp.playlist_tracks(playlist_id)
    explicit_tracks = 0
    remix_tracks = 0
    if playlist_tracks is None:
        print("Playlist could not be loaded, retrying in 5 seconds")
        time.sleep(5)
        playlist_tracks = sp.playlist_tracks(playlist_id)
    
    if playlist_tracks is None:
        return True

    num_songs = playlist_tracks["total"]

    while playlist_tracks:
        for track in playlist_tracks["items"]:
            if track['track'] is None:
                continue
            explicit_tracks += 1 if track['track']['explicit'] else 0
            remix_tracks += 1 if "mix" in track['track']['name'].lower() else 0
        playlist_tracks = sp.next(playlist_tracks)
        
    return explicit_tracks / num_songs > MAX_EXPLICIT_MIX_PERCENT or remix_tracks / num_songs > MAX_EXPLICIT_MIX_PERCENT


def process_playlist(playlist_id, artist_playlist_dict):
    playlist_name = sp.playlist(playlist_id)['name']
    if not is_playlist_bad(playlist_id):
        playlist_tracks = sp.playlist_tracks(playlist_id)
        while playlist_tracks:
            for track in playlist_tracks['items']:
                if track['track'] is None or track['track']['artists'] is None:
                    continue
                for artist in track["track"]["artists"]:
                    if artist["name"] not in artist_playlist_dict:
                        artist_playlist_dict[artist["name"].lower()] = set()
                    artist_playlist_dict[artist["name"].lower()].add(playlist_name)
            playlist_tracks = sp.next(playlist_tracks)
    return artist_playlist_dict

def generate_artist_playlist_dict(playlist_ids):
    artist_playlist_dict = {}
    cnt = 0
    for playlist_id in playlist_ids:
        playlist_name = "????"
        succeeded = False
        while not succeeded: 
            try:
                playlist_name = sp.playlist(playlist_id)['name']
                print(f"Processing playlist {cnt}: {playlist_name}")
                artist_playlist_dict = process_playlist(playlist_id, artist_playlist_dict)
                succeeded = True
            except (ReadTimeout, ReadTimeoutError):
                print("Timeout error during processing of playlist: " + playlist_name +", Retrying in 5 seconds")
                time.sleep(5)
        cnt += 1
    

    return artist_playlist_dict


def check_generate_playlist_ids():
    if os.path.isfile(PLAYLIST_IDS_FILE):
        with open(PLAYLIST_IDS_FILE, 'rb') as f:
            last_scrape_time, playlist_ids = pickle.load(f)
        print("Last scrape time: " + str(datetime.datetime.fromtimestamp(last_scrape_time)))
        print("Last scraped playlist ids: " + str(len(playlist_ids)))
        if last_scrape_time + 86400 > time.time():
            rescrape = input("Last scrape was less than 24 hours ago. Do you want to scrape again? If not, previous scrape will be used to generate database. (y/n) ")
            while rescrape != 'y' and rescrape != 'n':
                rescrape = input("Please enter 'y' or 'n': ")
            if rescrape == 'y':
                return True
            return False
    return True


def check_generate_artist_playlist_dict():
    if os.path.isfile(ARTIST_PLAYLIST_FILE):
        last_generation, artist_playlist_dict = pickle.load(open(ARTIST_PLAYLIST_FILE, 'rb'))
        if last_generation + 2.628e+6 > time.time():
            print("Database was last generated: " + str(datetime.datetime.fromtimestamp(last_generation)))
            regenerate = input("Database was last created less than a month ago. Are you sure you want to regenerate it? (y/n) ")
            while regenerate != 'y' and regenerate != 'n':
                regenerate = input("Please enter 'y' or 'n': ")
            if regenerate == 'y':
                return True
            return False
    return True


def find_most_similar_artist(artist_name, artist_playlist_dict):
    """Finds key in dictionary closest to artist_name"""
    best_artist = ""
    worst_score = 0

    for artist in artist_playlist_dict:
        score = ratio(artist, artist_name)
        if score > worst_score:
            worst_score = score
            best_artist = artist
    return best_artist


def main():
    get_ids = input("Do you want to generate a new database? (y/n) ")

    while get_ids != 'y' and get_ids != 'n':
        get_ids = input("Please enter 'y' or 'n': ")

    if get_ids == 'y':
        should_generate_artist_playlist_dict = check_generate_artist_playlist_dict()
        
        if should_generate_artist_playlist_dict:
            should_generate_playlists = check_generate_playlist_ids()
            if should_generate_playlists:
                playlist_ids = get_spotify_playlist_ids()
                save_playlist_ids(playlist_ids)
            else:
                _, playlist_ids = pickle.load(open(PLAYLIST_IDS_FILE, 'rb'))
            print("Generating databse...")
            artist_playlist_dict = generate_artist_playlist_dict(playlist_ids)
            with open(ARTIST_PLAYLIST_FILE, 'wb') as f:
                pickle.dump([time.time(), artist_playlist_dict], f)
        else:
            _, artist_playlist_dict = pickle.load(open(ARTIST_PLAYLIST_FILE, 'rb'))

    else:
        if not os.path.isfile(ARTIST_PLAYLIST_FILE):
            print("No playlist database found. Please run the script again with 'y' as input.")
            exit()
        last_generation, artist_playlist_dict = pickle.load(open(ARTIST_PLAYLIST_FILE, 'rb'))
        if last_generation + 2.628e+6 < time.time():
            print("Database was last generated: " + str(datetime.datetime.fromtimestamp(last_generation)))
            regenerate = input("Database has not be regenerated in over a month, are you sure you do not want to regenerate it? (y/n)")
            while regenerate != 'y' and regenerate != 'n':
                regenerate = input("Please enter 'y' or 'n': ")
            if regenerate == 'y':
                should_generate_playlists = check_generate_playlist_ids()
                if should_generate_playlists:
                    playlist_ids = get_spotify_playlist_ids()
                    save_playlist_ids(playlist_ids)
                
                artist_playlist_dict = generate_artist_playlist_dict(playlist_ids)
                with open(ARTIST_PLAYLIST_FILE, 'wb') as f:
                    pickle.dump([time.time(), artist_playlist_dict], f)

    artist = ""

    while True:
        artist = input("Enter artist name: ")

        if artist not in artist_playlist_dict:
            closest_artist = find_most_similar_artist(artist, artist_playlist_dict)
            is_closest_artist = input(f"Artist not found. Did you mean {closest_artist}? (y/n) ")
            while is_closest_artist != 'y' and is_closest_artist != 'n':
                is_closest_artist = input("Please enter 'y' or 'n': ")
            if is_closest_artist == 'y':
                artist = closest_artist
            else:
                continue

        artist_playlists = artist_playlist_dict[artist]

        print(f"\nArtist: {artist} is found in {len(artist_playlists)} 'good' playlists:")
        print("-------------------------------------------------------")
        print("\n".join(artist_playlists))

main()