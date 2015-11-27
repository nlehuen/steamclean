﻿#!/usr/bin/env python3

# Filename:         steamclean.py
# Published:        2015.11.27
# Description:      Script to find and remove extraneous files from
#                   Steam game installation directories.

from datetime import date
from platform import architecture as pa
from platform import platform as pp
import argparse
import logging
import os
import re

if (os.name == 'nt'):
    import winreg


# build logger and its configuration to write script data to specified log
logger = logging.getLogger('steamclean')
logger.setLevel(logging.INFO)
logformatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s',
                                 datefmt='%Y-%m-%d %H:%M:%S')
fh = logging.FileHandler('steamclean_' + str(date.today()) + '.log')
fh.setFormatter(logformatter)
logger.addHandler(fh)


def print_header():
    """ Clear terminal window and print script name and release date. """

    if os.name == 'nt':
        os.system('cls')
    elif os.name == 'posix':
        os.system('clear')

    # Attempt to print script name and modified date as header if able
    try:
        filename = os.path.basename(__file__)
        publishon = str(date.fromtimestamp(os.path.getmtime(__file__)))

        print('%s last updated %s \n' % (filename, publishon))
        logger.info('Starting script ' + filename + ' updated ' + publishon)
        logger.info('Current operating system: ' + pp() + ' ' + pa()[0])
    except:
        logger.warning('Unable to script information from file %s', filename)
        pass


def win_reg_check():
    """ Get Steam installation path from reading registry data.
        If unable to read registry information prompt user for input. """

    arch = pa()[0]
    regbase = 'HKEY_LOCAL_MACHINE\\'
    regkey = None

    # use architecture returned to evaluate appropriate registry key
    if arch == '64bit':
        logger.info('64bit operating system detected')

        regpath = r'SOFTWARE\Wow6432Node\Valve\Steam'
        regopts = (winreg.KEY_WOW64_64KEY + winreg.KEY_READ)
    elif arch == '32bit':
        logger.info('32 bit operating system detected')

        regpath = r'SOFTWARE\Valve\Steam'
        regopts = winreg.KEY_READ
    else:
        logger.error('Unable to determine system architecture.')
        raise ValueError('ERROR: Unable to determine system architecture.')

    try:
        regkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, regpath, 0,
                                  regopts)
        # Save installation path value and close open registry key.
        ipath = winreg.QueryValueEx(regkey, 'InstallPath')[0]

    except PermissionError:
        logger.error('Unable to read registry data at %s due to insufficient \
                 privileges.', regbase + regpath)
        logger.error('Run this script as administrator to resolve.')
        print('Permission denied to read registry data at %s.', regpath)

        ipath = input('Please enter the Steam installation directory: ')

    finally:
        # Ensure registry key is closed after reading as applicable.
        if regkey is not None:
            logger.info('Registry data at %s used to determine installation' +
                        ' path', regbase + regpath)
            logger.info('Steam installation path found at %s', ipath)

            winreg.CloseKey(regkey)

        return ipath.strip()


def analyze_vdf(steamdir, nodir=False, library=None):
    """ Find all .vdf files in provided locations and
    extract file locations of redistributable data. """

    gamedir = {}
    cleanable = {}

    # validate steamdirectory or prompt for input when invalid or missing
    while os.path.isdir(steamdir) and 'Steam' not in steamdir:
        logger.warning('Invalid or missing directory at %s', steamdir)
        steamdir = os.path.abspath(
            input('Invalid or missing directory, ' +
                  'please re-enter the directory: '))

    # Validate Steam installation path.
    if os.path.isdir(steamdir) and 'Steam' in steamdir:
        # Append steamapps directory if required.
        if 'SteamApps' not in steamdir:
            steamdir = os.path.join(steamdir, 'SteamApps', 'common')

        logger.info('Game installations located at %s', steamdir)

    # Gather game directories from default path.
    logger.info('Checking %s', steamdir)
    print('Checking %s' % (steamdir))
    for dir in os.listdir(steamdir):
        # if path is a directory and not already in list add it
        if os.path.isdir(os.path.join(steamdir, dir)):
            if dir not in gamedir:
                gamedir[os.path.join(steamdir, dir)] = ''

    if library is not None:
        # Force lower case and separate multiple libraries.
        liblist = library.lower().split(',')

        # Check all provided libraries.
        for lib in liblist:
            lib = lib.replace('"', '')
            # Verify library path exists and append games directory.
            if os.path.isdir(lib) and 'steam' in lib:
                if 'SteamApps' not in lib:
                    # remove extra quotes from input string
                    lib = os.path.join(lib, 'SteamApps', 'common')

            logger.info('Checking library at %s', lib)
            print('Checking library at %s' % (lib))

            # validate game directories in specified library
            if library is not None and 'SteamApps' in lib \
                    and os.path.isdir(lib):
                for dir in os.listdir(lib):
                    if os.path.isdir(os.path.join(lib, dir)):
                        if dir not in gamedir:
                            gamedir[os.path.join(lib, dir)] = ''

    if not nodir:
        # Build a list of redistributable files found in common folders.
        redistfiles = []
        for game in gamedir:
            for item in os.listdir(game):
                pathlist = os.path.abspath(game + '\\' + item)
                if os.path.isdir(pathlist) and os.path.exists(pathlist):
                    # Determine if path may contain redist file types
                    fileregex = re.compile(r'(.*)(directx|redist|miles)(.*)',
                                           re.IGNORECASE)
                    if fileregex.match(pathlist):
                        # Verify the files being added are valid and exist.
                        for (path, dirs, files) in os.walk(game + '\\' + item):
                            for file in files:
                                filepath = os.path.abspath(path + '\\' + file)
                                # Check for valid installer extensions
                                extregex = re.compile(r'(cab|exe|msi)',
                                                      re.IGNORECASE)
                                if extregex.search(filepath):
                                    if (os.path.isfile(filepath) and
                                            os.path.exists(filepath)):
                                        redistfiles.append(filepath)

        # Add filename and size to cleanable list.
        for rfile in redistfiles:
            cleanable[rfile] = ((os.path.getsize(rfile) / 1024) / 1024)

    # get all vdf files from game directories for review
    for game in gamedir:
        files = os.listdir(game)
        for file in files:
            if '.vdf' in file:
                gamedir[game] = os.path.abspath(game + '\\' + file)

    # Scrub dictionary of entries that do not have a valid .vdf file.
    cleangamedir = {}
    for game in gamedir:
        if gamedir[game] != '':
            cleangamedir[game] = gamedir[game]

    # Substitute game path for %INSTALLDIR% within .vdf file.
    for game in cleangamedir:
        with open(cleangamedir[game]) as vdffile:
            for line in vdffile:
                # Only read lines with an installation specified.
                if 'INSTALLDIR' in line:
                    # Replace %INSTALLDIR% with path and make it valid.
                    splitline = line.split('%')
                    newline = splitline[1].replace('INSTALLDIR', game) + \
                        splitline[2][0: splitline[2].find('.') + 4]

                    # Clean path, appending only existing files to clean list.
                    filepath = os.path.abspath(newline)
                    if os.path.isfile(filepath) and os.path.exists(filepath):
                        filepath = filepath.lower()
                        # Check filename to determine if it is a
                        # redistributable before adding to cleanable to
                        # ensure a required file is not removed.
                        for rc in ['setup', 'redist']:
                            if rc in filepath:
                                cleanable[filepath] = (
                                    (os.path.getsize(filepath) / 1024) / 1024)

    # log all detected files and their size
    for file in cleanable:
        logger.info('File %s found with size %s MB',
                    file, format(cleanable[file], '.2f'))

    # Return the list of cleanable files and their approximate size.
    return cleanable


def clean_data(filelist):
    """ Function to remove found data from installed game directories.
        Will prompt user for a list of files to exclude with the proper
        options otherwise all will be deleted."""

    dry_run(filelist)
    confirm = ''
    excludes = []

    # Print a warning that files will be permanantly deleted and
    # inform user they can exclude files with the -p option.
    print('WARNING: All files will be permanantly deleted! Please see the log '
          'file for specific file information if desired.\n')
    while True:
        confirm = input('Do you wish to remove extra files [y/N]: ').lower()
        if confirm == '':
            break
        elif confirm != 'y' and confirm != 'n':
            continue
        else:
            break

    # Confirm removal of all found files. Print list of files not removed and
    # count of removed items.
    if confirm == 'y':
        removed = 0

        for index, file in enumerate(filelist):
            if index not in excludes:
                try:
                    if os.path.isfile(file) and os.path.exists(file):
                        os.remove(file)
                        removed += 1
                        logger.info('File %s removed successfully', file)

                except FileNotFoundError:
                    logger.error('File %s not found, skipping...', file)
                    print('File %s not found, skipping.' % (file))

                except PermissionError:
                    logger.error('Permission denied to file %s skipping...',
                                 file)
                    print('Permission denied to file %s skipping...' % (file))

        logger.info('%s files removed successfully.', removed)
        print('\n%s files removed successfully.' % (removed))


def dry_run(cleanable):
    """ Print a report of removable files and thier estimated size. """

    filecount = len(cleanable)
    totalsize = 0
    for cfile in cleanable:
        totalsize += cleanable[cfile]

    logger.info('Total number of files marked for removal: %s', filecount)
    logger.info('Estimated disk space saved after removal: %s MB',
                format(totalsize, '.2f'))

    print('\nTotal number of files marked for removal: %s' % filecount)
    print('Estimated disk space saved after removal: %s MB' %
          format(totalsize, '.2f'), '\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Find and clean extraneous files from game directories '
                    'including various Windows redistributables.')
    parser.add_argument('--dryrun',
                        help='Run script without allowing any file removal.',
                        action='store_true')
    parser.add_argument('--nodir',
                        help='Do not clean redistributable directories.',
                        action='store_true')
    parser.add_argument('-l', '--library',
                        help='Additional Steam libraries to examine '
                        '(comma separated).')
    args = parser.parse_args()

    print_header()

    if os.name == 'nt':
        cleanable = analyze_vdf(win_reg_check(), args.nodir, args.library)

        if len(cleanable) > 0:
            if args.dryrun:
                dry_run(cleanable)
            else:
                clean_data(cleanable)
        else:
            print('\nCongratulations! No files were found for removal. ')
    elif os.name == 'posix':
        print('No Linux support at this time. \
        Please report files that can be cleaned.')
    else:
        print('Invalid operating system detected.')

    input('\nPress Enter to exit...')
