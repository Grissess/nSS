import nss
import curses
import time

class Env(object):
    def __init__(self):
        self.scr=curses.initscr()
        curses.cbreak()
        curses.noecho()
        self.scr.keypad(1)
        curses.start_color()
        self.scr.bkgdset(ord(' '), curses.color_pair(curses.COLOR_BLUE))
    def Render(self):
        self.scr.addstr(0, 0, 'This is a shitton of text for you to read!\nHave a nice motherfucking day!\n', curses.color_pair(curses.COLOR_YELLOW))
        self.scr.addstr('(mofos)', curses.color_pair(curses.COLOR_RED))
        self.scr.refresh()
    def __del__(self):
        self.scr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()

env=Env()
env.Render()
time.sleep(5)

#env=nss.CursesConsoleHTTPEnvironment()

#env.cmdloop()
