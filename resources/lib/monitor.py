# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import Monitor
from api import Api
from playbackmanager import PlaybackManager
from player import UpNextPlayer
from statichelper import from_unicode
from utils import decode_json, get_property, log as ulog


class UpNextMonitor(Monitor):
    """Service monitor for Kodi"""

    def __init__(self):
        """Constructor for Monitor"""
        self.api = Api()
        self.player = UpNextPlayer(__api=self.api)
        self.playback_manager = PlaybackManager(self.player)
        Monitor.__init__(self)

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def run(self):
        """Main service loop"""
        self.log('Service started', 0)

        while not self.abortRequested():
            # check every 1 sec
            if self.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

            if not self.player.is_tracking():
                continue

            if bool(get_property('PseudoTVRunning') == 'True'):
                self.player.set_tracking(False)
                continue

            # Next Up is disabled
            if self.player.is_disabled():
                self.player.set_tracking(False)
                continue

            if self.player.isExternalPlayer():
                self.log('Tracking: stopped - external player used', 2)
                self.player.set_tracking(False)
                continue

            if not self.player.isPlaying():
                self.log('Tracking: error - no file is playing', 1)
                self.player.set_tracking(False)
                continue

            last_file = self.player.get_last_file()
            tracked_file = self.player.get_tracked_file()
            current_file = self.player.getPlayingFile()
            # Already processed this playback before
            if last_file and last_file == current_file:
                self.log('Monitoring: old file is playing', 2)
                continue

            # New stream started without tracking being updated
            if tracked_file and tracked_file != current_file:
                self.log('Tracking: error - unknown file playing', 1)
                self.player.set_tracking(False)
                continue

            # Check that video stream has actually loaded and started playing
            # TODO: This check should no longer be required. Test and remove
            total_time = self.player.getTotalTime()
            if total_time == 0:
                self.log('Tracking: error - zero length file', 1)
                self.player.set_tracking(False)
                continue

            play_time = self.player.getTime()
            popup_time = self.player.get_popup_time()
            # Media hasn't reach popup time yet, waiting a bit longer
            if play_time < popup_time:
                continue

            # Disable tracking to ensure second popup can't trigger
            # after next file has been requested but has not yet loaded
            self.player.set_tracking(False)

            # Store current file and reset playing_next state
            self.player.set_last_file(from_unicode(current_file))

            # Start Up Next to handle playback of next file
            msg = 'Popup: launch - episode ({0}s runtime) ends in {1}s'
            msg = msg.format(total_time, total_time - play_time)
            self.log(msg, 2)
            self.playback_manager.launch_up_next()

        self.log('Service stopped', 0)

    def onNotification(self, sender, method, data):  # pylint: disable=invalid-name
        """Notification event handler for accepting data from add-ons"""
        # Ignore notifications not targeting Up Next
        if not method.endswith('upnext_data'):
            return

        decoded_data, encoding = decode_json(data)
        sender = sender.replace('.SIGNAL', '')
        if decoded_data is None:
            msg = 'Addon: data error - {0} sent {1}'.format(sender, data)
            self.log(msg, 1)
            return
        decoded_data.update(id='%s_play_action' % sender)

        self.player.track_playback(decoded_data, encoding)
