import vlc
import os
import signal
import sys
import keyboard
import time
import glob
import random
from win32gui import GetWindowText, GetForegroundWindow, MoveWindow
import argparse

import series_config as config


#RUN vlc.exe --reset-plugins-cache IF YOU GET STALE PLUGIN CACHE... SHIT DOESNT DO IT AUTO CAUSE ??????

class Series:
    """
    Save file format:
        [FILE]
        TIME #Float between 0 and 1
    TODO: DONE FOR NOW WOOOO
    """

    def __init__(self):
        self.parse_config()
        self.fixoptions()

        signal.signal(signal.SIGINT, self.signal_handler)
        self.fullscreen = False
        self.winsize = False
        self.toggle = True
        self.series = None

        if self.args.testing:
            self.test_method()
            sys.exit(0)

        # self.output = sys.stdout
        # sys.stdout = None
        # sys.stderr = None

        if self.args.fork:
            print('Forking disabled, retry without fork')
            print('Just use pythonw...')
            sys.exit(1)
        elif self.args.ver:
            self.print_version()
            sys.exit(0)
        elif self.args.random:
            print('picking random episode')
            if self.args.reshuffle:
                self.shufflestuff()
            self.random_loop()
        else:
            self.series = self.args.series
            self.play_series(self.series_dirs[self.series])
            sys.exit(0)


    def print_version(self):
        """Print version of this vlc.py and of the libvlc"""
        try:
            print('%s: %s (%s)' % (os.path.basename(__file__), __version__, build_date))
            print('LibVLC version: %s (%#x)' % (bytes_to_str(libvlc_get_version()), libvlc_hex_version()))
            print('LibVLC compiler: %s' % bytes_to_str(libvlc_get_compiler()))
            if plugin_path:
                print('Plugin path: %s' % plugin_path)
        except Exception:
            print('Error: %s' % sys.exc_info()[1])

    def parse_config(self):
        self.random_dirs = config.random_dirs
        self.series_dirs = config.series
        self.possible_series = list(self.series_dirs.keys())
        self.endings = config.endings

    def fixoptions(self):
        series = self.possible_series + ['random']
        options = argparse.ArgumentParser()
        options.add_argument('--fork', help='subproc this shit', action='store_true', dest='fork')
        options.add_argument('-v', help='show libvlc ver', action='store_true', dest='ver')

        group = options.add_mutually_exclusive_group(required=True)
        group.add_argument('-s', '--series', type=str, dest='series',
            help='which series to start (default: random)', choices=series, default='random')
        group.add_argument('--random', help='random episode of random show', action='store_true', dest='random')
        group.add_argument('--test', help='testing stuff', action='store_true', dest='testing')

        options.add_argument('--reshuffle', help='reshuffle random episodes, does nothing without --random', action='store_true', dest='reshuffle')

        self.args = options.parse_args()

    def signal_handler(self, sig, frame):
        '''
        Is really of no use at the moment.. added for potential future use.
        '''
        try:
            print('Stopping playback')
            self.player.stop()
            print('Playback stopped')
        except Exception:
            print('Error while stopping, nothing bad happens... probably')

        print('You pressed Ctrl+C. Progress will not be saved. GOOD JOB!')
        sys.exit(0)

    def test_method(self):
        pass

    def shufflestuff(self):
        all_files = []
        for ending in self.endings:
            for dir in self.random_dirs:
                files = [f for f in glob.glob(dir + '/**/**/**/*' + ending, recursive=True)]
                for file in files:
                    all_files.append(file)
        random.shuffle(all_files )
        if all_files:
            with open('random_episodes.txt', 'w') as fout:
                for file in all_files:
                    fout.write(file + '\n')

    def random_loop(self):
        files = []
        while len(files) == 0:
            with open('random_episodes.txt', 'r') as fout:
                files = fout.readlines()
            if len(files) == 0:
                print('No files, reshuffling')
                self.shufflestuff()

        self.current_file = files[0].strip()
        # print(type(self.current_file))
        print(self.current_file)
        # print(os.path.exists(self.current_file))
        if os.path.exists(self.current_file):
            self.player = vlc.MediaPlayer(self.current_file)
            self.player.play()
            time.sleep(0.2)
            while not self.player.is_playing():
                time.sleep(0.5)
        else:
            print('FILE ERROR: {}'.format(self.current_file))
            sys.exit(1)
        self.main_loop(files)

    def play_series(self, dir):
        episodes = self.get_episodes([dir])
        saved_data = self.get_saved_data(self.series)
        progress = 0
        if saved_data == -1:
            print('Saved data error')
        else:
            try:
                index = episodes.index(saved_data[0].strip())
                del episodes[:index]
                progress = saved_data[1]
            except Exception:
                print('EXCEPTION')

        self.current_file = episodes[0]
        if os.path.exists(self.current_file):
            print(self.current_file)
            self.player = vlc.MediaPlayer(self.current_file)
            self.player.play()
            time.sleep(0.2)
            while not self.player.is_playing():
                time.sleep(0.5)
            self.player.set_position(float(progress))

        self.main_loop(episodes)

    def get_saved_data(self, series):
        data_file = series + '_save.txt'
        if os.path.exists(data_file):
            with open(data_file, 'r') as fout:
                all_data = fout.readlines()
        else:
            return -1
        return all_data

    def get_episodes(self, dirs):
        all_files = []
        for ending in self.endings:
            for dir in dirs:
                files = [f for f in glob.glob(dir + '/**/*' + ending, recursive=True)]
                for file in files:
                    all_files.append(file.strip())
        return all_files

    def save_data_to_file(self, progress):
        data_file = self.series + '_save.txt'
        with open(data_file, 'w') as fout:
            fout.write(self.current_file + '\n')
            fout.write(str(progress))

    def main_loop(self, episodes):
        if len(episodes) == 0:
            print('No episodes')
            sys.exit(2)
        while True:
            ret_code = self.resize_and_keybinds()
            if ret_code == 5 or self.player.get_position() >= 0.999:
                self.player.pause()
                episodes.pop(0)
                if len(episodes) == 0:
                    print('No more episodes')
                    sys.exit(0)
                next_file = episodes[0].strip()
                new_med = vlc.Media(next_file)
                self.player.set_media(new_med)
                self.player.play()
                time.sleep(0.2)
                while not self.player.is_playing():
                    time.sleep(0.5)
                self.current_file = next_file
                print(self.current_file)
                if self.fullscreen:
                    self.player.set_fullscreen(True)
                else:
                    self.winsize = False
                time.sleep(0.5)
            elif ret_code == 2: #exiting
                print('See ya')
                if not self.args.random:
                    cur_pos = self.player.get_position()
                    self.save_data_to_file(cur_pos)
                else:
                    with open('random_episodes.txt', 'w') as fout:
                        for file in episodes:
                            fout.write(file)
                sys.exit(0)

    def resize_and_keybinds(self):
        '''
        return values:
            2 = exit
            5 = skip
            0 = nothing
        '''
        if (GetWindowText(GetForegroundWindow()) == 'VLC (Direct3D11 output)'):
            if not self.winsize:
                MoveWindow(GetForegroundWindow(), 150, 30, 1600, 1000, True)
                self.winsize = True
            if keyboard.is_pressed('space'):
                if self.toggle:
                    self.player.pause()
                    self.toggle = False
                    time.sleep(0.5)
                else:
                    self.player.play()
                    self.toggle = True
                    time.sleep(0.5)
            if keyboard.is_pressed('ctrl+d'):
                self.player.set_time(self.player.get_time()+60000)
                time.sleep(0.5)
            elif keyboard.is_pressed('d'):
                self.player.set_time(self.player.get_time()+15000)
                time.sleep(0.5)
            if keyboard.is_pressed('ctrl+a'):
                self.player.set_time(self.player.get_time()-60000)
                time.sleep(0.5)
            elif keyboard.is_pressed('a'):
                self.player.set_time(self.player.get_time()-15000)
                time.sleep(0.5)
            if keyboard.is_pressed('shift+f'):
                self.player.toggle_fullscreen()
                self.fullscreen = not self.fullscreen
                time.sleep(0.5)
            if keyboard.is_pressed('y'):
                return 5
            if keyboard.is_pressed('esc'):
                return 2
            return 0
        else:
            time.sleep(1)
            return 0


if __name__ == "__main__":
    Series()
