"""Basic script to fetch the authentication token for a Google Keep account."""
import logging
import ssl
import sys

import gkeepapi
import pkg_resources

logging.basicConfig(level=logging.INFO)


class GoogleKeepAPI:
    """Handles authentication and operations for Google Keep API."""

    def __init__(self, username: str, password: str):
        """Initialize with user credentials."""
        self._keep = gkeepapi.Keep()
        self._username = username
        self._password = password
        self._token = None

    def authenticate(self) -> bool:
        """Authenticate the user with Google Keep."""
        try:
            self._keep.login(self._username, self._password)
            self._token = self._keep.getMasterToken()
            return True
        except gkeepapi.exception.LoginException as e:
            logging.error("Failed to login to Google Keep: %s", e)
            return False

    @property
    def token(self) -> str:
        """Return the current authentication token."""
        return self._token


def print_versions():
    """Print versions of the script and its dependencies."""
    # Extract only the version number from the OpenSSL version string
    openssl_version = ssl.OPENSSL_VERSION.split()[1]

    version_info = [
        ("Python", sys.version.split()[0]),
        ("OpenSSL", openssl_version),
    ] + [
        (package, pkg_resources.get_distribution(package).version)
        for package in ["gkeepapi", "urllib3", "gpsoauth", "requests"]
    ]

    print("Current Version Information:")
    max_name_length = max(len(name) for name, _ in version_info)
    for name, version in version_info:
        print(f"{name.ljust(max_name_length)}: {version}")


def print_working_versions():
    """Print the known working versions of dependencies."""
    working_versions = {
        "Python": "3.11.4",
        "OpenSSL": "1.1.1n",
        "gkeepapi": "0.14.2",
        "urllib3": "1.26.18",
        "gpsoauth": "1.0.2",
        "requests": "2.31.0",
    }

    max_name_length = max(len(name) for name in working_versions)
    for name, version in working_versions.items():
        print(f"{name.ljust(max_name_length)}: {version}")


def main():
    """Execute main script functionality."""
    print_versions()
    username = input("\nEnter your Google Keep username: ")
    password = input("Enter your Google Keep password: ")

    api = GoogleKeepAPI(username, password)
    if api.authenticate():
        print(f"\nAuthenticated! Token: {api.token}")
    else:
        print(
            "\nAuthentication failed. Please try again with the known working versions:"
        )
        print_working_versions()


if __name__ == "__main__":
    main()
