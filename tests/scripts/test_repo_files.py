#!/usr/bin/env python3
#
# Copyright (c) 2022 Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0

from unittest import TestCase, main, skipIf, SkipTest
from pathlib import Path
from re import search, S, compile
from urllib import request
from urllib.error import HTTPError, URLError
from argparse import ArgumentParser
from subprocess import Popen, check_output, PIPE, run
from pycodestyle import StyleGuide
from shutil import rmtree, copy2
from platform import python_version_tuple
from sys import platform
from threading import Thread
from tempfile import mkdtemp
import os


p_root = Path(__file__).absolute().parents[2]
p_tests = p_root / 'tests'
p_readme = p_root / "README.md"
p_pypi_readme = p_root / "pypi_README.md"
p_architecture = p_root / "ARCHITECTURE.md"
p_release_notes = p_root / "RELEASE_NOTES.md"
p_init_py = p_root / '__init__.py'
p_zcbor_py = p_root / 'zcbor' / 'zcbor.py'
p_add_helptext = p_root / 'scripts' / 'add_helptext.py'
p_regenerate_samples = p_root / 'scripts' / 'regenerate_samples.py'
p_test_zcbor_py = p_tests / 'scripts' / 'test_zcbor.py'
p_test_versions_py = p_tests / 'scripts' / 'test_versions.py'
p_test_repo_files_py = p_tests / 'scripts' / 'test_repo_files.py'
p_hello_world_sample = p_root / 'samples' / 'hello_world'
p_hello_world_build = p_hello_world_sample / 'build'
p_pet_sample = p_root / 'samples' / 'pet'
p_pet_cmake = p_pet_sample / 'pet.cmake'
p_pet_include = p_pet_sample / 'include'
p_pet_src = p_pet_sample / 'src'
p_pet_build = p_pet_sample / 'build'


class TestCodestyle(TestCase):
    def do_codestyle(self, files, **kwargs):
        style = StyleGuide(max_line_length=100, **kwargs)
        result = style.check_files([str(f) for f in files])
        result.print_statistics()
        self.assertEqual(result.total_errors, 0,
                         f"Found {result.total_errors} style errors")

    def test_codestyle(self):
        """Run codestyle tests on all Python scripts in the repo."""
        self.do_codestyle([p_init_py, p_test_versions_py, p_test_repo_files_py, p_add_helptext,
                           p_regenerate_samples])
        self.do_codestyle([p_zcbor_py], ignore=['W191', 'E101', 'W503'])
        self.do_codestyle([p_test_zcbor_py], ignore=['E402', 'E501', 'W503'])


def version_int(in_str):
    return int(search(r'\A\d+', in_str)[0])  # e.g. '0rc' -> '0'


class TestSamples(TestCase):
    def popen_test(self, args, input='', exp_retcode=0, **kwargs):
        call0 = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
        stdout0, stderr0 = call0.communicate(input)
        self.assertEqual(exp_retcode, call0.returncode, stderr0.decode('utf-8'))
        return stdout0, stderr0

    def cmake_build_run(self, path, build_path):
        if build_path.exists():
            rmtree(build_path)
        with open(path / 'README.md', 'r', encoding="utf-8") as f:
            contents = f.read()

        to_build_patt = r'### To build:.*?```(?P<to_build>.*?)```'
        to_run_patt = r'### To run:.*?```(?P<to_run>.*?)```'
        exp_out_patt = r'### Expected output:.*?(?P<exp_out>(\n>[^\n]*)+)'
        to_build = search(to_build_patt, contents, flags=S)['to_build'].strip()
        to_run = search(to_run_patt, contents, flags=S)['to_run'].strip()
        exp_out = search(exp_out_patt, contents, flags=S)['exp_out'].replace("\n> ", "\n").strip()

        os.chdir(path)
        commands_build = [(line.split(' ')) for line in to_build.split('\n')]
        assert '\n' not in to_run, "The 'to run' section should only have one command."
        commands_run = to_run.split(' ')
        for c in commands_build:
            self.popen_test(c)
        output_run = ""
        for c in commands_run:
            output, _ = self.popen_test(c)
            output_run += output.decode('utf-8')
        self.assertEqual(exp_out, output_run.strip())

    @skipIf(platform.startswith("win"), "Skip on Windows because requires a Unix shell.")
    def test_hello_world(self):
        output = self.cmake_build_run(p_hello_world_sample, p_hello_world_build)

    @skipIf(platform.startswith("win"), "Skip on Windows because requires a Unix shell.")
    def test_pet(self):
        output = self.cmake_build_run(p_pet_sample, p_pet_build)

    def test_pet_regenerate(self):
        """Check the zcbor-generated code for the "pet" sample"""
        regenerate = Popen(["python3", p_regenerate_samples, "--check"])
        regenerate.communicate()
        self.assertEqual(0, regenerate.returncode)

    def test_pet_file_header(self):
        files = (list(p_pet_include.iterdir()) + list(p_pet_src.iterdir()) + [p_pet_cmake])
        for p in [f for f in files if "pet" in f.name]:
            with p.open('r', encoding="utf-8") as f:
                f.readline()  # discard
                self.assertEqual(
                    f.readline().strip(" *#\n"),
                    "Copyright (c) 2022 Nordic Semiconductor ASA")
                f.readline()  # discard
                self.assertEqual(
                    f.readline().strip(" *#\n"),
                    "SPDX-License-Identifier: Apache-2.0")
                f.readline()  # discard
                self.assertIn("Generated using zcbor version", f.readline())
                self.assertIn("https://github.com/NordicSemiconductor/zcbor", f.readline())
                self.assertIn("Generated with a --default-max-qty of", f.readline())


class TestDocs(TestCase):
    @staticmethod
    def _repo_url_to_github_https(repo_url: str) -> str | None:
        """Convert common git remote URL formats to https://github.com/..."""
        repo_url = repo_url.strip()

        # git@github.com:org/repo(.git)
        if repo_url.startswith("git@github.com:"):
            repo_url = "https://github.com/" + repo_url.removeprefix("git@github.com:")

        # git@github.com/org/repo(.git)
        elif repo_url.startswith("git@github.com/"):
            repo_url = "https://github.com/" + repo_url.removeprefix("git@github.com/")

        # ssh://git@github.com/org/repo(.git)
        elif repo_url.startswith("ssh://git@github.com/"):
            repo_url = "https://github.com/" + repo_url.removeprefix("ssh://git@github.com/")

        # https://github.com/org/repo(.git)
        elif repo_url.startswith("https://github.com/"):
            pass

        # http://github.com/org/repo(.git)
        elif repo_url.startswith("http://github.com/"):
            repo_url = "https://github.com/" + repo_url.removeprefix("http://github.com/")

        else:
            return None

        if repo_url.endswith(".git"):
            repo_url = repo_url.removesuffix(".git")

        return repo_url

    def __init__(self, *args, **kwargs):
        """Overridden to get base URL for relative links from remote tracking branch."""
        super(TestDocs, self).__init__(*args, **kwargs)
        remote_tr_args = ['git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']
        remote_tracking = run(remote_tr_args, capture_output=True).stdout.decode('utf-8').strip()

        if remote_tracking:
            remote, remote_branch = remote_tracking.split('/', 1)  # '1' to only split one time.
            repo_url_args = ['git', 'remote', 'get-url', remote]
            repo_url_raw = check_output(repo_url_args).decode('utf-8').strip()
            repo_url = self._repo_url_to_github_https(repo_url_raw)

            # Use /blob/<branch>/ so relative file links resolve correctly.
            self.base_url = (repo_url + '/blob/' + remote_branch + '/') if repo_url else None
        elif "GITHUB_SHA" in os.environ and "GITHUB_REPOSITORY" in os.environ:
            repo = os.environ["GITHUB_REPOSITORY"]
            sha = os.environ["GITHUB_SHA"]
            self.base_url = f"https://github.com/{repo}/blob/{sha}/"
        else:
            # There is no remote tracking branch.
            self.base_url = None

        self.link_regex = compile(r'\[.*?\]\((?P<link>.*?)\)')

    def check_code(self, link, codes):
        """Check the status code of a URL link. Assert if not 200 (OK)."""
        try:
            req = request.Request(
                link,
                headers={
                    # Some sites (e.g. Wikipedia) may reject urllib's default user-agent.
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) zcbor-tests",
                },
            )
            call = request.urlopen(req, timeout=10)
            code = call.getcode()
        except HTTPError as e:
            code = e.code
        except Exception as e:
            # Avoid noisy thread stack traces; surface the root cause in the assertion.
            code = f"{type(e).__name__}: {e}"
        codes.append((link, code))

    def do_test_links(self, path, allow_local=True):
        """Get all Markdown links in the file at <path> and check that they work."""
        if allow_local and self.base_url is None:
            raise SkipTest('This test requires the current branch to be pushed to Github.')

        text = path.read_text(encoding="utf-8")

        if allow_local:
            # Use .parent to test relative links (links to repo files):
            relative_path = str(path.relative_to(p_root).parent)
            relative_path = "" if relative_path == "." else relative_path + "/"

        matches = self.link_regex.findall(text)
        codes = list()
        for m in matches:
            link = m
            if allow_local:
                if link.startswith("#"):
                    # Github sometimes need the filename for anchor (#) links to work, so add it:
                    link = path.name + m
                if not link.startswith("https://"):
                    link = self.base_url + relative_path + link
            else:
                self.assertTrue(link.startswith("https://"), "Link is not a URL")

            # Run sequentially to avoid noisy threaded exception dumps when
            # the environment has SSL/HTTP issues.
            self.check_code(link, codes)

        for link, code in codes:
            if isinstance(code, int):
                self.assertEqual(code, 200, f"'{link}' gives code {code}")
            else:
                self.fail(f"'{link}' failed: {code}")

    def test_readme_links(self):
        self.do_test_links(p_readme)

    def test_architecture(self):
        self.do_test_links(p_architecture)

    def test_release_notes(self):
        self.do_test_links(p_release_notes)

    def test_hello_world_readme(self):
        self.do_test_links(p_hello_world_sample / "README.md")

    def test_pet_readme(self):
        self.do_test_links(p_pet_sample / "README.md")

    def test_pypi_readme(self):
        self.do_test_links(p_pypi_readme, allow_local=False)

    @skipIf(list(map(version_int, python_version_tuple())) < [3, 10, 0],
            "Skip on Python < 3.10 because of different wording in argparse output.")
    @skipIf(platform.startswith("win"), "Skip on Windows because of path/newline issues.")
    def test_cli_doc(self):
        """Check the auto-generated CLI docs in the top level README.md file."""
        add_help = Popen(["python3", p_add_helptext, "--check"])
        add_help.communicate()
        self.assertEqual(0, add_help.returncode)


if __name__ == "__main__":
    main()
