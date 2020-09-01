# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import xbmc
import api
import playbackmanager
import player
import state
import statichelper
import utils


class UpNextMonitor(xbmc.Monitor):
    """Service and player monitor for Kodi"""

    def __init__(self):
        self.state = state.UpNextState()
        self.player = player.UpNextPlayer()
        self.playbackmanager = playbackmanager.PlaybackManager(
            player=self.player,
            state=self.state
        )
        self.idle = False
        xbmc.Monitor.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def run(self):
        """Main service loop"""
        self.log('Service started', 0)
        interval = 10
        while not self.abortRequested():
            # Service monitor loop runs every 1s unless disabled or idle
            if (interval == 10
                    and not self.state.is_disabled()
                    and not self.idle):
                self.log('Active', 2)
                interval = 1
            # If disabled in settings increase loop interval to 10s and cleanup
            elif interval == 1 and self.state.is_disabled():
                self.log('Disabled', 0)
                self.playbackmanager.remove_popup()
                self.state.reset()
                interval = 10
            # If screensaver is active increase loop interval to 10s
            elif interval == 1 and self.idle:
                self.log('Idling', 2)
                interval = 10

            if self.waitForAbort(interval):
                break

            if (self.state.is_disabled()
                    or self.idle
                    or not self.state.is_tracking()):
                continue

            if bool(utils.get_property('PseudoTVRunning') == 'True'):
                self.state.set_tracking(False)
                continue

            if self.player.isExternalPlayer():
                self.log('Tracking: stopped - external player used', 2)
                self.state.set_tracking(False)
                continue

            if not self.player.isPlaying():
                self.log('Tracking: stopped - no file is playing', 2)
                self.state.set_tracking(False)
                continue

            last_file = self.state.get_last_file()
            tracked_file = self.state.get_tracked_file()
            current_file = self.player.getPlayingFile()
            # Already processed this playback before
            if last_file and last_file == current_file:
                self.log('Monitoring: old file is playing', 2)
                continue

            # New stream started without tracking being updated
            if tracked_file and tracked_file != current_file:
                self.log('Tracking: error - unknown file playing', 1)
                self.state.set_tracking(False)
                continue

            # Check that video stream has actually loaded and started playing
            # TODO: This check should no longer be required. Test and remove
            total_time = self.player.getTotalTime()
            # if total_time == 0:
            #     self.log('Tracking: error - zero length file', 1)
            #     self.state.set_tracking(False)
            #     continue

            play_time = self.player.getTime()
            popup_time = self.state.get_popup_time()
            # Media hasn't reach popup time yet, waiting a bit longer
            if play_time < popup_time:
                continue

            # Disable tracking to ensure second popup can't trigger
            # after next file has been requested but has not yet loaded
            self.state.set_tracking(False)

            # Store current file as last file played
            self.state.set_last_file(statichelper.from_unicode(current_file))

            # Start Up Next to handle playback of next file
            msg = 'Popup: launch - episode ({0}s runtime) ends in {1}s'
            msg = msg.format(total_time, total_time - play_time)
            self.log(msg, 2)
            self.playbackmanager.launch_up_next()

        self.log('Service stopped', 0)

    def track_playback(self, data=None, encoding=None):
        # Only process one start at a time unless addon data has been received
        if self.state.starting and not data:
            return
        # Increment starting counter
        self.state.starting += 1
        start_num = self.state.starting

        # onPlayBackEnded for current file can trigger after next file starts
        # Wait additional 5s after onPlayBackEnded or last start
        wait_limit = 5 * start_num
        wait_count = 0
        while not self.abortRequested() and wait_count < wait_limit:
            # Exit if starting state has been reset by playback error/end/stop
            if not self.state.starting:
                self.log('Tracking: failed - starting state reset', 1)
                return

            self.waitForAbort(1)
            wait_count += 1

        # Exit if no file playing
        total_time = self.player.isPlaying() and self.player.getTotalTime()
        if not total_time:
            return

        # Exit if starting counter has been reset or new start detected
        if start_num != self.state.starting:
            return
        self.state.starting = 0
        self.state.ended = 0

        is_playlist_item = api.get_playlist_position()
        has_addon_data = bool(data)
        is_episode = xbmc.getCondVisibility('videoplayer.content(episodes)')

        # Exit if Up Next playlist handling has not been enabled
        if is_playlist_item and not self.state.enable_playlist:
            self.log('Tracking: disabled - playlist handling not enabled', 2)
            return

        # Use new addon data if provided
        if data:
            self.state.set_addon_data(data, encoding)
        # Ensure that old addon data is not used. Note this may cause played in
        # a row count to reset incorrectly if playlist of mixed non-addon and
        # addon content is used
        else:
            self.state.reset_addon_data()
            has_addon_data = False

        # Start tracking if Up Next can handle the currently playing file
        if is_playlist_item or has_addon_data or is_episode:
            self.state.set_tracking(self.player.getPlayingFile())
            self.state.reset_queue()

            # Get details of currently playing file to save playcount
            if has_addon_data:
                self.state.handle_addon_now_playing()
            else:
                self.state.handle_library_now_playing()

            # Store popup time and check if cue point was provided
            self.state.set_popup_time(total_time)

        # Reset state if required
        elif self.state.is_tracking():
            self.state.reset()

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        self.log('Settings changed', 2)
        self.state.update_settings()

    def onScreensaverActivated(self):  # pylint: disable=invalid-name
        self.idle = True

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        self.idle = False

    def onNotification(self, sender, method, data):  # pylint: disable=invalid-name
        """Handler for Kodi state change and data transfer from addons"""

        if (utils.get_kodi_version() < 18 and method == 'Player.OnPlay'
                or method == 'Player.OnAVStart'):
            # Check whether Up Next can start tracking
            self.track_playback()

            # Disable any forces and remove any existing popups
            self.player.state['time']['force'] = False
            self.playbackmanager.remove_popup()

        elif method == 'Player.OnPause':
            # Update paused state if not forced
            if not self.player.state['paused']['force']:
                self.player.state['paused']['value'] = True

        elif method == 'Player.OnResume':
            # Update paused state if not forced
            if not self.player.state['paused']['force']:
                self.player.state['paused']['value'] = False

        elif method == 'Player.OnStop':
            self.state.reset_queue()
            # OnStop can occur before/after the next file has started playing
            if self.state.playing_next:
                self.state.playing_next = False
            # Reset state if Up Next has not requested the next file to play
            else:
                self.state.reset()

        # Data transfer from addons
        elif method.endswith('upnext_data'):
            decoded_data, encoding = utils.decode_json(data)
            sender = sender.replace('.SIGNAL', '')
            if decoded_data is None:
                msg = 'Addon: data error - {0} sent {1}'.format(sender, data)
                self.log(msg, 1)
                return
            decoded_data.update(id='%s_play_action' % sender)

            # Initial processing of data to start tracking
            self.track_playback(decoded_data, encoding)
