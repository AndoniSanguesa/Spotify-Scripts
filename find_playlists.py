import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os

load_dotenv()

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
app_redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
user_name = os.getenv("SPOTIFY_USER_NAME")

scope = "playlist-modify-private playlist-read-private playlist-modify-public user-library-read user-library-modify"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(redirect_uri=app_redirect_uri, scope=scope, client_id=client_id, client_secret=client_secret))

user_id = sp.current_user()["id"]

playlists = sp.user_playlists('spotify')

cnt = 0
with open("playlist_names.txt", 'w', encoding="utf-8") as f:
    while playlists:
        for i, playlist in enumerate(playlists['items']):
            print(cnt)
            cnt += 1
            f.write(playlist['name'] + '\n')
        playlists = sp.next(playlists)

