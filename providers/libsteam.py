# filename:     libsteam.py
# description:  Collection of functions directly related to the Steam client
#               handling within steamclean.py

from platform import architecture as pa
import logging
import os
import re
import winreg

# module specific sublogger to avoid duplicate log entries
liblogger = logging.getLogger('steamclean.libsteam')


def winreg_read():
    """ Get Steam installation path from reading registry data.
    If unable to read registry information prompt user for input. """

    arch = pa()[0]
    regbase = 'HKEY_LOCAL_MACHINE\\'
    regkey = None

    # use architecture returned to evaluate appropriate registry key
    if arch == '64bit':
        regpath = r'SOFTWARE\Wow6432Node\Valve\Steam'
        regopts = (winreg.KEY_WOW64_64KEY + winreg.KEY_READ)
    elif arch == '32bit':
        liblogger.info('32 bit operating system detected')

        regpath = r'SOFTWARE\Valve\Steam'
        regopts = winreg.KEY_READ
    else:
        liblogger.error('Unable to determine system architecture.')
        raise ValueError('ERROR: Unable to determine system architecture.')

    try:
        regkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, regpath, 0,
                                  regopts)
        # Save installation path value and close open registry key.
        ipath = winreg.QueryValueEx(regkey, 'InstallPath')[0]

    except PermissionError:
        liblogger.error('Permission denied to read registry key',
                     regbase + regpath)
        liblogger.error('Run this script as administrator to resolve.')
        print('Permission denied to read registry data at %s.', regpath)

        ipath = input('Please enter the Steam installation directory: ')

    finally:
        # Ensure registry key is closed after reading as applicable.
        if regkey is not None:
            liblogger.info('Registry data at %s used to determine ' +
                        'installation path', regbase + regpath)
            liblogger.info('Steam installation path found at %s', ipath)

            winreg.CloseKey(regkey)

        installpath = os.path.abspath(ipath.strip())
        return installpath


def get_libraries(steamdir):
    """ Attempt to automatically read extra Steam library directories by
        checking the libraryfolders.vdf file. """

    libfiledir = os.path.join(steamdir, 'steamapps')
    # Build the path to libraryfolders.vdf which stores configured libraries.
    libfile = os.path.abspath(os.path.join(libfiledir, 'libraryfolders.vdf'))
    # This regex checks for lines starting with the number and grabs the
    # path specified in that line by matching anything within quotes.
    libregex = re.compile('(^\t"[1-8]").*(".*")')

    try:
        libdirs = []

        liblogger.info('Attempting to read libraries from %s', libfile)
        with open(libfile) as file:
            for line in file:
                dir = libregex.search(line)
                if dir:
                    # Normalize directory path which is the second match group
                    ndir = os.path.normpath(dir.group(2))
                    liblogger.info('Library found at %s', ndir)
                    libdirs.append(ndir.strip('"'))

        # Return list of any directories found, directories are checked
        # outside of this function for validity and are ignored if invalid.
        return libdirs
    except FileNotFoundError:
        liblogger.error('Unable to find file %s', libfile, steamdir)
        print('Unable to find file %s' % (libfile, steamdir))
    except PermissionError:
        liblogger.error('Permission denied to %s', libfile)
        print('Permission denied to %s' % (libfile))