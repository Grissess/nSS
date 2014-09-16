nSS
===

neXus Service System is a very, very simple and lightweight pure-Python webserver, suitable for very small projects--especially ones where a Python interpreter is available (perhaps as the language of a web app) and installing another server is otherwise prohibitive.

Nearly the entirety of the webserver is contained in one file; most of the actual serving functions are provided through small modules containing `HTTPManager`s that generate data (or errors :). See the included _ex.py modules for examples of such managers; the current ones include basic managers (managers that always serve one file), filesystem managers (both static filesystem and standard CGI), and debug managers (that show the status of the server). This modular system should make it fairly easy to add different methods of content generation to the server (WSGI is a big TODO).

The server can be instructed through console commands. On Windows installations, these can be issued at the terminal; on POSIX-compatible systems, a long-standing bug prevents this from occuring (ncurses will exit() the process without warning). The command system can be fairly easily integrated with the `ConsoleHTTPEnvironment` if one wishes to design a method of issuing commands to the server at runtime.

In any case, the first command executed by the server is:

    exec autoexec.txt
  
This executes the file `autoexec.txt` line by line. This file may, in turn, execute other files.

Arguably the most important command for startup scripts is the `mount` command, with the following syntax:

    mount <host> <path> <module> <class>
  
Where `<host>` is the virtual host (as would be present in a `Host:` HTTP header, and may be `.` to represent any valid host), `<path>` is a mount path (which should end with a trailing `/` for managers that serve directories), `<module>` is a python module (anywhere in `sys.path`, including `.`), and `<class>` is a class in that module implementing the `HTTPManager` interface. For examples of this in use, look at `nexus.txt`.
