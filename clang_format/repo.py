from utils import callo
import os
import subprocess
import re


class Repo(object):
    """Class encapsulates all knowledge about a git repository, and its metadata
    to run clang-format.
    """
    def __init__(self, path, custom_regex=""):
        """Initialization method.
        
        :path str Relative path to the Root of the repository

        WARNING: After initialization of the Repo, users should set the
        languages the repo contains (langs_used). This is used to run
        clang-format only on files designated by the langage
        """
        self.path = path
        self.custom_regex = "(" + custom_regex + ")"

        # Programming languages that the files in this repo are written in.
        # Variable is used to decide what files is clang-format ultimately is
        # going to operate on
        self.langs_to_file_endings = {
            "cpp": ["h", "hxx", "cpp", "cc", "cxx"],
            "c": ["h", "c"],
            "objc": ["h", "mm"],
            "java": ["class", "java"],
            "javascript": ["js"],
            None: [],
        }

        self._langs_used = []

        self.root = self._get_root()

    @property
    def langs_used(self):
        return self._langs_used

    @langs_used.setter
    def langs_used(self, langs_in):
        """Set the programming languages that the repo contains files of."""
        assert isinstance(langs_in, list) and \
            ("The languages of the repo should be provided in a list of "
             "strings.\nExiting...")

        assert all([i for i in langs_in if i in
                    self.langs_to_file_endings.keys()]) and \
            ("Some of the given languages (%s) are not "
             "available.\nExiting.".format(langs_in))

        self._langs_used = langs_in

    @langs_used.getter
    def langs_used(self):
        return self._langs_used

    def _callgito(self, args):
        """Call git for this repository, and return the captured output
        """
        # These two flags are the equivalent of -C in newer versions of Git but
        # we use these to support versions pre 1.8.5 but it depends on the
        # command and what the current directory is
        return callo(['git', '--git-dir', os.path.join(self.path, ".git"),
                      '--work-tree', self.path] + args)

    def _callgit(self, args):
        """Call git for this repository without capturing output
        This is designed to be used when git returns non-zero exit codes.
        """
        # These two flags are the equivalent of -C in newer versions of Git but
        # we use these to support versions pre 1.8.5 but it depends on the
        # command and what the current directory is
        return subprocess.call(['git', '--git-dir',
                                os.path.join(self.path, ".git"),
                                '--work-tree', self.path] + args)

    def _get_local_dir(self, path):
        """Get a directory path relative to the git root directory
        """
        if os.path.isabs(path):
            return os.path.relpath(path, self.root)
        return path

    def get_candidates(self, candidates):
        """Get the set of candidate files to check by querying the repository

        Returns the full path to the file for clang-format to consume.
        """
        if candidates is not None and len(candidates) > 0:
            candidates = [self._get_local_dir(f) for f in candidates]
            valid_files = list(set(candidates).intersection(
                self.get_candidate_files()))
        else:
            valid_files = list(self.get_candidate_files())

        # Get the full file name here
        valid_files = [os.path.normpath(os.path.join(self.root, f))
                       for f in valid_files]

        return valid_files

    def get_root(self):
        """Get the root directory for this repository
        """
        return self.root

    def _get_root(self):
        """Gets the root directory for this repository from git
        """
        gito = self._callgito(['rev-parse', '--show-toplevel'])

        return gito.rstrip()

    def _git_ls_files(self, cmd):
        """Run git-ls-files and filter the list of files to a valid candidate
        list

        This constitutes a backbone method for fetching the list of files on
        which clang-format operates on.
        """
        gito = self._callgito(cmd)

        # This allows us to pick all the interesting files
        # in the mongo and mongo-enterprise repos
        file_list = [line.rstrip() for line in gito.splitlines()]

        files_match_str = ""
        for lang in self.langs_used:
            lang_exts = self.langs_to_file_endings[lang]
            for ext in lang_exts + [ext.upper() for ext in lang_exts]:
                files_match_str += ext + "|"

        files_match_str = "(" + files_match_str + ")"

        files_match = re.compile('{}\\.{}$'.format(self.custom_regex,
                                                   files_match_str))
        print files_match.pattern
        file_list = [a for a in file_list if files_match.search(a)]

        return file_list

    def get_candidate_files(self):
        """Query git to get a list of all files in the repo to consider for analysis
        """
        return self._git_ls_files(["ls-files", "--cached"])

    def get_working_tree_candidate_files(self):
        """Query git to get a list of all files in the working tree to consider
        for analysis. Files may not be managed by Git
        """
        files = self._git_ls_files(["ls-files", "--cached", "--others"])
        return files

    def get_working_tree_candidates(self):
        """Get the set of candidate files to check by querying the repository

        Returns the full path to the file for clang-format to consume.
        """
        valid_files = list(self.get_working_tree_candidate_files())

        # Get the full file name here
        valid_files = [os.path.normpath(os.path.join(self.root, f))
                       for f in valid_files]

        return valid_files

    def is_detached(self):
        """Is the current working tree in a detached HEAD state?
        """
        # symbolic-ref returns 1 if the repo is in a detached HEAD state
        return self._callgit(["symbolic-ref", "--quiet", "HEAD"])

    def is_ancestor(self, parent, child):
        """Is the specified parent hash an ancestor of child hash?
        """
        # merge base returns 0 if parent is an ancestor of child
        return not self._callgit(
            ["merge-base", "--is-ancestor", parent, child])

    def is_commit(self, sha1):
        """Is the specified hash a valid git commit?
        """
        # cat-file -e returns 0 if it is a valid hash
        return not self._callgit(["cat-file", "-e", "%s^{commit}" % sha1])

    def is_working_tree_dirty(self):
        """Does the current working tree have changes?
        """
        # diff returns 1 if the working tree has local changes
        return self._callgit(["diff", "--quiet"])

    def does_branch_exist(self, branch):
        """Does the branch exist?
        """
        # rev-parse returns 0 if the branch exists
        return not self._callgit(["rev-parse", "--verify", branch])

    def get_merge_base(self, commit):
        """Get the merge base between 'commit' and HEAD
        """
        return self._callgito(["merge-base", "HEAD", commit]).rstrip()

    def get_branch_name(self):
        """Get the current branch name, short form
           This returns "master", not "refs/head/master"
           Will not work if the current branch is detached
        """
        branch = self.rev_parse(["--abbrev-ref", "HEAD"])
        if branch == "HEAD":
            raise ValueError("Branch is currently detached")

        return branch

    def add(self, command):
        """git add wrapper
        """
        return self._callgito(["add"] + command)

    def checkout(self, command):
        """git checkout wrapper
        """
        return self._callgito(["checkout"] + command)

    def commit(self, command):
        """git commit wrapper
        """
        return self._callgito(["commit"] + command)

    def diff(self, command):
        """git diff wrapper
        """
        return self._callgito(["diff"] + command)

    def log(self, command):
        """git log wrapper
        """
        return self._callgito(["log"] + command)

    def rev_parse(self, command):
        """git rev-parse wrapper
        """
        return self._callgito(["rev-parse"] + command).rstrip()

    def rm(self, command):
        """git rm wrapper
        """
        return self._callgito(["rm"] + command)

    def show(self, command):
        """git show wrapper
        """
        return self._callgito(["show"] + command)


