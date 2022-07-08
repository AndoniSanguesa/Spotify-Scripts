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

offset = 0
albums = sp.current_user_saved_albums(limit=20, offset=offset)["items"]

while len(albums) == 20:
    temp_albums = []
    for album in albums:
        print(album["album"]["name"])
        temp_albums.append(album["album"]["id"])
    
    sp.current_user_saved_albums_delete(temp_albums)
    offset += 20
    albums = sp.current_user_saved_albums(limit=20, offset=offset)["items"]


