import src.migrations.clients.Youtube as Youtube
import src.migrations.clients.Spotify as Spotify
from PyInquirer import prompt
from examples import custom_style_2
import sys
from colorama import Fore, Back, Style


class Migrator:
    """Migration class for Youtube -> Spotify"""

    def __init__(self):
        # initialize and authenticate Youtube client instances
        self.YoutubeAPI = Youtube.Client()
        self.YoutubeAPI.authenticate()
        # initialize and authenticate Spotify client instances
        self.SpotifyAPI = Spotify.Client()
        self.SpotifyAPI.authenticate()
        # self._youtube_playlist = None
        self._songs = []

    # MAIN
    def execute(self):
        youtube_playlist = self._get_playlist_from_input()
        if self._get_spotify_matches(youtube_playlist['items']) is False:
            print(Style.BRIGHT + Back.RED + Fore.WHITE +
                  'ERROR:' + Style.RESET_ALL)
            print(Style.NORMAL + Fore.RED +
                  'No matches found. Terminating...' + Style.RESET_ALL)
            sys.exit()
        uri_list = self._confirm_spotify_matches()
        self._transfer_songs(uri_list, youtube_playlist['title'])

    # HELPER METHODS
    def _get_playlist_from_input(self):
        """
        Fetch Youtube playlists for user.
        Ask them to choose one for transferring.
        """
        playlists = self.YoutubeAPI.get_all_playlists()                         # fetch the user's playlists
        question = [                                                            # prompt user to select one
            {
                'type': 'list',
                'name': 'selectedPlaylist',
                'message': "Which Youtube playlist would you like to transfer to Spotify?",
                'choices': [{'value': idx, 'name': item["snippet"]["title"]}
                            for idx, item in enumerate(playlists["items"])]
            }
        ]
        answer = prompt(question, style=custom_style_2)
        selectedIndex = answer['selectedPlaylist']
        selectedPlaylistId = playlists['items'][selectedIndex]['id']
        selectedPlaylistTitle = playlists['items'][selectedIndex]['snippet']['title']
        playlist_items = self.YoutubeAPI.get_playlist_items(selectedPlaylistId)
        # add playlist title onto the obj
        playlist_items['title'] = selectedPlaylistTitle
        return playlist_items

    def _get_spotify_matches(self, items):
        """
        Fetch list of spotify search results for given array of Youtube videos.
        Youtube_dl track parsing broken after Youtube site update
        Instead, manually parse the video title. Most follow a similar format:
        {Artist name} - {Track name} {(Optional Parenthetical Statement that gets ignored here)}
        """
        print('Matching YouTube videos to Spotify songs.')
        # iterate through youtube playlist and search spotify for match
        no_matches_found = True  # will remain true if none are found
        for item in items:
            title = item['snippet']['title']
            print(f"Searching Spotify for: {title}")
            try:
                # try to parse (likely) artist and track name from title
                artist, track = title.split('-')
                artist = artist.strip()
                track = track.strip()
                # remove parenthetical substr e.g. (Official Music Video)
                parenth_index = track.find('(')
                if parenth_index == -1:
                    parenth_index = len(track)
                track = track[:parenth_index]
            except:
                artist = 'Unknown'
                track = title
            # construct new song
            song = {
                # from youtube
                "youtube_title": title,
                "youtube_track": track,
                "youtube_artist": artist,
                # from querying spotify search API
                "spotify_match": self.SpotifyAPI.get_search_result(track, artist)
            }
            if song['spotify_match'] is not None:
                print(Fore.GREEN + "Match found." + Style.RESET_ALL)
                no_matches_found = False
            else:
                print(Fore.RED + "No match found." + Style.RESET_ALL)
            self._songs.append(song)
        print()
        return no_matches_found == False

    def _confirm_spotify_matches(self):
        """
        Prompt user with checkbox list of matches from search results
        Ask them to confirm the list before proceeding to transfer to Spotify
        They may uncheck any box to skip over during transfer
        If no match found, checkbox should be disabled
        """
        answers = {}
        answers['transfer_list'] = []
        while len(answers['transfer_list']) == 0:
            questions = [
                {
                    'type': 'checkbox',
                    'message': 'Confirm songs for transfer. Uncheck to skip.',
                    'name': 'transfer_list',
                    'choices': [
                        {
                            # 'value': idx, causes bug where 'checked' is ignored -- will parse index out of name
                            'name': (str(idx + 1) + ': ' + song['spotify_match']['artists'][0]['name'] + ' - ' + song['spotify_match']['name']
                                     if song['spotify_match']
                                     else str(idx + 1) + ': ' + song['youtube_title']),
                            'checked': True if song['spotify_match'] is not None else False,
                            'disabled': False if song['spotify_match'] is not None else "No match found"
                        } for idx, song in enumerate(self._songs)
                    ],
                    # validation for checkboxes broken in package - need to refactor
                    # could use Questionary instead: https://github.com/tmbo/questionary
                    # using while loop as quick fix
                    'validate': lambda answer: 'You must choose at least one song to transfer.' \
                    if len(answer) == 0 else True
                }
            ]
            answers = prompt(questions, style=custom_style_2)
        # filter our songs list for just the ones selected by the user
        selected_indices = []
        for song in answers['transfer_list']:
            colon_idx = song.find(':')
            original_idx = int(song[0:colon_idx]) - 1
            selected_indices.append(original_idx)
        return [self._songs[i]['spotify_match']['uri'] for i in selected_indices]

    def _transfer_songs(self, song_list, youtube_playlist_title):
        question = [                                                            # prompt user to select one
            {
                'type': 'list',
                'name': 'transfer_method',
                'message': "Would you like to create a new playlist or add to an existing one?",
                'choices': [
                    {
                        'name': "Create new playlist"
                    },
                    {
                        'name': "Add to existing playlist"
                    }
                ]
            }
        ]
        answer = prompt(question, style=custom_style_2)['transfer_method']
        if answer == 'Create new playlist':
            question = [
                {
                    'type': 'input',
                    'name': 'new_playlist_name',
                    'message': 'Enter a name for your new playlist:',
                    'default': youtube_playlist_title,
                    'validate': lambda answer: 'You must enter a name for your playlist.'
                    if len(answer) == 0 else True
                }
            ]
            new_playlist_name = prompt(question, style=custom_style_2)[
                'new_playlist_name']
            playlist_id = self.SpotifyAPI.create_playlist(new_playlist_name)
        else:
            # get spotify playlists
            user_playlists = self.SpotifyAPI.get_all_playlists()
            # prompt for selection and
            # filter out playlists that the user can\'t modify
            user_id = self.SpotifyAPI.get_user_id()
            question = [                                                            # prompt user to select one
                {
                    'type': 'list',
                    'name': 'selectedPlaylist',
                    'message': "Which playlist would you like to transfer the songs to?",
                    'choices': [
                        {
                            'value': idx,
                            'name': playlist["name"]
                            # 'disabled': False if (playlist['owner']['id'] == user_id or playlist['collaborative'] == True)
                            #     else "Unable to modify this playlist"
                        } for idx, playlist in enumerate(user_playlists)
                        if (playlist['owner']['id'] == user_id
                            or playlist['collaborative'] == True)]
                }
            ]
            answer = prompt(question, style=custom_style_2)
            selectedIndex = answer['selectedPlaylist']
            # get the playlist_id
            playlist_id = user_playlists[selectedIndex]['id']
        # add to songs to new or selected playlist and print out the URL
        playlist_URL = self.SpotifyAPI.add_songs_to_playlist(
            song_list, playlist_id)
        print(Fore.YELLOW + f"\nDone! Playlist available at:", end=" ")
        print(Fore.BLUE + playlist_URL + Style.RESET_ALL + "\n")
