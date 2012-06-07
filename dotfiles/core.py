# -*- coding: utf-8 -*-

"""
dotfiles.core
~~~~~~~~~~~~~

This module provides the basic functionality of dotfiles.
"""

import os
import shutil
import fnmatch
import sys
import warnings


__version__ = '0.5.3'
__author__ = 'Jon Bernard'
__license__ = 'ISC'


SEPARATORS = os.sep + (os.altsep if os.altsep else '')


if sys.platform != 'win32':
    symlink = os.symlink
else:
    def symlink(source, link_name):
        os.symlink(source, link_name, os.path.isdir(source))

def delete(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


class Dotfile(object):

    def __init__(self, name, target, home):
        self.name = os.path.join(home, name)
        self.basename = os.path.basename(self.name)
        self.target = target.rstrip(SEPARATORS)
        self.status = ''
        if not os.path.lexists(self.name):
            self.status = 'missing'
        elif os.path.realpath(self.name) != self.target:
            self.status = 'unsynced'

    def sync(self, handle_existing):
        if handle_existing not in ['skip', 'overwrite', 're-add']:
            raise ValueError(
                    'unknown value for handle_exisiting: %s' % handle_existing)
        if self.status == '':
            # already synced - nothing to do
            return
        if self.status == 'unsynced':
            if handle_existing == 'skip':
                print("Skipping \"%s\", use --force or --re-add to override"
                        % self.basename)
                return
            if handle_existing == 're-add':
                delete(self.target)
                shutil.move(self.name, self.target)
            else:
                delete(self.name)
        symlink(self.target, self.name)
        self.status = ''

    def add(self):
        if self.status == 'missing':
            print("Skipping \"%s\", file not found" % self.basename)
            return
        if self.status == '':
            print("Skipping \"%s\", already managed" % self.basename)
            return
        shutil.move(self.name, self.target)
        symlink(self.target, self.name)
        self.status = ''

    def remove(self):
        if self.status != '':
            print("Skipping \"%s\", file is %s" % (self.basename, self.status))
            return
        os.remove(self.name)
        shutil.move(self.target, self.name)
        self.status == 'unsynced'

    def __str__(self):
        return '%-18s %-s' % (self.basename, self.status)


class Dotfiles(object):
    """A Dotfiles Repository."""

    __attrs__ = ['homedir', 'repository', 'prefix', 'ignore', 'externals']

    def __init__(self, **kwargs):

        # Map args from kwargs to instance-local variables
        for k, v in kwargs.items():
            if k in self.__attrs__:
                setattr(self, k, v)
            else:
                warnings.warn("unknown keyword argument '%s'" % k)

        self._load()

    def _load(self):
        """Load each dotfile in the repository."""

        self.dotfiles = list()

        all_repofiles = os.listdir(self.repository)
        repofiles_to_symlink = set(all_repofiles)

        for pat in self.ignore:
            repofiles_to_symlink.difference_update(
                    fnmatch.filter(all_repofiles, pat))

        for dotfile in repofiles_to_symlink:
            self.dotfiles.append(Dotfile('.' + dotfile[len(self.prefix):],
                os.path.join(self.repository, dotfile), self.homedir))

        for dotfile in self.externals.keys():
            self.dotfiles.append(Dotfile(dotfile,
                os.path.expanduser(self.externals[dotfile]),
                self.homedir))

    def _fqpn(self, dotfile):
        """Return the fully qualified path to a dotfile."""

        return os.path.join(self.repository,
                            self.prefix + os.path.basename(dotfile)[1:])

    def list(self, verbose=True):
        """List the contents of this repository."""

        for dotfile in sorted(self.dotfiles, key=lambda dotfile: dotfile.name):
            if dotfile.status or verbose:
                print(dotfile)

    def check(self):
        """List only unsynced and/or missing dotfiles."""

        self.list(verbose=False)

    def sync(self, handle_existing='skip'):

        """Synchronize this repository, creating and updating the necessary
        symbolic links."""

        for dotfile in self.dotfiles:
            dotfile.sync(handle_existing)

    def add(self, files):
        """Add dotfile(s) to the repository."""

        self._perform_action('add', files)

    def remove(self, files):
        """Remove dotfile(s) from the repository."""

        self._perform_action('remove', files)

    def _perform_action(self, action, files):
        for file in files:
            file = file.rstrip(SEPARATORS)
            if os.path.basename(file).startswith('.'):
                getattr(Dotfile(file, self._fqpn(file), self.homedir), action)()
            else:
                print("Skipping \"%s\", not a dotfile" % file)
        self._load()

    def move(self, target):
        """Move the repository to another location."""

        if os.path.exists(target):
            raise ValueError('Target already exists: %s' % (target))

        old_statuses = dict((dotfile.name, dotfile.status)
                            for dotfile in self.dotfiles)

        shutil.move(self.repository, target)

        self.repository = target

        self._load()

        for dotfile in self.dotfiles:
            if old_statuses[dotfile.name] == '' \
                    and dotfile.status == 'unsynced':
                dotfile.sync(handle_existing='overwrite')
