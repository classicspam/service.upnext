# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the actual UpNext script"""

from __future__ import absolute_import, division, unicode_literals

from random import choice as randchoice

import dummydata
import monitor
import player
import popuphandler
import state
import utils
import xbmcaddon
from settings import SETTINGS


def test_popup(popup_type, simple_style=False):
    db_type = randchoice(('movies', 'episodes'))
    selection = randchoice((0, 2))

    test_video = dummydata.LIBRARY[db_type][selection]
    test_next_video = dummydata.LIBRARY[db_type][selection + 1]

    # Create test state object
    test_state = state.UpNextState()
    # Simulate after file has started
    test_state.starting = 0
    # Use test episode to simulate next playing episode used for popup display
    test_state.next_item = utils.create_item_details(test_next_video, 'playlist')

    # Choose popup style
    SETTINGS.simple_mode = bool(simple_style)
    # Choose popup type
    if popup_type == 'stillwatching':
        test_state.played_in_a_row = SETTINGS.played_limit

    # Create test player object
    test_player = player.UpNextPlayer()
    # Simulate player state
    test_player.player_state.update({
        # 'external_player': {'value': False, 'force': False},
        # Simulate file is playing
        'playing': {'value': True, 'force': True},
        # 'paused': {'value': False, 'force': False},
        # Simulate dummy file name
        'playing_file': {'value': test_video['file'], 'force': True},
        'speed': {'value': 1, 'force': True},
        # Simulate playtime of endtime minus 10s
        'time': {'value': test_video['runtime'] - 10, 'force': True},
        # Simulate endtime based on dummy episode
        'total_time': {'value': test_video['runtime'], 'force': True},
        # 'next_file': {'value': None, 'force': False},
        # Simulate episode media type is being played based on dummy episode
        'type': {'value': 'episode', 'force': True},
        # Simulate stop to ensure actual playback doesnt stop when popup closes
        'stop': {'force': True}
    })
    # Simulate player state could also be done using the following
    test_player.player_state.set('playing', True, force=True)
    test_player.player_state.set('playing_file', test_video['file'], force=True)
    test_player.player_state.set('speed', 1, force=True)
    test_player.player_state.set('time', (test_video['runtime'] - 10), force=True)
    test_player.player_state.set('total_time', test_video['runtime'], force=True)
    test_player.player_state.set('type', 'episode', force=True)
    test_player.player_state.set('stop', force=True)

    # Create a test popuphandler and create an actual popup for testing
    has_next_item = popuphandler.UpNextPopupHandler(
        player=test_player, state=test_state
    ).start()

    return has_next_item


def test_upnext(popup_type, simple_style=False):
    test_episode = dummydata.LIBRARY['episodes'][0]
    test_next_episode = dummydata.LIBRARY['episodes'][1]

    # Create test state object
    test_state = state.UpNextState()
    # Simulate after file has started
    test_state.starting = 0

    # Choose popup style
    SETTINGS.simple_mode = bool(simple_style)
    # Choose popup type
    if popup_type == 'stillwatching':
        test_state.played_in_a_row = SETTINGS.played_limit

    # Create test player object
    test_player = player.UpNextPlayer()
    # Simulate player state
    test_player.player_state.update({
        # 'external_player': {'value': False, 'force': False},
        # Simulate file is playing
        'playing': {'value': True, 'force': True},
        # 'paused': {'value': False, 'force': False},
        # Simulate dummy file name
        'playing_file': {'value': test_episode['file'], 'force': True},
        'next_file': {'value': test_next_episode['file'], 'force': True},
        'speed': {'value': 1, 'force': True},
        # Simulate playtime to start of dummy episode
        'time': {'value': 0, 'force': True},
        # Simulate endtime based on dummy episode
        'total_time': {'value': test_episode['runtime'], 'force': True},
        # Simulate episode media type is being played based on dummy episode
        'type': {'value': 'episode', 'force': True},
        # Simulate stop to ensure actual playback doesn't stop on popup close
        'stop': {'force': True}
    })
    # Simulate player state could also be done using the following
    test_player.player_state.set('playing', True, force=True)
    test_player.player_state.set('playing_file', test_episode['file'], force=True)
    test_player.player_state.set('next_file', test_next_episode['file'], force=True)
    test_player.player_state.set('speed', 1, force=True)
    test_player.player_state.set('time', 0, force=True)
    test_player.player_state.set('total_time', test_episode['runtime'], force=True)
    test_player.player_state.set('type', 'episode', force=True)
    test_player.player_state.set('stop', force=True)

    test_monitor = monitor.UpNextMonitor()
    test_monitor.start(player=test_player, state=test_state)

    return test_monitor


def open_settings():
    xbmcaddon.Addon().openSettings()
    return True


def run(argv):
    """Route to API method"""

    # Example usage:
    #   RunScript(service.upnext,test_window,upnext)
    #   RunScript(service.upnext,test_window,stillwatching)
    #   RunScript(service.upnext,test_window,upnext,simple)
    #   RunScript(service.upnext,test_window,stillwatching,simple)
    if len(argv) > 2:
        if argv[1] == 'test_window':
            test_method = test_popup
        else:
            test_method = test_upnext
        # Fancy style popup
        if len(argv) == 3:
            return test_method(argv[2])
        # Simple style popup
        if len(argv) == 4:
            return test_method(argv[2], argv[3])
        return False
    return open_settings()
